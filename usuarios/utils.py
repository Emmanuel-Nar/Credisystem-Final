from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .whatsapp import enviar_codigo_whatsapp


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _enlace_token(usuario, ruta):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    base = settings.BACKEND_PUBLIC_URL.rstrip("/")
    return f"{base}{ruta.format(uid=uid, token=token)}"


def enviar_codigo_verificacion(usuario, codigo_obj, canal="whatsapp"):
    if canal == "whatsapp" and usuario.telefono:
        if enviar_codigo_whatsapp(usuario.telefono, codigo_obj.codigo):
            return "whatsapp"
    if codigo_obj.tipo == codigo_obj.Tipo.REGISTRO:
        asunto = "Verificá tu email - CREDISYSTEM"
        enlace = _enlace_token(usuario, "/api/auth/verificar/enlace/{uid}/{token}/")
        accion = f"También podés verificar tu email desde este enlace: {enlace}"
    else:
        asunto = "Recuperá tu contraseña - CREDISYSTEM"
        enlace = _enlace_token(usuario, "/api/auth/password/enlace/{uid}/{token}/")
        accion = f"También podés recuperar tu contraseña desde este enlace: {enlace}"
    mensaje = (
        f"Hola {usuario.nombre}, tu código es {codigo_obj.codigo}. "
        f"Vence en {settings.AUTH_CODIGO_EXPIRA_MINUTOS} minutos.\n\n{accion}\n\n"
        "Si no lo solicitaste, ignorá este mensaje."
    )
    send_mail(asunto, mensaje, from_email=None, recipient_list=[usuario.email], fail_silently=True)
    return "email"
