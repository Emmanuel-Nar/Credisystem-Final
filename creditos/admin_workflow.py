from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Credito, Notificacion, SolicitudCredito, Transaccion
from .notificaciones import notificar
from .services import crear_cuotas_para_credito


@transaction.atomic
def procesar_estado_solicitud(solicitud, estado_anterior=None):
    solicitud = SolicitudCredito.objects.select_for_update().get(pk=solicitud.pk)

    if solicitud.estado == SolicitudCredito.Estado.RECHAZADA:
        if not (solicitud.motivo_rechazo or "").strip():
            raise ValueError("Debe indicar el motivo de rechazo.")
        if estado_anterior != solicitud.estado:
            notificar(
                solicitud.id_usuario,
                Notificacion.Tipo.ESTADO_SOLICITUD,
                f"Tu solicitud #{solicitud.id_solicitud} fue rechazada. Motivo: {solicitud.motivo_rechazo}",
            )
        return None

    if solicitud.motivo_rechazo:
        solicitud.motivo_rechazo = None
        solicitud.save(update_fields=["motivo_rechazo"])

    if solicitud.estado == SolicitudCredito.Estado.APROBADA:
        hoy = timezone.now().date()
        credito, creado = Credito.objects.get_or_create(
            solicitud=solicitud,
            defaults={
                "id_usuario": solicitud.id_usuario,
                "monto_original": solicitud.monto_solicitado,
                "saldo_pendiente": solicitud.monto_solicitado,
                "tasa_interes_anual": Decimal(settings.CREDITO_TASA_INTERES_ANUAL),
                "plazo_meses": solicitud.plazo_meses,
                "fecha_otorgamiento": hoy,
                "primer_vencimiento": hoy + timedelta(days=30),
                "estado": Credito.Estado.ACTIVO,
            },
        )
        if creado:
            crear_cuotas_para_credito(credito)
            Transaccion.objects.create(
                id_usuario=solicitud.id_usuario,
                tipo=Transaccion.Tipo.DESEMBOLSO,
                descripcion=f"Desembolso del crédito #{credito.id_credito} por solicitud #{solicitud.id_solicitud}",
                importe=credito.monto_original,
            )
            notificar(
                solicitud.id_usuario,
                Notificacion.Tipo.ESTADO_SOLICITUD,
                f"Tu solicitud #{solicitud.id_solicitud} fue aprobada. Se otorgó el crédito #{credito.id_credito}.",
            )
        elif estado_anterior != solicitud.estado:
            notificar(
                solicitud.id_usuario,
                Notificacion.Tipo.ESTADO_SOLICITUD,
                f"Tu solicitud #{solicitud.id_solicitud} fue aprobada.",
            )
        return credito

    if estado_anterior != solicitud.estado:
        notificar(
            solicitud.id_usuario,
            Notificacion.Tipo.ESTADO_SOLICITUD,
            f"Tu solicitud #{solicitud.id_solicitud} quedó en revisión.",
        )
    return None
