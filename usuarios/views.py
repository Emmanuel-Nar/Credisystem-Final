from django.conf import settings
from django.db import transaction
from django.contrib.auth import authenticate, login as iniciar_sesion, logout as cerrar_sesion
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CodigoVerificacion, Usuario
from .serializers import (
    ConfirmarRecuperacionSerializer,
    CambiarPasswordSerializer,
    LoginSerializer,
    ReenviarCodigoSerializer,
    RegistroSerializer,
    SolicitarRecuperacionSerializer,
    UsuarioPerfilSerializer,
    VerificarCodigoSerializer,
)
from .services import bloqueo_activo, evaluar_bloqueo_por_intentos, registrar_intento
from .utils import enviar_codigo_verificacion, get_client_ip


def _emitir_tokens(usuario):
    refresh = RefreshToken.for_user(usuario)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegistroView(APIView):
    """CU1: registro de usuario. Crea la cuenta inactiva y envía código
    de verificación por email (o SMS/WhatsApp si se integra ese canal)."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            usuario = serializer.save()
            codigo_obj = CodigoVerificacion.generar(
                usuario, CodigoVerificacion.Tipo.REGISTRO, settings.AUTH_CODIGO_EXPIRA_MINUTOS
            )
        canal = enviar_codigo_verificacion(usuario, codigo_obj)

        mensajes = {
            "email": "Cuenta creada. Enviamos el código de activación a tu correo. Revisá también Spam.",
            "whatsapp": "Cuenta creada. Enviamos el código de activación por WhatsApp.",
            "consola": "Cuenta creada en modo de desarrollo. El código está en la consola del servidor; no se envió un correo real.",
            "no_enviado": "Tu cuenta fue creada, pero no pudimos enviar el código. Podés solicitar un reenvío sin registrarte otra vez.",
        }
        return Response(
            {"detail": mensajes[canal], "canal_verificacion": canal, "codigo_enviado": canal in {"email", "whatsapp"}},
            status=status.HTTP_201_CREATED,
        )


class VerificarCuentaView(APIView):
    """CU1 (paso 4-6): valida el código y activa la cuenta."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def post(self, request):
        serializer = VerificarCodigoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.validated_data["usuario"]
        codigo_obj = serializer.validated_data["codigo_obj"]

        codigo_obj.usado = True
        codigo_obj.save(update_fields=["usado"])

        usuario.is_active = True
        usuario.estado = Usuario.Estado.ACTIVO
        usuario.email_verificado = True
        usuario.save(update_fields=["is_active", "estado", "email_verificado"])

        tokens = _emitir_tokens(usuario)
        return Response(
            {"detail": "Cuenta verificada correctamente.", **tokens},
            status=status.HTTP_200_OK,
        )


class ReenviarCodigoView(APIView):
    """Flujo alternativo del CU1: reenvío de código si el original expiró."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def post(self, request):
        serializer = ReenviarCodigoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        usuario = Usuario.objects.filter(email=email, is_active=False).first()
        if usuario:
            codigo_obj = CodigoVerificacion.generar(
                usuario, CodigoVerificacion.Tipo.REGISTRO, settings.AUTH_CODIGO_EXPIRA_MINUTOS
            )
            enviar_codigo_verificacion(usuario, codigo_obj)

        # Respuesta genérica siempre, exista o no la cuenta (anti enumeración)
        return Response(
            {"detail": "Si hay una cuenta pendiente, se intentó enviar el código por el canal configurado. Si no lo recibís, revisá Spam y volvé a intentarlo."},
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    CU2: inicio de sesión + CU10: bloqueo por intentos fallidos.
    Cada intento (exitoso o no) queda registrado en IntentoAcceso.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        ip = get_client_ip(request)

        usuario = Usuario.objects.filter(email=email).first()

        # Email inexistente: mensaje genérico, no confirmamos si existe o no
        if usuario is None:
            return Response(
                {"detail": "Credenciales inválidas."}, status=status.HTTP_401_UNAUTHORIZED
            )

        bloqueo = bloqueo_activo(usuario)
        if bloqueo:
            registrar_intento(usuario, exito=False, ip=ip, motivo_fallo="cuenta_bloqueada")
            minutos_restantes = max(0, int((bloqueo.fecha_fin - timezone.now()).total_seconds() // 60) + 1)
            return Response(
                {
                    "detail": f"Cuenta bloqueada temporalmente por intentos fallidos. "
                              f"Volvé a intentar en {minutos_restantes} minuto(s).",
                    "bloqueada_hasta": bloqueo.fecha_fin,
                },
                status=status.HTTP_423_LOCKED,
            )

        if not usuario.is_active:
            registrar_intento(usuario, exito=False, ip=ip, motivo_fallo="cuenta_no_verificada")
            return Response(
                {"detail": "Tu cuenta todavía no fue verificada."},
                status=status.HTTP_403_FORBIDDEN,
            )

        usuario_autenticado = authenticate(request, email=email, password=password)

        if usuario_autenticado is None:
            registrar_intento(usuario, exito=False, ip=ip, motivo_fallo="password_incorrecta")
            nuevo_bloqueo = evaluar_bloqueo_por_intentos(usuario)
            if nuevo_bloqueo:
                return Response(
                    {
                        "detail": "Superaste el número de intentos permitidos. "
                                  f"Tu cuenta quedó bloqueada {settings.AUTH_BLOQUEO_MINUTOS} minutos.",
                        "bloqueada_hasta": nuevo_bloqueo.fecha_fin,
                    },
                    status=status.HTTP_423_LOCKED,
                )
            return Response(
                {"detail": "Credenciales inválidas."}, status=status.HTTP_401_UNAUTHORIZED
            )

        registrar_intento(usuario, exito=True, ip=ip)
        return self.respuesta_login(request, usuario_autenticado)

    def respuesta_login(self, request, usuario_autenticado):
        tokens = _emitir_tokens(usuario_autenticado)
        return Response(
            {**tokens, "usuario": UsuarioPerfilSerializer(usuario_autenticado).data},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginWebView(LoginView):
    """Login del formulario web; solo el superusuario obtiene sesión de admin."""

    authentication_classes = []

    def respuesta_login(self, request, usuario_autenticado):
        if usuario_autenticado.is_superuser and usuario_autenticado.is_staff:
            iniciar_sesion(request, usuario_autenticado)
            return Response({"admin_url": reverse("admin:index")})
        # Evita conservar la sesión administrativa al cambiar a una cuenta cliente.
        cerrar_sesion(request)
        return super().respuesta_login(request, usuario_autenticado)


class LogoutView(APIView):
    """Invalida el refresh token (requiere el blacklist de simplejwt)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Falta el refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Sesión cerrada."}, status=status.HTTP_205_RESET_CONTENT)


class SolicitarRecuperacionView(APIView):
    """CU9 (paso 1-4): pide el email y envía el código de recuperación."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def post(self, request):
        serializer = SolicitarRecuperacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        usuario = Usuario.objects.filter(email=email).first()
        if usuario:
            codigo_obj = CodigoVerificacion.generar(
                usuario, CodigoVerificacion.Tipo.RECUPERACION, settings.AUTH_CODIGO_EXPIRA_MINUTOS
            )
            enviar_codigo_verificacion(usuario, codigo_obj)

        # Respuesta genérica siempre (anti enumeración de usuarios)
        return Response(
            {"detail": "Si existe una cuenta con ese correo, se intentó enviar el código de recuperación. Si no lo recibís, revisá Spam y volvé a intentarlo."},
            status=status.HTTP_200_OK,
        )


class ConfirmarRecuperacionView(APIView):
    """CU9 (paso 5-6): valida el código y define la nueva contraseña."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def post(self, request):
        serializer = ConfirmarRecuperacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.validated_data["usuario"]
        codigo_obj = serializer.validated_data["codigo_obj"]

        codigo_obj = serializer.validated_data.get("codigo_obj")
        if codigo_obj:
            codigo_obj.usado = True
            codigo_obj.save(update_fields=["usado"])

        usuario.set_password(serializer.validated_data["password_nueva"])
        # Si estaba bloqueada por intentos fallidos, restablecer la contraseña
        # también levanta el bloqueo (dueño legítimo demostró identidad).
        if usuario.estado == Usuario.Estado.BLOQUEADO:
            usuario.estado = Usuario.Estado.ACTIVO
        usuario.save()

        return Response({"detail": "Contraseña actualizada correctamente."}, status=status.HTTP_200_OK)


class PerfilView(APIView):
    """Consultar el perfil y actualizar solo los datos de contacto del usuario."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioPerfilSerializer(request.user).data)

    def patch(self, request):
        serializer = UsuarioPerfilSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CambiarPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["password_nueva"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Contraseña actualizada correctamente."}, status=status.HTTP_200_OK)


class VerificarEmailEnlaceView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def get(self, request, uidb64, token):
        try:
            usuario = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
            usuario = None
        if not usuario or not default_token_generator.check_token(usuario, token):
            return redirect("verificar_email")
        usuario.is_active = True
        usuario.estado = Usuario.Estado.ACTIVO
        usuario.email_verificado = True
        usuario.save(update_fields=["is_active", "estado", "email_verificado"])
        CodigoVerificacion.objects.filter(usuario=usuario, tipo=CodigoVerificacion.Tipo.REGISTRO, usado=False).update(usado=True)
        return redirect("/login/?email_verificado=1")


class RecuperacionEnlaceView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "anon"

    def get(self, request, uidb64, token):
        try:
            usuario = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
            usuario = None
        if not usuario or not default_token_generator.check_token(usuario, token):
            return redirect("/recuperar-password/?enlace=invalido")
        return redirect(f"/confirmar-password/?uid={uidb64}&token={token}")
