from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Usuario


class PerfilSeguroTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="perfil@test.com",
            nombre="Facundo",
            apellido="Prueba",
            documento="30111222",
            password="ClaveSegura123",
            telefono="3415555555",
            direccion="Direccion inicial",
        )
        self.url = reverse("perfil")

    def test_perfil_requiere_autenticacion(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_puede_ver_su_propio_perfil(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["email"], self.usuario.email)
        self.assertEqual(respuesta.data["documento"], self.usuario.documento)

    def test_usuario_puede_actualizar_datos_permitidos(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.patch(self.url, {
            "nombre": "  Facu  ",
            "apellido": "Actualizado",
            "telefono": "+54 341 555 1234",
            "direccion": "  Calle Nueva 123  ",
        }, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, "Facu")
        self.assertEqual(self.usuario.telefono, "+543415551234")
        self.assertEqual(self.usuario.direccion, "Calle Nueva 123")

    def test_campos_sensibles_no_se_modifican_desde_perfil(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.patch(self.url, {
            "email": "intruso@test.com",
            "documento": "99999999",
            "estado": Usuario.Estado.BLOQUEADO,
            "is_staff": True,
            "push_token": "token-alterado",
            "biometria_habilitada": True,
        }, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "perfil@test.com")
        self.assertEqual(self.usuario.documento, "30111222")
        self.assertEqual(self.usuario.estado, Usuario.Estado.ACTIVO)
        self.assertFalse(self.usuario.is_staff)
        self.assertIsNone(self.usuario.push_token)
        self.assertFalse(self.usuario.biometria_habilitada)

    def test_telefono_invalido_es_rechazado(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.patch(self.url, {"telefono": "123"}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, "3415555555")

class ValidacionGlobalApiTests(APITestCase):
    def test_endpoint_inexistente_no_expone_informacion_interna(self):
        respuesta = self.client.get("/api/recurso-que-no-existe/", HTTP_ACCEPT="application/json")
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)
        contenido = respuesta.content.decode("utf-8").lower()
        self.assertNotIn("traceback", contenido)
        self.assertNotIn("settings", contenido)

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import CodigoVerificacion


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", BACKEND_PUBLIC_URL="http://testserver")
class RecuperacionYVerificacionEmailTests(APITestCase):
    def crear_usuario(self, email="seguridad@test.com", documento="40111222"):
        return Usuario.objects.create_user(email=email, nombre="Ana", apellido="Prueba", documento=documento, password="ClaveSegura123")

    def test_solicitud_recuperacion_no_revela_si_email_existe(self):
        url = reverse("password-recuperar")
        existente = self.client.post(url, {"email": "nadie@test.com"}, format="json")
        usuario = self.crear_usuario()
        real = self.client.post(url, {"email": usuario.email}, format="json")
        self.assertEqual(existente.status_code, 200)
        self.assertEqual(real.status_code, 200)
        self.assertEqual(existente.data["detail"], real.data["detail"])

    def test_email_recuperacion_incluye_enlace_seguro(self):
        usuario = self.crear_usuario()
        self.client.post(reverse("password-recuperar"), {"email": usuario.email}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/api/auth/password/enlace/", mail.outbox[0].body)

    def test_recuperacion_por_enlace_cambia_password_e_invalida_token(self):
        usuario = self.crear_usuario()
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        respuesta = self.client.post(reverse("password-confirmar"), {"uid": uid, "token": token, "password_nueva": "NuevaClave987!", "password_nueva2": "NuevaClave987!"}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("NuevaClave987!"))
        repetido = self.client.post(reverse("password-confirmar"), {"uid": uid, "token": token, "password_nueva": "OtraClave987!", "password_nueva2": "OtraClave987!"}, format="json")
        self.assertEqual(repetido.status_code, 400)

    def test_codigo_recuperacion_sigue_funcionando_y_es_un_solo_uso(self):
        usuario = self.crear_usuario()
        codigo = CodigoVerificacion.generar(usuario, CodigoVerificacion.Tipo.RECUPERACION)
        payload = {"email": usuario.email, "codigo": codigo.codigo, "password_nueva": "NuevaClave987!", "password_nueva2": "NuevaClave987!"}
        self.assertEqual(self.client.post(reverse("password-confirmar"), payload, format="json").status_code, 200)
        self.assertEqual(self.client.post(reverse("password-confirmar"), payload, format="json").status_code, 400)

    def test_registro_marca_email_como_no_verificado(self):
        payload = {"nombre":"Ana", "apellido":"Prueba", "email":"nuevo@test.com", "documento":"40999888", "password":"ClaveSegura123!", "password2":"ClaveSegura123!"}
        respuesta = self.client.post(reverse("registro-api"), payload, format="json")
        self.assertEqual(respuesta.status_code, 201)
        usuario = Usuario.objects.get(email="nuevo@test.com")
        self.assertFalse(usuario.email_verificado)
        self.assertFalse(usuario.is_active)

    def test_email_registro_incluye_enlace_de_verificacion(self):
        payload = {"nombre":"Ana", "apellido":"Prueba", "email":"enlace@test.com", "documento":"40999889", "password":"ClaveSegura123!", "password2":"ClaveSegura123!"}
        self.client.post(reverse("registro-api"), payload, format="json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/api/auth/verificar/enlace/", mail.outbox[0].body)

    def test_verificacion_por_enlace_activa_cuenta(self):
        usuario = self.crear_usuario("pendiente@test.com", "40111223")
        usuario.is_active = False
        usuario.estado = Usuario.Estado.INACTIVO
        usuario.email_verificado = False
        usuario.save(update_fields=["is_active", "estado", "email_verificado"])
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        respuesta = self.client.get(reverse("verificar-email-enlace", kwargs={"uidb64": uid, "token": token}))
        self.assertEqual(respuesta.status_code, 302)
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.email_verificado)
        self.assertEqual(usuario.estado, Usuario.Estado.ACTIVO)

    def test_verificacion_por_codigo_actualiza_email_verificado(self):
        usuario = self.crear_usuario("codigo@test.com", "40111224")
        usuario.is_active = False
        usuario.estado = Usuario.Estado.INACTIVO
        usuario.email_verificado = False
        usuario.save(update_fields=["is_active", "estado", "email_verificado"])
        codigo = CodigoVerificacion.generar(usuario, CodigoVerificacion.Tipo.REGISTRO)
        respuesta = self.client.post(reverse("verificar-cuenta"), {"email": usuario.email, "codigo": codigo.codigo}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        usuario.refresh_from_db()
        self.assertTrue(usuario.email_verificado)
