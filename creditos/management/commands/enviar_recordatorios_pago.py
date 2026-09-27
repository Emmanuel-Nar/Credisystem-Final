from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from creditos.models import Credito, Cuota, Notificacion
from creditos.notificaciones import notificar


class Command(BaseCommand):
    help = "Genera recordatorios de cuotas próximas a vencer y vencidas."
    DIAS_ANTICIPACION = 3

    def _ya_notificada_hoy(self, usuario, marcador, hoy):
        return Notificacion.objects.filter(
            id_usuario=usuario,
            tipo=Notificacion.Tipo.VENCIMIENTO,
            fecha_envio__date=hoy,
            mensaje__contains=marcador,
        ).exists()

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        fecha_objetivo = hoy + timedelta(days=self.DIAS_ANTICIPACION)
        creadas = 0

        cuotas = Cuota.objects.filter(
            credito__estado__in=[Credito.Estado.ACTIVO, Credito.Estado.EN_MORA],
            estado__in=[Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDA],
            fecha_vencimiento__lte=fecha_objetivo,
        ).select_related("credito", "credito__id_usuario")

        for cuota in cuotas:
            credito = cuota.credito
            usuario = credito.id_usuario
            marcador = f"cuota #{cuota.numero} del crédito #{credito.id_credito}"

            if cuota.fecha_vencimiento < hoy:
                if cuota.estado != Cuota.Estado.VENCIDA:
                    cuota.estado = Cuota.Estado.VENCIDA
                    cuota.save(update_fields=["estado"])
                if credito.estado != Credito.Estado.EN_MORA:
                    credito.estado = Credito.Estado.EN_MORA
                    credito.save(update_fields=["estado"])
                if self._ya_notificada_hoy(usuario, marcador, hoy):
                    continue
                dias = (hoy - cuota.fecha_vencimiento).days
                mensaje = (
                    f"La {marcador} está vencida desde {cuota.fecha_vencimiento} "
                    f"({dias} día{'s' if dias != 1 else ''} de atraso)."
                )
            elif cuota.fecha_vencimiento == fecha_objetivo:
                if self._ya_notificada_hoy(usuario, marcador, hoy):
                    continue
                mensaje = (
                    f"Tu {marcador} vence en {self.DIAS_ANTICIPACION} días "
                    f"({cuota.fecha_vencimiento})."
                )
            else:
                continue

            notificar(usuario, Notificacion.Tipo.VENCIMIENTO, mensaje)
            creadas += 1

        # Compatibilidad con créditos antiguos que todavía no tienen cronograma de cuotas.
        creditos_sin_cuotas = Credito.objects.filter(
            estado=Credito.Estado.ACTIVO,
            primer_vencimiento=fecha_objetivo,
            cuotas__isnull=True,
        ).select_related("id_usuario")
        for credito in creditos_sin_cuotas:
            marcador = f"crédito #{credito.id_credito}"
            if self._ya_notificada_hoy(credito.id_usuario, marcador, hoy):
                continue
            mensaje = (
                f"Tu cuota del {marcador} vence en {self.DIAS_ANTICIPACION} días "
                f"({credito.primer_vencimiento})."
            )
            notificar(credito.id_usuario, Notificacion.Tipo.VENCIMIENTO, mensaje)
            creadas += 1

        self.stdout.write(self.style.SUCCESS(f"Recordatorios generados: {creadas}"))
