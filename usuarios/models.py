import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    """
    Manager personalizado: Django hashea la contraseña automáticamente
    con create_user()/set_password() (PBKDF2 por defecto). Nunca se
    guarda en texto plano ni se debe asignar directo al campo password.
    """

    def create_user(self, email, nombre, apellido, documento, password=None, **extra_fields):
        if not email:
            raise ValueError("El usuario debe tener un email")
        if not documento:
            raise ValueError("El usuario debe tener un documento")

        email = self.normalize_email(email)
        usuario = self.model(
            email=email,
            nombre=nombre,
            apellido=apellido,
            documento=documento,
            **extra_fields,
        )
        usuario.set_password(password)  # hash seguro, nunca texto plano
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, nombre, apellido, documento, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("estado", Usuario.Estado.ACTIVO)
        return self.create_user(email, nombre, apellido, documento, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Tabla Usuario del diccionario de datos.
    hash_password se resuelve con el campo `password` heredado de
    AbstractBaseUser (Django lo hashea internamente, nunca en claro).
    """

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"
        BLOQUEADO = "bloqueado", "Bloqueado"

    telefono_validator = RegexValidator(
        regex=r"^\+?[0-9]{8,20}$",
        message="Ingresá un número de teléfono válido (solo dígitos, opcionalmente con +).",
    )

    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(
        max_length=30, blank=True, null=True, validators=[telefono_validator]
    )
    documento = models.CharField(max_length=20, unique=True)  # DNI/CUIT
    direccion = models.CharField(max_length=200, blank=True, null=True)
    # password (hash) lo maneja AbstractBaseUser -> campo `password`
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.ACTIVO
    )
    biometria_habilitada = models.BooleanField(default=False)
    email_verificado = models.BooleanField(default=True)

    # No estaban en el diccionario de datos original: hacen falta para
    # el CU7 (notificaciones push) - saber si el usuario las activó y a
    # qué dispositivo (token de Firebase Cloud Messaging) mandarlas.
    notificaciones_push_activas = models.BooleanField(default=True)
    push_token = models.CharField(max_length=255, blank=True, null=True)

    # Requeridos por Django admin / permisos
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "apellido", "documento"]

    class Meta:
        db_table = "usuario"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["documento"]),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.email})"

    @property
    def esta_bloqueado(self):
        return self.estado == self.Estado.BLOQUEADO


class CodigoVerificacion(models.Model):
    """
    Códigos de un solo uso para verificar el registro (CU1) o
    autorizar la recuperación de contraseña (CU9). Se envían por
    correo/SMS/WhatsApp y expiran a los pocos minutos.
    """

    class Tipo(models.TextChoices):
        REGISTRO = "registro", "Verificación de registro"
        RECUPERACION = "recuperacion", "Recuperación de contraseña"

    id_codigo = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codigos_verificacion"
    )
    codigo = models.CharField(max_length=6)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    creado = models.DateTimeField(auto_now_add=True)
    expira = models.DateTimeField()
    usado = models.BooleanField(default=False)

    class Meta:
        db_table = "codigo_verificacion"
        indexes = [models.Index(fields=["usuario", "tipo", "usado"])]

    def __str__(self):
        return f"Código {self.tipo} - {self.usuario_id}"

    @staticmethod
    def generar(usuario, tipo, minutos_expiracion=10):
        codigo = f"{random.randint(0, 999999):06d}"
        return CodigoVerificacion.objects.create(
            usuario=usuario,
            codigo=codigo,
            tipo=tipo,
            expira=timezone.now() + timedelta(minutes=minutos_expiracion),
        )

    @property
    def vencido(self):
        return timezone.now() > self.expira

    @property
    def valido(self):
        return not self.usado and not self.vencido
