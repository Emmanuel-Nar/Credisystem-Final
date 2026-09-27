from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from usuarios.models import Usuario
from .admin_workflow import procesar_estado_solicitud
from .models import Credito, Cuota, Notificacion, Pago, SolicitudCredito, Transaccion
from .services import procesar_pago_aprobado


class FlujoIntegralCreditoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="integral@test.com",
            nombre="Cliente",
            apellido="Integral",
            documento="30999001",
            password="ClaveSegura123",
        )
        self.otro = Usuario.objects.create_user(
            email="integral-otro@test.com",
            nombre="Otro",
            apellido="Cliente",
            documento="30999002",
            password="ClaveSegura123",
        )

    def _solicitud(self, usuario=None):
        return SolicitudCredito.objects.create(
            id_usuario=usuario or self.usuario,
            monto_solicitado=Decimal("120000.00"),
            plazo_meses=6,
            ingresos_mensuales=Decimal("600000.00"),
            estado=SolicitudCredito.Estado.EN_REVISION,
        )

    def _aprobar(self, solicitud):
        solicitud.estado = SolicitudCredito.Estado.APROBADA
        solicitud.save(update_fields=["estado"])
        return procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.EN_REVISION)

    def test_flujo_aprobacion_credito_cuotas_pago_y_estado_cuenta(self):
        solicitud = self._solicitud()
        credito = self._aprobar(solicitud)

        self.assertEqual(credito.cuotas.count(), 6)
        self.assertEqual(Transaccion.objects.filter(id_usuario=self.usuario, tipo=Transaccion.Tipo.DESEMBOLSO).count(), 1)

        primera = credito.cuotas.get(numero=1)
        pago = Pago.objects.create(
            id_credito=credito,
            monto_pagado=primera.importe,
            resultado=Pago.Resultado.PENDIENTE,
            external_reference="integral-pago-1",
        )
        procesar_pago_aprobado(pago)

        primera.refresh_from_db()
        credito.refresh_from_db()
        self.assertEqual(primera.estado, Cuota.Estado.PAGADA)
        self.assertLess(credito.saldo_pendiente, credito.monto_original)

        self.client.force_authenticate(self.usuario)
        respuesta = self.client.get(reverse("estado-cuenta"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["cuotas_pagadas"], 1)
        self.assertEqual(Decimal(respuesta.data["total_pagado"]), pago.monto_pagado)

    def test_rechazo_con_motivo_no_genera_credito_y_notifica(self):
        solicitud = self._solicitud()
        solicitud.estado = SolicitudCredito.Estado.RECHAZADA
        solicitud.motivo_rechazo = "Ingresos insuficientes"
        solicitud.save(update_fields=["estado", "motivo_rechazo"])

        procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.EN_REVISION)

        self.assertFalse(Credito.objects.filter(solicitud=solicitud).exists())
        self.assertTrue(Notificacion.objects.filter(
            id_usuario=self.usuario,
            tipo=Notificacion.Tipo.ESTADO_SOLICITUD,
            mensaje__contains="Ingresos insuficientes",
        ).exists())

    def test_reprocesar_aprobacion_no_duplica_credito_cuotas_ni_desembolso(self):
        solicitud = self._solicitud()
        credito = self._aprobar(solicitud)
        procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.APROBADA)

        self.assertEqual(Credito.objects.filter(solicitud=solicitud).count(), 1)
        self.assertEqual(credito.cuotas.count(), 6)
        self.assertEqual(Transaccion.objects.filter(id_usuario=self.usuario, tipo=Transaccion.Tipo.DESEMBOLSO).count(), 1)

    def test_recordatorio_integrado_marca_mora_y_no_duplica_aviso(self):
        solicitud = self._solicitud()
        credito = self._aprobar(solicitud)
        cuota = credito.cuotas.get(numero=1)
        cuota.fecha_vencimiento = timezone.now().date() - timedelta(days=1)
        cuota.save(update_fields=["fecha_vencimiento"])

        call_command("enviar_recordatorios_pago")
        call_command("enviar_recordatorios_pago")

        cuota.refresh_from_db()
        credito.refresh_from_db()
        self.assertEqual(cuota.estado, Cuota.Estado.VENCIDA)
        self.assertEqual(credito.estado, Credito.Estado.EN_MORA)
        self.assertEqual(Notificacion.objects.filter(
            id_usuario=self.usuario,
            tipo=Notificacion.Tipo.VENCIMIENTO,
            mensaje__contains=f"crédito #{credito.id_credito}",
        ).count(), 1)

    def test_aislamiento_entre_clientes_en_detalle_y_estado_de_cuenta(self):
        credito_propio = self._aprobar(self._solicitud(self.usuario))
        credito_ajeno = self._aprobar(self._solicitud(self.otro))

        self.client.force_authenticate(self.usuario)
        detalle_ajeno = self.client.get(reverse("credito-detalle", args=[credito_ajeno.id_credito]))
        self.assertEqual(detalle_ajeno.status_code, 404)

        estado = self.client.get(reverse("estado-cuenta"))
        self.assertEqual(estado.status_code, 200)
        ids = {item["id_credito"] for item in estado.data["creditos"]}
        self.assertEqual(ids, {credito_propio.id_credito})
