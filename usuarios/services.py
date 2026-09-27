from django.conf import settings
from django.utils import timezone

from creditos.models import BloqueoCuenta, IntentoAcceso


def bloqueo_activo(usuario):
    """Devuelve el BloqueoCuenta vigente del usuario, o None si no tiene."""
    return (
        BloqueoCuenta.objects.filter(id_usuario=usuario, fecha_fin__gt=timezone.now())
        .order_by("-fecha_inicio")
        .first()
    )


def registrar_intento(usuario, exito, ip, motivo_fallo=None):
    IntentoAcceso.objects.create(
        id_usuario=usuario,
        exito=exito,
        ip=ip,
        motivo_fallo=motivo_fallo,
    )


def evaluar_bloqueo_por_intentos(usuario):
    """
    Cuenta los intentos fallidos recientes del usuario y, si superan el
    máximo permitido, crea un BloqueoCuenta temporal (CU10).
    """
    ventana = timezone.now() - timezone.timedelta(minutes=settings.AUTH_VENTANA_INTENTOS_MIN)
    fallidos = IntentoAcceso.objects.filter(
        id_usuario=usuario, exito=False, fecha_intento__gte=ventana
    ).count()

    if fallidos >= settings.AUTH_MAX_INTENTOS_FALLIDOS:
        return BloqueoCuenta.objects.create(
            id_usuario=usuario,
            fecha_fin=timezone.now() + timezone.timedelta(minutes=settings.AUTH_BLOQUEO_MINUTOS),
            motivo=f"{fallidos} intentos de inicio de sesión fallidos",
        )
    return None
