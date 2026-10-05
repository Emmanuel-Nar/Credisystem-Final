import io
import os
import runpy
import tempfile
from pathlib import Path
from smtplib import SMTPAuthenticationError
from unittest.mock import patch

from decouple import AutoConfig
from django.core import mail
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import CodigoVerificacion, Usuario
from .utils import enviar_codigo_verificacion


class ConfiguracionCorreoTests(SimpleTestCase):
    def test_configuracion_se_lee_de_env_y_entorno_tiene_prioridad(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, '.env').write_text('EMAIL_HOST=smtp.gmail.com\nEMAIL_HOST_USER=ejemplo@gmail.com\nEMAIL_HOST_PASSWORD=abcd efgh ijkl mnop\nEMAIL_PORT=587\nEMAIL_USE_TLS=True\nEMAIL_USE_SSL=False\nDJANGO_DEBUG=True\n')
            config = AutoConfig(search_path=tmp)
            with patch.dict(os.environ, {}, clear=True), patch('decouple.AutoConfig', return_value=config):
                values = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'credisystem/settings.py'))
            self.assertEqual(values['EMAIL_HOST_PASSWORD'], 'abcdefghijklmnop')
            self.assertEqual(values['EMAIL_HOST_USER'], 'ejemplo@gmail.com')
            self.assertEqual(values['EMAIL_PORT'], 587)
            self.assertTrue(values['EMAIL_USE_TLS'])
            self.assertFalse(values['EMAIL_USE_SSL'])
            self.assertEqual(values['EMAIL_BACKEND'], 'django.core.mail.backends.smtp.EmailBackend')
            self.assertEqual(values['DEFAULT_FROM_EMAIL'], 'ejemplo@gmail.com')
            with patch.dict(os.environ, {'EMAIL_HOST_USER': 'entorno@gmail.com'}, clear=True), patch('decouple.AutoConfig', return_value=config):
                values = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'credisystem/settings.py'))
            self.assertEqual(values['EMAIL_HOST_USER'], 'entorno@gmail.com')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AUTH_CANAL_VERIFICACION='email', DEFAULT_FROM_EMAIL='CREDISYSTEM <ejemplo@gmail.com>', BACKEND_PUBLIC_URL='https://ejemplo.test')
class EnvioCorreoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email='persona@example.com', nombre='Ana', apellido='Prueba', documento='40111222', password='ClaveSegura123!', telefono='3415555555', is_active=False, email_verificado=False)
        self.codigo = CodigoVerificacion.generar(self.usuario, CodigoVerificacion.Tipo.REGISTRO)

    def test_email_con_telefono_no_usa_whatsapp(self):
        with patch('usuarios.utils.enviar_codigo_whatsapp') as whatsapp:
            self.assertEqual(enviar_codigo_verificacion(self.usuario, self.codigo), 'email')
        whatsapp.assert_not_called()
        self.assertEqual(mail.outbox[0].from_email, 'CREDISYSTEM <ejemplo@gmail.com>')
        self.assertIn(self.codigo.codigo, mail.outbox[0].body)
        self.assertIn('https://ejemplo.test/api/auth/verificar/enlace/', mail.outbox[0].body)

    def test_fallos_no_confirman_envio_ni_exponen_texto_del_proveedor(self):
        for error in (SMTPAuthenticationError(535, b'secreto-del-proveedor'), TimeoutError('secreto-del-proveedor')):
            with self.subTest(error=type(error).__name__), patch('usuarios.utils.send_mail', side_effect=error), self.assertLogs('usuarios.utils', level='ERROR') as logs:
                self.assertEqual(enviar_codigo_verificacion(self.usuario, self.codigo), 'no_enviado')
            self.assertNotIn('secreto-del-proveedor', str(logs.output))
            self.assertNotIn(self.codigo.codigo, str(logs.output))

    def test_cero_envios_se_trata_como_fallo(self):
        with patch('usuarios.utils.send_mail', return_value=0), self.assertLogs('usuarios.utils', level='ERROR'):
            self.assertEqual(enviar_codigo_verificacion(self.usuario, self.codigo), 'no_enviado')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend', DEBUG=True)
    def test_consola_se_distingue_del_correo_real(self):
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(enviar_codigo_verificacion(self.usuario, self.codigo), 'consola')

    def test_backends_sin_envio_real_en_produccion_no_se_confirman(self):
        for backend in ('console', 'dummy'):
            with self.subTest(backend=backend), override_settings(EMAIL_BACKEND=f'django.core.mail.backends.{backend}.EmailBackend', DEBUG=False), patch('usuarios.utils.send_mail') as enviar, self.assertLogs('usuarios.utils', level='ERROR'):
                self.assertEqual(enviar_codigo_verificacion(self.usuario, self.codigo), 'no_enviado')
                enviar.assert_not_called()

    def test_registro_fallido_puede_reenviarse_sin_repetir_registro(self):
        payload = dict(nombre='Ana', apellido='Prueba', email='nuevo@example.com', documento='40999888', password='ClaveSegura123!', password2='ClaveSegura123!')
        with patch('usuarios.utils.send_mail', side_effect=TimeoutError), self.assertLogs('usuarios.utils', level='ERROR'):
            respuesta = self.client.post(reverse('registro-api'), payload, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertFalse(respuesta.data['codigo_enviado'])
        self.assertEqual(respuesta.data['canal_verificacion'], 'no_enviado')
        usuario = Usuario.objects.get(email=payload['email'])
        self.assertFalse(usuario.is_active)
        respuesta = self.client.post(reverse('reenviar-codigo'), {'email': usuario.email}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Usuario.objects.filter(email=usuario.email).count(), 1)

    def test_reenvio_y_recuperacion_no_revelan_existencia_ante_fallo(self):
        for endpoint in ('reenviar-codigo', 'password-recuperar'):
            with self.subTest(endpoint=endpoint), patch('usuarios.utils.send_mail', side_effect=TimeoutError), self.assertLogs('usuarios.utils', level='ERROR'):
                existente = self.client.post(reverse(endpoint), {'email': self.usuario.email}, format='json')
            ausente = self.client.post(reverse(endpoint), {'email': 'nadie@example.com'}, format='json')
            self.assertEqual(existente.status_code, 200)
            self.assertEqual(existente.data, ausente.data)
            self.assertNotIn('enviamos', existente.data['detail'].lower())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.gmail.com', EMAIL_HOST_USER='ejemplo@gmail.com', EMAIL_HOST_PASSWORD='clave-ficticia', EMAIL_USE_TLS=True, EMAIL_USE_SSL=False)
class ComandoCorreoTests(SimpleTestCase):
    def test_revision_local_no_envia_mensajes(self):
        with patch('usuarios.management.commands.probar_correo.send_mail') as enviar:
            salida = io.StringIO()
            call_command('probar_correo', stdout=salida)
        enviar.assert_not_called()
        self.assertIn('No se verificó la conexión', salida.getvalue())

    def test_envio_explicito_y_confirmacion_del_servidor(self):
        with patch('usuarios.management.commands.probar_correo.send_mail', return_value=1) as enviar:
            salida = io.StringIO()
            call_command('probar_correo', enviar_a='propio@example.com', stdout=salida)
        self.assertEqual(enviar.call_args.args[3], ['propio@example.com'])
        self.assertIn('El servidor aceptó', salida.getvalue())

    def test_fallo_no_expone_respuesta_del_proveedor(self):
        with patch('usuarios.management.commands.probar_correo.send_mail', side_effect=SMTPAuthenticationError(535, b'secreto-del-proveedor')):
            with self.assertRaises(CommandError) as error:
                call_command('probar_correo', enviar_a='propio@example.com')
        self.assertNotIn('secreto-del-proveedor', str(error.exception))

    @override_settings(EMAIL_HOST_PASSWORD='')
    def test_credenciales_incompletas(self):
        with self.assertRaises(CommandError):
            call_command('probar_correo')
