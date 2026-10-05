import re

from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import Usuario


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LoginWebTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.password = 'ClaveDePrueba987!'
        self.admin = Usuario.objects.create_superuser(
            email='admin@prueba.com', nombre='Admin', apellido='Prueba',
            documento='50111222', password=self.password,
        )
        self.cliente = Usuario.objects.create_user(
            email='cliente@prueba.com', nombre='Cliente', apellido='Prueba',
            documento='50111223', password=self.password,
        )

    def login_web(self, usuario, password=None, extra=None):
        pagina = self.client.get('/login/')
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        return self.client.post(reverse('login-web'), {
            'email': usuario.email, 'password': password or self.password, **(extra or {}),
        }, format='json', HTTP_X_CSRFTOKEN=csrf)

    def test_superusuario_ingresa_al_admin_sin_segundo_login(self):
        respuesta = self.login_web(self.admin)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['admin_url'], reverse('admin:index'))
        self.assertNotIn('access', respuesta.data)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.admin.pk))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_cliente_recibe_jwt_sin_acceso_admin(self):
        respuesta = self.login_web(self.cliente)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('access', respuesta.data)
        self.assertNotIn('admin_url', respuesta.data)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_staff_sin_superusuario_no_obtiene_sesion_admin(self):
        self.cliente.is_staff = True
        self.cliente.save()
        respuesta = self.login_web(self.cliente)
        self.assertNotIn('admin_url', respuesta.data)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_no_se_puede_elegir_rol_desde_el_formulario(self):
        respuesta = self.login_web(self.cliente, extra={'is_superuser': True, 'is_staff': True, 'admin_url': '/admin/'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('admin_url', respuesta.data)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_password_incorrecta_no_crea_sesion(self):
        respuesta = self.login_web(self.admin, password='Incorrecta123')
        self.assertEqual(respuesta.status_code, 401)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_superusuario_inactivo_no_ingresa(self):
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(self.login_web(self.admin).status_code, 403)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_web_requiere_csrf(self):
        respuesta = self.client.post(reverse('login-web'), {'email': self.admin.email, 'password': self.password}, format='json')
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_web_rechaza_origen_externo(self):
        pagina = self.client.get('/login/')
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        respuesta = self.client.post(reverse('login-web'), {'email': self.admin.email, 'password': self.password}, format='json', HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN='https://externo.example')
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_api_original_sigue_sin_crear_sesion_admin(self):
        respuesta = self.client.post('/api/auth/login/', {'email': self.admin.email, 'password': self.password}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('access', respuesta.data)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_cambiar_a_cliente_elimina_la_sesion_administrativa(self):
        self.login_web(self.admin)
        respuesta = self.login_web(self.cliente)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_logout_del_admin_cierra_el_acceso(self):
        self.login_web(self.admin)
        pagina = self.client.get(reverse('admin:index'))
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        respuesta = self.client.post(reverse('admin:logout'), HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
