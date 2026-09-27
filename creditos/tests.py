from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from usuarios.models import Usuario

from .models import Credito, HistorialSolicitud, Notificacion, Pago, SolicitudCredito, Transaccion


class PagoMercadoPagoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="cliente@test.com",
            nombre="Cliente",
            apellido="Prueba",
            documento="30123123",
            password="ClaveSegura123",
        )
        self.usuario.is_active = True
        self.usuario.estado = Usuario.Estado.ACTIVO
        self.usuario.save()

        self.credito = Credito.objects.create(
            id_usuario=self.usuario,
            monto_original=Decimal("50000"),
            saldo_pendiente=Decimal("50000"),
            tasa_interes_anual=Decimal("85.00"),
            plazo_meses=12,
            fecha_otorgamiento=date.today(),
            primer_vencimiento=date.today() + timedelta(days=30),
            estado=Credito.Estado.ACTIVO,
        )

        self.client.force_authenticate(user=self.usuario)

    @patch("creditos.mercadopago_service.crear_preferencia_pago")
    def test_iniciar_pago_crea_preferencia_pendiente(self, mock_crear):
        mock_crear.return_value = ("pref-123", "https://www.mercadopago.com/checkout/pref-123")

        url = reverse("iniciar-pago", args=[self.credito.id_credito])
        respuesta = self.client.post(url, {"monto": "10000"})

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["estado"], "pendiente")
        self.assertIn("init_point", respuesta.data)

        pago = Pago.objects.get(id_pago=respuesta.data["id_pago"])
        self.assertEqual(pago.resultado, Pago.Resultado.PENDIENTE)
        self.assertEqual(pago.mp_preference_id, "pref-123")

    @patch("creditos.mercadopago_service.crear_preferencia_pago")
    def test_no_permite_pagar_mas_del_saldo_pendiente(self, mock_crear):
        url = reverse("iniciar-pago", args=[self.credito.id_credito])
        respuesta = self.client.post(url, {"monto": "999999"})

        self.assertEqual(respuesta.status_code, 400)
        mock_crear.assert_not_called()

    def test_no_puede_iniciar_pago_de_credito_ajeno(self):
        otro_usuario = Usuario.objects.create_user(
            email="otro@test.com", nombre="Otro", apellido="Usuario",
            documento="30999111", password="ClaveSegura123",
        )
        self.client.force_authenticate(user=otro_usuario)

        url = reverse("iniciar-pago", args=[self.credito.id_credito])
        respuesta = self.client.post(url, {"monto": "10000"})

        self.assertEqual(respuesta.status_code, 404)

    @patch("creditos.mercadopago_service.obtener_pago_mp")
    @patch("creditos.mercadopago_service.validar_firma_webhook", return_value=True)
    def test_webhook_aprobado_actualiza_saldo_y_notifica(self, mock_firma, mock_obtener):
        pago = Pago.objects.create(
            id_credito=self.credito,
            monto_pagado=Decimal("10000"),
            resultado=Pago.Resultado.PENDIENTE,
            external_reference="pago-abc123",
        )
        mock_obtener.return_value = {
            "status": "approved",
            "external_reference": "pago-abc123",
            "payment_type_id": "credit_card",
            "transaction_details": {"external_resource_url": "https://mp.example/comprobante.pdf"},
        }

        url = reverse("webhook-mercadopago")
        respuesta = self.client.post(
            url, {"type": "payment", "data": {"id": "999888777"}}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)

        pago.refresh_from_db()
        self.credito.refresh_from_db()

        self.assertEqual(pago.resultado, Pago.Resultado.APROBADO)
        self.assertEqual(pago.medio_pago, "credito")
        self.assertEqual(self.credito.saldo_pendiente, Decimal("40000"))
        self.assertTrue(Transaccion.objects.filter(id_usuario=self.usuario, tipo="pago").exists())
        self.assertTrue(Notificacion.objects.filter(id_usuario=self.usuario).exists())

    @patch("creditos.mercadopago_service.obtener_pago_mp")
    @patch("creditos.mercadopago_service.validar_firma_webhook", return_value=True)
    def test_webhook_rechazado_no_toca_el_saldo(self, mock_firma, mock_obtener):
        pago = Pago.objects.create(
            id_credito=self.credito,
            monto_pagado=Decimal("10000"),
            resultado=Pago.Resultado.PENDIENTE,
            external_reference="pago-def456",
        )
        mock_obtener.return_value = {
            "status": "rejected",
            "external_reference": "pago-def456",
            "payment_type_id": "credit_card",
        }

        url = reverse("webhook-mercadopago")
        self.client.post(url, {"type": "payment", "data": {"id": "111222333"}}, format="json")

        pago.refresh_from_db()
        self.credito.refresh_from_db()

        self.assertEqual(pago.resultado, Pago.Resultado.RECHAZADO)
        self.assertEqual(self.credito.saldo_pendiente, Decimal("50000"))

    @patch("creditos.mercadopago_service.validar_firma_webhook", return_value=False)
    def test_webhook_con_firma_invalida_se_rechaza(self, mock_firma):
        url = reverse("webhook-mercadopago")
        respuesta = self.client.post(
            url, {"type": "payment", "data": {"id": "1"}}, format="json"
        )
        self.assertEqual(respuesta.status_code, 401)

    @patch("creditos.mercadopago_service.obtener_pago_mp")
    @patch("creditos.mercadopago_service.validar_firma_webhook", return_value=True)
    def test_webhook_no_procesa_dos_veces_el_mismo_pago(self, mock_firma, mock_obtener):
        pago = Pago.objects.create(
            id_credito=self.credito,
            monto_pagado=Decimal("10000"),
            resultado=Pago.Resultado.APROBADO,  # ya procesado antes
            external_reference="pago-ya-procesado",
        )
        saldo_antes = self.credito.saldo_pendiente
        mock_obtener.return_value = {
            "status": "approved",
            "external_reference": "pago-ya-procesado",
            "payment_type_id": "credit_card",
        }

        url = reverse("webhook-mercadopago")
        self.client.post(url, {"type": "payment", "data": {"id": "1"}}, format="json")

        self.credito.refresh_from_db()
        # El webhook puede reconsultar el pago en Mercado Pago (es normal
        # recibir notificaciones duplicadas), pero no debe volver a
        # descontar el saldo de un pago que ya estaba aprobado.
        self.assertEqual(self.credito.saldo_pendiente, saldo_antes)


class NotificacionesTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="notif@test.com", nombre="Noti", apellido="Ficaciones",
            documento="30777666", password="ClaveSegura123",
        )
        self.usuario.is_active = True
        self.usuario.estado = Usuario.Estado.ACTIVO
        self.usuario.save()
        self.client.force_authenticate(user=self.usuario)

    def test_listar_notificaciones_propias(self):
        Notificacion.objects.create(id_usuario=self.usuario, tipo="vencimiento", mensaje="Msj 1")
        Notificacion.objects.create(id_usuario=self.usuario, tipo="promocion", mensaje="Msj 2", leida=True)

        respuesta = self.client.get(reverse("notificaciones"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 2)

    def test_filtrar_por_no_leidas(self):
        Notificacion.objects.create(id_usuario=self.usuario, tipo="vencimiento", mensaje="No leída")
        Notificacion.objects.create(id_usuario=self.usuario, tipo="promocion", mensaje="Leída", leida=True)

        respuesta = self.client.get(reverse("notificaciones") + "?leida=false")
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(respuesta.data["results"][0]["mensaje"], "No leída")

    def test_marcar_una_notificacion_como_leida(self):
        n = Notificacion.objects.create(id_usuario=self.usuario, tipo="vencimiento", mensaje="Hola")
        url = reverse("notificacion-leer", args=[n.id_notificacion])

        respuesta = self.client.patch(url)
        self.assertEqual(respuesta.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.leida)

    def test_no_puede_marcar_notificacion_ajena(self):
        otro = Usuario.objects.create_user(
            email="otro2@test.com", nombre="Otro", apellido="Mas",
            documento="30111000", password="ClaveSegura123",
        )
        n = Notificacion.objects.create(id_usuario=otro, tipo="vencimiento", mensaje="Ajena")
        url = reverse("notificacion-leer", args=[n.id_notificacion])

        respuesta = self.client.patch(url)
        self.assertEqual(respuesta.status_code, 404)

    def test_marcar_todas_como_leidas(self):
        Notificacion.objects.create(id_usuario=self.usuario, tipo="vencimiento", mensaje="A")
        Notificacion.objects.create(id_usuario=self.usuario, tipo="promocion", mensaje="B")

        respuesta = self.client.post(reverse("notificaciones-leer-todas"))
        self.assertEqual(respuesta.data["actualizadas"], 2)
        self.assertFalse(Notificacion.objects.filter(id_usuario=self.usuario, leida=False).exists())


class RecordatorioPagoCommandTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="recordatorio@test.com", nombre="Rec", apellido="Datorio",
            documento="30222333", password="ClaveSegura123",
        )

    def test_genera_recordatorio_para_credito_que_vence_en_3_dias(self):
        from django.core.management import call_command
        from django.utils import timezone

        Credito.objects.create(
            id_usuario=self.usuario,
            monto_original=Decimal("50000"),
            saldo_pendiente=Decimal("50000"),
            tasa_interes_anual=Decimal("85.00"),
            plazo_meses=12,
            fecha_otorgamiento=timezone.now().date(),
            primer_vencimiento=timezone.now().date() + timedelta(days=3),
            estado=Credito.Estado.ACTIVO,
        )

        call_command("enviar_recordatorios_pago")

        self.assertTrue(
            Notificacion.objects.filter(id_usuario=self.usuario, tipo="vencimiento").exists()
        )

    def test_no_duplica_recordatorio_si_ya_se_genero_hoy(self):
        from django.core.management import call_command
        from django.utils import timezone

        credito = Credito.objects.create(
            id_usuario=self.usuario,
            monto_original=Decimal("50000"),
            saldo_pendiente=Decimal("50000"),
            tasa_interes_anual=Decimal("85.00"),
            plazo_meses=12,
            fecha_otorgamiento=timezone.now().date(),
            primer_vencimiento=timezone.now().date() + timedelta(days=3),
            estado=Credito.Estado.ACTIVO,
        )

        call_command("enviar_recordatorios_pago")
        call_command("enviar_recordatorios_pago")

        self.assertEqual(
            Notificacion.objects.filter(
                id_usuario=self.usuario, tipo="vencimiento", mensaje__contains=f"crédito #{credito.id_credito}"
            ).count(),
            1,
        )


class GestionAdministrativaSolicitudesTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="adminflow@test.com", nombre="Admin", apellido="Flow",
            documento="30999111", password="ClaveSegura123",
        )

    def crear_solicitud(self, estado=SolicitudCredito.Estado.EN_REVISION, motivo=None):
        return SolicitudCredito.objects.create(
            id_usuario=self.usuario, monto_solicitado=Decimal("120000"),
            plazo_meses=12, ingresos_mensuales=Decimal("500000"),
            estado=estado, motivo_rechazo=motivo,
        )

    def test_aprobar_genera_un_solo_credito_y_desembolso(self):
        from creditos.admin_workflow import procesar_estado_solicitud
        solicitud = self.crear_solicitud()
        solicitud.estado = SolicitudCredito.Estado.APROBADA
        solicitud.save()
        procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.EN_REVISION)
        procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.APROBADA)
        self.assertEqual(Credito.objects.filter(solicitud=solicitud).count(), 1)
        self.assertEqual(Transaccion.objects.filter(tipo=Transaccion.Tipo.DESEMBOLSO).count(), 1)

    def test_rechazo_exige_motivo(self):
        from creditos.admin_workflow import procesar_estado_solicitud
        solicitud = self.crear_solicitud(SolicitudCredito.Estado.RECHAZADA)
        with self.assertRaises(ValueError):
            procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.EN_REVISION)

    def test_cambio_estado_notifica_cliente(self):
        from creditos.admin_workflow import procesar_estado_solicitud
        solicitud = self.crear_solicitud()
        solicitud.estado = SolicitudCredito.Estado.RECHAZADA
        solicitud.motivo_rechazo = "Documentación insuficiente"
        solicitud.save()
        procesar_estado_solicitud(solicitud, SolicitudCredito.Estado.EN_REVISION)
        self.assertTrue(Notificacion.objects.filter(
            id_usuario=self.usuario, tipo=Notificacion.Tipo.ESTADO_SOLICITUD,
            mensaje__contains="Documentación insuficiente",
        ).exists())


class AuditoriaSolicitudesTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            email="admin-auditoria@test.com",
            nombre="Admin",
            apellido="Auditoria",
            documento="30999888",
            password="ClaveSegura123",
        )
        self.cliente = Usuario.objects.create_user(
            email="cliente-auditoria@test.com",
            nombre="Cliente",
            apellido="Auditoria",
            documento="30999777",
            password="ClaveSegura123",
        )
        self.solicitud = SolicitudCredito.objects.create(
            id_usuario=self.cliente,
            monto_solicitado=Decimal("100000"),
            plazo_meses=12,
            ingresos_mensuales=Decimal("500000"),
            estado=SolicitudCredito.Estado.EN_REVISION,
        )

    def test_historial_guarda_administrador_estados_y_observacion(self):
        historial = HistorialSolicitud.objects.create(
            solicitud=self.solicitud,
            administrador=self.admin,
            estado_anterior=SolicitudCredito.Estado.EN_REVISION,
            estado_nuevo=SolicitudCredito.Estado.RECHAZADA,
            observacion="Ingresos insuficientes",
        )
        self.assertEqual(historial.administrador, self.admin)
        self.assertEqual(historial.estado_anterior, SolicitudCredito.Estado.EN_REVISION)
        self.assertEqual(historial.estado_nuevo, SolicitudCredito.Estado.RECHAZADA)
        self.assertEqual(historial.observacion, "Ingresos insuficientes")
        self.assertIsNotNone(historial.fecha_cambio)

    def test_historial_queda_relacionado_con_solicitud(self):
        HistorialSolicitud.objects.create(
            solicitud=self.solicitud,
            administrador=self.admin,
            estado_anterior=SolicitudCredito.Estado.EN_REVISION,
            estado_nuevo=SolicitudCredito.Estado.APROBADA,
        )
        self.assertEqual(self.solicitud.historial_administrativo.count(), 1)

    def test_eliminar_solicitud_elimina_su_historial(self):
        HistorialSolicitud.objects.create(
            solicitud=self.solicitud,
            administrador=self.admin,
            estado_anterior=SolicitudCredito.Estado.EN_REVISION,
            estado_nuevo=SolicitudCredito.Estado.RECHAZADA,
        )
        solicitud_id = self.solicitud.id_solicitud
        self.solicitud.delete()
        self.assertFalse(HistorialSolicitud.objects.filter(solicitud_id=solicitud_id).exists())

class SeguridadPanelAdministrativoTests(APITestCase):
    def setUp(self):
        from django.contrib.auth.models import Permission
        self.cliente = Usuario.objects.create_user(
            email="cliente-admin@test.com", nombre="Cliente", apellido="Normal",
            documento="30123450", password="ClaveSegura123",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            email="staff-limitado@test.com", nombre="Staff", apellido="Limitado",
            documento="30123451", password="ClaveSegura123", is_staff=True,
        )
        self.staff_analista = Usuario.objects.create_user(
            email="analista@test.com", nombre="Analista", apellido="Credito",
            documento="30123452", password="ClaveSegura123", is_staff=True,
        )
        permiso = Permission.objects.get(codename="change_solicitudcredito")
        self.staff_analista.user_permissions.add(permiso)
        self.solicitud = SolicitudCredito.objects.create(
            id_usuario=self.cliente, monto_solicitado=Decimal("100000"),
            plazo_meses=12, ingresos_mensuales=Decimal("500000"),
            estado=SolicitudCredito.Estado.EN_REVISION,
        )

    def test_cliente_normal_no_puede_entrar_al_admin(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("admin:index"))
        self.assertEqual(respuesta.status_code, 302)

    def test_staff_sin_permiso_no_puede_modificar_solicitud(self):
        self.client.force_login(self.staff_sin_permiso)
        url = reverse("admin:creditos_solicitudcredito_change", args=[self.solicitud.pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 403)

    def test_analista_con_permiso_puede_modificar_solicitud(self):
        self.client.force_login(self.staff_analista)
        url = reverse("admin:creditos_solicitudcredito_change", args=[self.solicitud.pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)

    def test_analista_no_puede_eliminar_solicitud(self):
        self.client.force_login(self.staff_analista)
        url = reverse("admin:creditos_solicitudcredito_delete", args=[self.solicitud.pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 403)

class CuotasVencimientosTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="cuotas@test.com", nombre="Cliente", apellido="Cuotas",
            documento="30123999", password="ClaveSegura123",
        )
        self.solicitud = SolicitudCredito.objects.create(
            id_usuario=self.usuario, monto_solicitado=Decimal("120000"), plazo_meses=6,
            ingresos_mensuales=Decimal("600000"), estado=SolicitudCredito.Estado.EN_REVISION,
        )

    def test_aprobacion_genera_una_cuota_por_mes(self):
        from .admin_workflow import procesar_estado_solicitud
        from .models import Cuota
        self.solicitud.estado = SolicitudCredito.Estado.APROBADA
        self.solicitud.save()
        credito = procesar_estado_solicitud(self.solicitud, SolicitudCredito.Estado.EN_REVISION)
        self.assertEqual(credito.cuotas.count(), 6)
        self.assertEqual(credito.cuotas.filter(estado=Cuota.Estado.PENDIENTE).count(), 6)

    def test_generacion_de_cuotas_es_idempotente(self):
        from .admin_workflow import procesar_estado_solicitud
        from .services import crear_cuotas_para_credito
        self.solicitud.estado = SolicitudCredito.Estado.APROBADA
        self.solicitud.save()
        credito = procesar_estado_solicitud(self.solicitud, SolicitudCredito.Estado.EN_REVISION)
        crear_cuotas_para_credito(credito)
        self.assertEqual(credito.cuotas.count(), 6)

    def test_vencimientos_son_mensuales_y_ordenados(self):
        from .admin_workflow import procesar_estado_solicitud
        self.solicitud.estado = SolicitudCredito.Estado.APROBADA
        self.solicitud.save()
        credito = procesar_estado_solicitud(self.solicitud, SolicitudCredito.Estado.EN_REVISION)
        fechas = list(credito.cuotas.values_list("fecha_vencimiento", flat=True))
        self.assertEqual(fechas, sorted(fechas))
        self.assertEqual(fechas[0], credito.primer_vencimiento)

    def test_detalle_credito_expone_cronograma_real(self):
        from .admin_workflow import procesar_estado_solicitud
        self.solicitud.estado = SolicitudCredito.Estado.APROBADA
        self.solicitud.save()
        credito = procesar_estado_solicitud(self.solicitud, SolicitudCredito.Estado.EN_REVISION)
        self.client.force_authenticate(user=self.usuario)
        respuesta = self.client.get(reverse("credito-detalle", args=[credito.id_credito]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data["cuotas"]), 6)
        self.assertEqual(respuesta.data["cuotas_pendientes"], 6)
        self.assertEqual(str(respuesta.data["proximo_vencimiento"]), str(credito.primer_vencimiento))


class RegistroPagosCuotasTests(APITestCase):
    def setUp(self):
        from .services import crear_cuotas_para_credito
        self.usuario = Usuario.objects.create_user(
            email="pagos-cuotas@test.com", nombre="Cliente", apellido="Pagos",
            documento="30123888", password="ClaveSegura123",
        )
        self.credito = Credito.objects.create(
            id_usuario=self.usuario,
            monto_original=Decimal("120000"), saldo_pendiente=Decimal("120000"),
            tasa_interes_anual=Decimal("0.00"), plazo_meses=3,
            fecha_otorgamiento=date.today(), primer_vencimiento=date.today() + timedelta(days=30),
            estado=Credito.Estado.ACTIVO,
        )
        crear_cuotas_para_credito(self.credito)

    def _pago(self, monto, referencia):
        return Pago.objects.create(
            id_credito=self.credito, monto_pagado=Decimal(monto),
            resultado=Pago.Resultado.PENDIENTE, external_reference=referencia,
        )

    def test_pago_aprobado_se_imputa_a_primera_cuota(self):
        from .models import Cuota, ImputacionPago
        from .services import procesar_pago_aprobado
        pago = self._pago("40000", "registro-1")
        procesar_pago_aprobado(pago)
        cuota = self.credito.cuotas.get(numero=1)
        self.assertEqual(cuota.estado, Cuota.Estado.PAGADA)
        self.assertEqual(cuota.monto_pagado, Decimal("40000.00"))
        self.assertTrue(ImputacionPago.objects.filter(pago=pago, cuota=cuota).exists())

    def test_pago_parcial_conserva_cuota_pendiente(self):
        from .models import Cuota
        from .services import procesar_pago_aprobado
        pago = self._pago("10000", "registro-2")
        procesar_pago_aprobado(pago)
        cuota = self.credito.cuotas.get(numero=1)
        self.assertEqual(cuota.estado, Cuota.Estado.PENDIENTE)
        self.assertEqual(cuota.monto_pagado, Decimal("10000.00"))

    def test_pago_puede_imputarse_a_mas_de_una_cuota(self):
        from .models import Cuota
        from .services import procesar_pago_aprobado
        pago = self._pago("80000", "registro-3")
        procesar_pago_aprobado(pago)
        self.assertEqual(self.credito.cuotas.filter(estado=Cuota.Estado.PAGADA).count(), 2)
        self.assertEqual(pago.imputaciones.count(), 2)

    def test_procesar_mismo_pago_dos_veces_no_duplica_efectos(self):
        from .services import procesar_pago_aprobado
        pago = self._pago("40000", "registro-4")
        procesar_pago_aprobado(pago)
        procesar_pago_aprobado(pago)
        self.credito.refresh_from_db()
        self.assertEqual(self.credito.saldo_pendiente, Decimal("80000.00"))
        self.assertEqual(pago.imputaciones.count(), 1)
        self.assertEqual(Transaccion.objects.filter(tipo=Transaccion.Tipo.PAGO, id_usuario=self.usuario).count(), 1)

class EstadoCuentaTests(APITestCase):
    def setUp(self):
        from .models import Cuota
        self.Cuota = Cuota
        self.usuario = Usuario.objects.create_user(
            email="estado-cuenta@test.com", nombre="Estado", apellido="Cuenta",
            documento="30123777", password="ClaveSegura123",
        )
        self.credito = Credito.objects.create(
            id_usuario=self.usuario, monto_original=Decimal("100000"),
            saldo_pendiente=Decimal("60000"), tasa_interes_anual=Decimal("85.00"),
            plazo_meses=2, fecha_otorgamiento=date.today(),
            primer_vencimiento=date.today() + timedelta(days=10), estado=Credito.Estado.ACTIVO,
        )
        Cuota.objects.create(
            credito=self.credito, numero=1, importe=Decimal("50000"),
            monto_pagado=Decimal("50000"), fecha_vencimiento=date.today() - timedelta(days=20),
            estado=Cuota.Estado.PAGADA,
        )
        Cuota.objects.create(
            credito=self.credito, numero=2, importe=Decimal("50000"),
            monto_pagado=Decimal("0"), fecha_vencimiento=date.today() + timedelta(days=10),
            estado=Cuota.Estado.PENDIENTE,
        )
        Pago.objects.create(
            id_credito=self.credito, monto_pagado=Decimal("40000"),
            resultado=Pago.Resultado.APROBADO,
        )
        self.client.force_authenticate(user=self.usuario)

    def test_estado_cuenta_resume_saldo_cuotas_y_pagos(self):
        respuesta = self.client.get(reverse("estado-cuenta"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Decimal(respuesta.data["saldo_total_pendiente"]), Decimal("60000.00"))
        self.assertEqual(respuesta.data["creditos_activos"], 1)
        self.assertEqual(respuesta.data["cuotas_pagadas"], 1)
        self.assertEqual(respuesta.data["cuotas_pendientes"], 1)
        self.assertEqual(Decimal(respuesta.data["total_pagado"]), Decimal("40000.00"))

    def test_estado_cuenta_muestra_proximo_vencimiento(self):
        respuesta = self.client.get(reverse("estado-cuenta"))
        self.assertEqual(str(respuesta.data["proximo_vencimiento"]), str(date.today() + timedelta(days=10)))

    def test_estado_cuenta_no_expone_datos_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro-estado@test.com", nombre="Otro", apellido="Cliente",
            documento="30123778", password="ClaveSegura123",
        )
        Credito.objects.create(
            id_usuario=otro, monto_original=Decimal("900000"), saldo_pendiente=Decimal("900000"),
            tasa_interes_anual=Decimal("85.00"), plazo_meses=12, fecha_otorgamiento=date.today(),
            primer_vencimiento=date.today() + timedelta(days=30), estado=Credito.Estado.ACTIVO,
        )
        respuesta = self.client.get(reverse("estado-cuenta"))
        self.assertEqual(len(respuesta.data["creditos"]), 1)
        self.assertEqual(Decimal(respuesta.data["saldo_total_pendiente"]), Decimal("60000.00"))

    def test_estado_cuenta_requiere_autenticacion(self):
        self.client.force_authenticate(user=None)
        respuesta = self.client.get(reverse("estado-cuenta"))
        self.assertIn(respuesta.status_code, (401, 403))

class ComprobantePagoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="comprobante@test.com", nombre="Cliente", apellido="Comprobante",
            documento="30123991", password="ClaveSegura123",
        )
        self.otro = Usuario.objects.create_user(
            email="otro-comprobante@test.com", nombre="Otro", apellido="Cliente",
            documento="30123992", password="ClaveSegura123",
        )
        self.credito = Credito.objects.create(
            id_usuario=self.usuario, monto_original=Decimal("100000"), saldo_pendiente=Decimal("60000"),
            tasa_interes_anual=Decimal("85.00"), plazo_meses=3, fecha_otorgamiento=date.today(),
            primer_vencimiento=date.today() + timedelta(days=30), estado=Credito.Estado.ACTIVO,
        )
        self.pago = Pago.objects.create(
            id_credito=self.credito, monto_pagado=Decimal("40000"),
            medio_pago=Pago.MedioPago.BILLETERA, resultado=Pago.Resultado.APROBADO,
            external_reference="COMP-001",
        )
        self.client.force_authenticate(user=self.usuario)

    def test_usuario_puede_ver_comprobante_de_pago_aprobado(self):
        respuesta = self.client.get(reverse("comprobante-pago", kwargs={"id_pago": self.pago.id_pago}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Comprobante de pago", respuesta.content.decode())
        self.assertIn("COMP-001", respuesta.content.decode())

    def test_usuario_no_puede_ver_comprobante_ajeno(self):
        self.client.force_authenticate(user=self.otro)
        respuesta = self.client.get(reverse("comprobante-pago", kwargs={"id_pago": self.pago.id_pago}))
        self.assertEqual(respuesta.status_code, 404)

    def test_pago_no_aprobado_no_emite_comprobante(self):
        self.pago.resultado = Pago.Resultado.PENDIENTE
        self.pago.save(update_fields=["resultado"])
        respuesta = self.client.get(reverse("comprobante-pago", kwargs={"id_pago": self.pago.id_pago}))
        self.assertEqual(respuesta.status_code, 409)

    def test_comprobante_requiere_autenticacion(self):
        self.client.force_authenticate(user=None)
        respuesta = self.client.get(reverse("comprobante-pago", kwargs={"id_pago": self.pago.id_pago}))
        self.assertIn(respuesta.status_code, (401, 403))

class RecordatoriosCuotasTests(APITestCase):
    def setUp(self):
        from django.utils import timezone
        from .models import Cuota
        self.Cuota = Cuota
        self.hoy = timezone.localdate()
        self.usuario = Usuario.objects.create_user(
            email="recordatorios-cuotas@test.com", nombre="Recordatorio", apellido="Cuotas",
            documento="30123999", password="ClaveSegura123",
        )
        self.credito = Credito.objects.create(
            id_usuario=self.usuario, monto_original=Decimal("90000"),
            saldo_pendiente=Decimal("90000"), tasa_interes_anual=Decimal("85.00"),
            plazo_meses=3, fecha_otorgamiento=self.hoy,
            primer_vencimiento=self.hoy + timedelta(days=3), estado=Credito.Estado.ACTIVO,
        )

    def test_avisa_cuota_que_vence_en_tres_dias(self):
        from django.core.management import call_command
        cuota = self.Cuota.objects.create(
            credito=self.credito, numero=1, importe=Decimal("30000"),
            fecha_vencimiento=self.hoy + timedelta(days=3),
        )
        call_command("enviar_recordatorios_pago")
        self.assertTrue(Notificacion.objects.filter(
            id_usuario=self.usuario, tipo=Notificacion.Tipo.VENCIMIENTO,
            mensaje__contains=f"cuota #{cuota.numero} del crédito #{self.credito.id_credito}",
        ).exists())

    def test_cuota_vencida_pasa_a_vencida_y_credito_a_mora(self):
        from django.core.management import call_command
        cuota = self.Cuota.objects.create(
            credito=self.credito, numero=1, importe=Decimal("30000"),
            fecha_vencimiento=self.hoy - timedelta(days=1),
        )
        call_command("enviar_recordatorios_pago")
        cuota.refresh_from_db()
        self.credito.refresh_from_db()
        self.assertEqual(cuota.estado, self.Cuota.Estado.VENCIDA)
        self.assertEqual(self.credito.estado, Credito.Estado.EN_MORA)

    def test_no_duplica_recordatorio_de_misma_cuota_en_el_dia(self):
        from django.core.management import call_command
        cuota = self.Cuota.objects.create(
            credito=self.credito, numero=1, importe=Decimal("30000"),
            fecha_vencimiento=self.hoy + timedelta(days=3),
        )
        call_command("enviar_recordatorios_pago")
        call_command("enviar_recordatorios_pago")
        self.assertEqual(Notificacion.objects.filter(
            id_usuario=self.usuario, tipo=Notificacion.Tipo.VENCIMIENTO,
            mensaje__contains=f"cuota #{cuota.numero} del crédito #{self.credito.id_credito}",
        ).count(), 1)

    def test_no_avisa_cuota_pagada(self):
        from django.core.management import call_command
        self.Cuota.objects.create(
            credito=self.credito, numero=1, importe=Decimal("30000"),
            fecha_vencimiento=self.hoy + timedelta(days=3), estado=self.Cuota.Estado.PAGADA,
            monto_pagado=Decimal("30000"),
        )
        call_command("enviar_recordatorios_pago")
        self.assertFalse(Notificacion.objects.filter(
            id_usuario=self.usuario, tipo=Notificacion.Tipo.VENCIMIENTO,
            mensaje__contains=f"crédito #{self.credito.id_credito}",
        ).exists())
