"""Pruebas con respuestas controladas; nunca consultan CUIL reales."""
import copy
import tempfile
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from usuarios.models import Usuario
from .bcra import consultar_bcra, evaluar_bcra, normalizar_cuil_cuit
from .models import Credito, Notificacion, SolicitudCredito, Transaccion


def numero_prueba(documento="30123456", prefijo="20"):
    base = prefijo + documento
    verificador = (11 - sum(int(d) * p for d, p in zip(base, [5, 4, 3, 2, 7, 6, 5, 4, 3, 2])) % 11) % 11
    if verificador == 10:
        return numero_prueba(documento, "23" if prefijo == "20" else "33")
    return base + str(verificador)


def respuesta_bcra(numero=None, situacion=1):
    return {"status": 200, "results": {
        "identificacion": int(numero or numero_prueba()), "denominacion": "DATOS PRIVADOS DE PRUEBA",
        "periodos": [{"periodo": timezone.localdate().strftime("%Y%m"), "entidades": [{
            "entidad": "BANCO PRIVADO DE PRUEBA", "situacion": situacion, "monto": 120.5,
            "diasAtrasoPago": 0, "refinanciaciones": False, "recategorizacionOblig": False,
            "situacionJuridica": False, "irrecDisposicionTecnica": False,
            "enRevision": False, "procesoJud": False,
        }]}],
    }}


class ConsultaBCRATests(SimpleTestCase):
    def setUp(self):
        self.get = patch("creditos.bcra.requests.get").start()
        self.addCleanup(patch.stopall)
        self.datos = respuesta_bcra()
        self.get.return_value = Mock(status_code=200)
        self.get.return_value.json.return_value = self.datos

    def test_normaliza_cuil_con_guiones(self):
        n = numero_prueba()
        self.assertEqual(normalizar_cuil_cuit(f"{n[:2]}-{n[2:10]}-{n[-1]}"), n)

    def test_rechaza_formatos_digito_y_prefijo_invalidos(self):
        for numero in ["", "123", "abcdefghijk", "00000000000", numero_prueba()[:-1] + str((int(numero_prueba()[-1]) + 1) % 10), "٢٠٣٠١٢٣٤٥٦٧", "20 30123456 1"]:
            with self.subTest(numero=numero), self.assertRaises(ValidationError):
                normalizar_cuil_cuit(numero)

    def test_tls_timeout_conversion_y_situacion_normal(self):
        estado, informe = evaluar_bcra(numero_prueba())
        self.assertEqual(estado, "aprobada")
        self.assertEqual(Decimal(informe["entidades"][0]["monto_pesos"]), Decimal("120500"))
        opciones = self.get.call_args.kwargs
        self.assertIs(opciones["verify"], True)
        self.assertFalse(opciones["allow_redirects"])
        self.assertEqual(opciones["timeout"], (3.05, 8))

    def test_fallos_red_no_fabrican_informacion(self):
        for error in [requests.Timeout(), requests.ConnectionError(), requests.exceptions.SSLError()]:
            self.get.side_effect = error
            estado, informe = evaluar_bcra(numero_prueba())
            self.assertEqual(estado, "en_revision")
            self.assertEqual(informe["estado"], "no_disponible")
            self.assertNotIn("entidades", informe)

    def test_error_http_y_redireccion_no_aprueban(self):
        for codigo in [301, 400, 429, 500, 503]:
            self.get.return_value.status_code = codigo
            self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_404_no_se_confunde_con_buen_historial(self):
        self.get.return_value.status_code = 404
        self.get.return_value.json.return_value = {"status":404,"errorMessages":["Sin datos"]}
        estado, informe = evaluar_bcra(numero_prueba())
        self.assertEqual(estado, "en_revision")
        self.assertEqual(informe["estado"], "sin_datos")

    def test_json_invalido(self):
        self.get.return_value.json.side_effect = ValueError("HTML")
        self.assertEqual(consultar_bcra(numero_prueba())["estado"], "no_disponible")

    def test_respuestas_incompletas_o_inconsistentes(self):
        variantes = [[], {}, {"status": 200, "results": None}]
        for campo, valor in [("identificacion", 1), ("periodos", None)]:
            d = copy.deepcopy(self.datos)
            d["results"][campo] = valor
            variantes.append(d)
        for campo, valor in [("situacion", True), ("situacion", "1"), ("situacion", 99), ("monto", "NaN"), ("monto", -1), ("enRevision", "false"), ("diasAtrasoPago", None)]:
            d = copy.deepcopy(self.datos)
            d["results"]["periodos"][0]["entidades"][0][campo] = valor
            variantes.append(d)
        d = copy.deepcopy(self.datos)
        del d["results"]["periodos"][0]["entidades"][0]["procesoJud"]
        variantes.append(d)
        for datos in variantes:
            with self.subTest(datos=datos):
                self.get.return_value.json.return_value = datos
                self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_situaciones_no_normales_requieren_revision(self):
        for situacion in [2, 3, 4, 5, 6]:
            self.get.return_value.json.return_value = respuesta_bcra(situacion=situacion)
            self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_observaciones_y_atrasos_requieren_revision(self):
        for campo in ["refinanciaciones", "recategorizacionOblig", "situacionJuridica", "irrecDisposicionTecnica", "enRevision", "procesoJud", "diasAtrasoPago"]:
            datos = copy.deepcopy(self.datos)
            datos["results"]["periodos"][0]["entidades"][0][campo] = 1 if campo == "diasAtrasoPago" else True
            self.get.return_value.json.return_value = datos
            self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_periodo_antiguo_o_futuro_no_aprueba(self):
        for periodo in ["200001", "209912", "202613"]:
            self.datos["results"]["periodos"][0]["periodo"] = periodo
            self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_elige_periodo_mas_reciente(self):
        antiguo = copy.deepcopy(self.datos["results"]["periodos"][0])
        antiguo["periodo"] = "200001"
        antiguo["entidades"][0]["situacion"] = 5
        self.datos["results"]["periodos"].insert(0, antiguo)
        self.assertEqual(evaluar_bcra(numero_prueba())[0], "aprobada")

    def test_sin_periodos_o_entidades_requiere_revision(self):
        self.datos["results"]["periodos"][0]["entidades"] = []
        self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")
        self.datos["results"]["periodos"] = []
        self.assertEqual(evaluar_bcra(numero_prueba())[0], "en_revision")

    def test_empresa_requiere_validar_titularidad(self):
        numero = numero_prueba(prefijo="30")
        self.get.return_value.json.return_value = respuesta_bcra(numero)
        estado, informe = evaluar_bcra(numero)
        self.assertEqual(estado, "en_revision")
        self.assertEqual(informe["decision"], "revision_titularidad_empresa")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SolicitudBCRATests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.tmp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.usuario = Usuario.objects.create_user(email="bcra@example.test", nombre="Prueba", apellido="Cliente", documento="30123456", password="PruebaSegura123", is_active=True)
        self.client.force_authenticate(self.usuario)
        self.get = patch("creditos.bcra.requests.get").start()
        self.addCleanup(patch.stopall)
        self.get.return_value = Mock(status_code=200)
        self.get.return_value.json.return_value = respuesta_bcra()
        self.url = reverse("solicitudes-credito")
        self.id_envio = str(uuid4())

    def datos(self, **cambios):
        datos = {"monto_solicitado":"100000", "plazo_meses":12, "ingresos_mensuales":"800000", "cuil_cuit":numero_prueba(), "autorizacion_consulta":"true", "id_envio":self.id_envio, "comprobante":SimpleUploadedFile("ingresos.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")}
        datos.update(cambios)
        return datos

    def enviar(self, **cambios):
        return self.client.post(self.url, self.datos(**cambios), format="multipart")

    def test_aprobacion_crea_credito_cuotas_notificacion_e_informe_privado(self):
        r = self.enviar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "aprobada")
        credito = Credito.objects.get()
        self.assertEqual(credito.cuotas.count(), 12)
        self.assertEqual(Notificacion.objects.count(), 1)
        s = SolicitudCredito.objects.get()
        self.assertTrue(s.autorizacion_consulta)
        self.assertEqual(s.bcra_estado, "consultado")
        self.assertEqual(s.cuil_cuit, numero_prueba())
        self.assertIsNotNone(s.bcra_fecha)
        self.assertNotIn("bcra_informe", r.data)
        self.assertNotIn("cuil_cuit", r.data)
        self.assertNotIn("BANCO PRIVADO", r.content.decode())

    def test_informacion_privada_ausente_en_lista_detalle_y_notificaciones(self):
        r = self.enviar()
        for url in [self.url, reverse("solicitud-detalle", args=[r.data["id_solicitud"]]), "/api/notificaciones/"]:
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            for privado in ["bcra_informe", "bcra_estado", "peor_situacion", "BANCO PRIVADO", numero_prueba()]:
                self.assertNotIn(privado, respuesta.content.decode())

    def test_reintentar_mismo_envio_no_duplica_efectos(self):
        uno = self.enviar()
        dos = self.enviar()
        self.assertEqual(uno.data, dos.data)
        self.assertEqual(dos.status_code, 200)
        self.assertEqual(Credito.objects.count(), 1)
        self.assertEqual(SolicitudCredito.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertEqual(Transaccion.objects.count(), 2)
        self.get.assert_called_once()

    def test_caida_bcra_guarda_revision_sin_credito(self):
        self.get.side_effect = requests.Timeout()
        r = self.enviar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["estado"], "en_revision")
        self.assertEqual(SolicitudCredito.objects.get().bcra_estado, "no_disponible")
        self.assertFalse(Credito.objects.exists())

    def test_observaciones_guardan_revision_sin_credito(self):
        self.get.return_value.json.return_value = respuesta_bcra(situacion=3)
        r = self.enviar()
        self.assertEqual(r.data["estado"], "en_revision")
        self.assertFalse(Credito.objects.exists())

    def test_ingresos_insuficientes_rechazan_sin_consulta(self):
        r = self.enviar(ingresos_mensuales="100")
        self.assertEqual(r.data["estado"], "rechazada")
        self.get.assert_not_called()
        self.assertFalse(Credito.objects.exists())

    def test_cuil_ajeno_no_consulta_ni_guarda(self):
        r = self.enviar(cuil_cuit=numero_prueba("30123457"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("cuil_cuit", r.data)
        self.get.assert_not_called()
        self.assertFalse(SolicitudCredito.objects.exists())

    def test_validaciones_obligatorias_en_backend(self):
        for cambios in [{"cuil_cuit":""}, {"cuil_cuit":"12345678901"}, {"autorizacion_consulta":"false"}, {"id_envio":"no-uuid"}, {"plazo_meses":0}, {"ingresos_mensuales":"NaN"}]:
            with self.subTest(cambios=cambios):
                self.assertEqual(self.enviar(**cambios).status_code, 400)
        self.get.assert_not_called()
        self.assertFalse(SolicitudCredito.objects.exists())

    def test_archivo_invalido_no_consulta(self):
        self.assertEqual(self.enviar(comprobante=SimpleUploadedFile("recibo.pdf", b"malicioso")).status_code, 400)
        self.get.assert_not_called()

    def test_cliente_no_puede_forzar_aprobacion_ni_informe(self):
        self.get.side_effect = requests.Timeout()
        r = self.enviar(estado="aprobada", bcra_estado="consultado", bcra_informe='{"motivo":"normal"}')
        self.assertEqual(r.data["estado"], "en_revision")
        self.assertFalse(Credito.objects.exists())

    def test_no_hay_consulta_publica_y_solicitud_exige_login(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.enviar().status_code, 401)
        self.assertEqual(self.client.get("/evaluacion-crediticia/").status_code, 404)
        self.assertEqual(self.client.post("/api/creditos/evaluacion-crediticia/", {}).status_code, 404)
        self.get.assert_not_called()

    def test_otra_cuenta_no_ve_solicitud(self):
        r = self.enviar()
        otro = Usuario.objects.create_user(email="otro@example.test", nombre="Otro", apellido="Cliente", documento="30123457", password="PruebaSegura123")
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get(reverse("solicitud-detalle", args=[r.data["id_solicitud"]])).status_code, 404)

    def test_fallo_transaccion_revierte_credito_y_archivo(self):
        from pathlib import Path
        with patch("creditos.views.procesar_estado_solicitud", side_effect=RuntimeError("fallo controlado")):
            with self.assertLogs("credisystem.errors", level="ERROR"):
                self.assertEqual(self.enviar().status_code, 500)
        self.assertFalse(SolicitudCredito.objects.exists())
        self.assertFalse(Transaccion.objects.exists())
        self.assertEqual(list(Path(self.tmp.name).rglob("*.pdf")), [])

    def test_solo_superusuario_ve_informe_en_admin(self):
        r = self.enviar()
        url = reverse("admin:creditos_solicitudcredito_change", args=[r.data["id_solicitud"]])
        operador = Usuario.objects.create_user(email="operador@example.test", nombre="Operador", apellido="Prueba", documento="30123458", password="PruebaSegura123", is_staff=True, is_active=True)
        operador.user_permissions.add(Permission.objects.get(codename="change_solicitudcredito"))
        self.client.force_authenticate(user=None)
        self.client.force_login(operador)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "BANCO PRIVADO")
        self.assertNotContains(respuesta, numero_prueba())
        operador.is_superuser = True
        operador.save()
        respuesta = self.client.get(url)
        self.assertContains(respuesta, "BANCO PRIVADO")
        self.assertContains(respuesta, numero_prueba())
