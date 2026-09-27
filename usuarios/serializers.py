from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import CodigoVerificacion, Usuario


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ["nombre", "apellido", "email", "telefono", "documento", "direccion", "password", "password2"]

    def validate_telefono(self, value):
        if not value:
            return value
        limpio = "".join(c for c in value if c.isdigit() or c == "+")
        if limpio.startswith("00"):
            limpio = "+" + limpio[2:]
        if limpio.count("+") > 1 or ("+" in limpio and not limpio.startswith("+")):
            raise serializers.ValidationError("Ingresá un teléfono válido.")
        digitos = limpio[1:] if limpio.startswith("+") else limpio
        if not digitos.isdigit() or not 8 <= len(digitos) <= 20:
            raise serializers.ValidationError("Ingresá entre 8 y 20 dígitos.")
        return limpio

    def validate_password(self, value):
        # Reutiliza los AUTH_PASSWORD_VALIDATORS del settings (longitud,
        # similitud con datos del usuario, contraseñas comunes, etc.)
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        usuario = Usuario.objects.create_user(password=password, **validated_data)
        # Queda inactivo hasta verificar el código enviado por WhatsApp
        usuario.is_active = False
        usuario.estado = Usuario.Estado.INACTIVO
        usuario.email_verificado = False
        usuario.save(update_fields=["is_active", "estado", "email_verificado"])
        return usuario


class VerificarCodigoSerializer(serializers.Serializer):
    email = serializers.EmailField()
    codigo = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        try:
            usuario = Usuario.objects.get(email=attrs["email"])
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({"email": "No existe una cuenta con ese correo."})

        codigo_obj = (
            CodigoVerificacion.objects.filter(
                usuario=usuario, codigo=attrs["codigo"], tipo=CodigoVerificacion.Tipo.REGISTRO
            )
            .order_by("-creado")
            .first()
        )
        if not codigo_obj or not codigo_obj.valido:
            raise serializers.ValidationError({"codigo": "El código es inválido o expiró."})

        attrs["usuario"] = usuario
        attrs["codigo_obj"] = codigo_obj
        return attrs


class ReenviarCodigoSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not Usuario.objects.filter(email=value).exists():
            # No revelamos si el email existe o no (evita enumeración de usuarios)
            return value
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SolicitarRecuperacionSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ConfirmarRecuperacionSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    codigo = serializers.CharField(max_length=6, min_length=6, required=False)
    uid = serializers.CharField(required=False)
    token = serializers.CharField(required=False)
    password_nueva = serializers.CharField(write_only=True, min_length=8)
    password_nueva2 = serializers.CharField(write_only=True, min_length=8)

    def validate_password_nueva(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs["password_nueva"] != attrs["password_nueva2"]:
            raise serializers.ValidationError({"password_nueva2": "Las contraseñas no coinciden."})

        usuario = None
        codigo_obj = None
        if attrs.get("uid") and attrs.get("token"):
            try:
                usuario = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])))
            except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
                usuario = None
            if not usuario or not default_token_generator.check_token(usuario, attrs["token"]):
                raise serializers.ValidationError({"token": "El enlace es inválido o expiró."})
        elif attrs.get("email") and attrs.get("codigo"):
            usuario = Usuario.objects.filter(email=attrs["email"]).first()
            if not usuario:
                raise serializers.ValidationError({"codigo": "El código es inválido o expiró."})
            codigo_obj = (CodigoVerificacion.objects.filter(
                usuario=usuario, codigo=attrs["codigo"], tipo=CodigoVerificacion.Tipo.RECUPERACION
            ).order_by("-creado").first())
            if not codigo_obj or not codigo_obj.valido:
                raise serializers.ValidationError({"codigo": "El código es inválido o expiró."})
        else:
            raise serializers.ValidationError({"detail": "Usá el enlace recibido o ingresá email y código."})

        try:
            validate_password(attrs["password_nueva"], usuario)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password_nueva": list(exc.messages)})
        attrs["usuario"] = usuario
        attrs["codigo_obj"] = codigo_obj
        return attrs


class UsuarioPerfilSerializer(serializers.ModelSerializer):
    # Se redefine el campo para normalizar el formato antes de aplicar la validación.
    # El RegexValidator del modelo rechazaría espacios/guiones antes de validate_telefono.
    telefono = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Usuario
        fields = [
            "id_usuario", "nombre", "apellido", "email", "telefono",
            "documento", "direccion", "estado", "biometria_habilitada", "fecha_registro",
            "notificaciones_push_activas", "push_token",
        ]
        read_only_fields = [
            "id_usuario", "email", "documento", "estado", "biometria_habilitada",
            "fecha_registro", "notificaciones_push_activas", "push_token",
        ]

    def validate_nombre(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return value

    def validate_apellido(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("El apellido debe tener al menos 2 caracteres.")
        return value

    def validate_telefono(self, value):
        if not value:
            return value
        limpio = "".join(c for c in value if c.isdigit() or c == "+")
        if limpio.startswith("00"):
            limpio = "+" + limpio[2:]
        if limpio.count("+") > 1 or ("+" in limpio and not limpio.startswith("+")):
            raise serializers.ValidationError("Ingresá un teléfono válido.")
        digitos = limpio[1:] if limpio.startswith("+") else limpio
        if not digitos.isdigit() or not 8 <= len(digitos) <= 20:
            raise serializers.ValidationError("Ingresá entre 8 y 20 dígitos.")
        return limpio

    def validate_direccion(self, value):
        return value.strip() if value else value


class CambiarPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True, min_length=8)
    password_nueva2 = serializers.CharField(write_only=True, min_length=8)

    def validate_password_nueva(self, value):
        try:
            validate_password(value, self.context.get("request").user if self.context.get("request") else None)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        usuario = self.context["request"].user
        if not usuario.check_password(attrs["password_actual"]):
            raise serializers.ValidationError({"password_actual": "La contraseña actual es incorrecta."})
        if attrs["password_nueva"] != attrs["password_nueva2"]:
            raise serializers.ValidationError({"password_nueva2": "Las contraseñas nuevas no coinciden."})
        return attrs
