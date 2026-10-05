import json
import re
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from .models import ConfiguracionAsistente, PreguntaFrecuente


class AsistenteTests(TestCase):
    def datos(self, response):
        return json.loads(re.search(r'<script id="asistente-datos" type="application/json">(.*?)</script>', response.content.decode(), re.S).group(1))

    def test_preguntas_iniciales_publicas_y_no_aparecen_en_login(self):
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.datos(response)['preguntas']), 7)
        self.assertEqual(self.datos(response)['whatsapp'], '')
        self.assertNotContains(self.client.get(reverse('login')), 'id="asistente-datos"')

    def test_preguntas_activas_ordenadas_y_ediciones_publicadas(self):
        primera = PreguntaFrecuente.objects.first()
        primera.activa = False
        primera.save()
        nueva = PreguntaFrecuente.objects.create(pregunta='Consulta nueva', respuesta='Respuesta editada', orden=0)
        data = self.datos(self.client.get('/'))
        self.assertEqual(data['preguntas'][0]['pregunta'], nueva.pregunta)
        self.assertEqual(data['preguntas'][0]['respuesta'], nueva.respuesta)
        self.assertNotIn(primera.pregunta, [p['pregunta'] for p in data['preguntas']])

    def test_configuracion_desactivada_oculta_asistente(self):
        ConfiguracionAsistente.objects.filter(pk=1).update(activo=False)
        self.assertNotContains(self.client.get('/'), 'id="asistente-datos"')

    def test_sin_preguntas_no_se_recargan_respuestas_ocultas(self):
        PreguntaFrecuente.objects.update(activa=False)
        self.assertEqual(self.datos(self.client.get('/'))['preguntas'], [])

    def test_whatsapp_valido_e_invalido(self):
        config = ConfiguracionAsistente.objects.get(pk=1)
        config.numero_whatsapp = '5493415551234'
        config.full_clean()
        config.save()
        self.assertEqual(self.datos(self.client.get('/'))['whatsapp'], 'https://wa.me/5493415551234')
        for numero in ['+54 341 5551234', 'javascript:alert(1)', '123', '5493415551234\n']:
            config.numero_whatsapp = numero
            with self.subTest(numero=numero), self.assertRaises(ValidationError):
                config.full_clean()
        ConfiguracionAsistente.objects.filter(pk=1).update(numero_whatsapp='javascript:alert(1)')
        self.assertEqual(self.datos(self.client.get('/'))['whatsapp'], '')

    def test_respuestas_como_texto_seguro_y_destinos_controlados(self):
        texto = '</script><script>alert("xss")</script>'
        PreguntaFrecuente.objects.create(pregunta='Seguridad', respuesta=texto, destino='javascript:alert(1)', orden=0)
        response = self.client.get('/')
        self.assertNotContains(response, texto)
        pregunta = self.datos(response)['preguntas'][0]
        self.assertEqual(pregunta['respuesta'], texto)
        self.assertEqual(pregunta['enlace'], '')
        for p in self.datos(response)['preguntas']:
            if p['etiqueta'] == 'Ver mis solicitudes':
                self.assertEqual(p['enlace'], '/login/?next=%2Fmis-solicitudes%2F')

    def test_la_configuracion_es_unica(self):
        with self.assertRaises(ValidationError):
            ConfiguracionAsistente(id=2).full_clean()

    def test_staff_con_permisos_no_edita_contenido_publico(self):
        staff = Usuario.objects.create_user(email='staff@example.com', nombre='Staff', apellido='Prueba', documento='40111444', password='ClaveSegura123!', is_staff=True)
        staff.user_permissions.set(Permission.objects.filter(content_type__app_label='frontend'))
        self.client.force_login(staff)
        pregunta = PreguntaFrecuente.objects.first()
        for model in ['preguntafrecuente', 'configuracionasistente']:
            self.assertEqual(self.client.get(reverse(f'admin:frontend_{model}_changelist')).status_code, 403)
        response = self.client.post(reverse('admin:frontend_preguntafrecuente_change', args=[pregunta.pk]), {'pregunta': 'Alterada', 'respuesta': 'Nueva', 'orden': 0, 'activa': 'on'})
        self.assertEqual(response.status_code, 403)
        pregunta.refresh_from_db()
        self.assertNotEqual(pregunta.pregunta, 'Alterada')

    def test_superusuario_edita_respuesta_y_contacto(self):
        admin = Usuario.objects.create_superuser(email='admin@example.com', nombre='Admin', apellido='Prueba', documento='40111555', password='ClaveSegura123!')
        self.client.force_login(admin)
        pregunta = PreguntaFrecuente.objects.first()
        response = self.client.post(reverse('admin:frontend_preguntafrecuente_change', args=[pregunta.pk]), {'pregunta': 'Pregunta editada', 'respuesta': 'Respuesta nueva', 'orden': 0, 'activa': 'on', 'destino': ''})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('admin:frontend_configuracionasistente_change', args=[1]), {'activo': 'on', 'numero_whatsapp': '5493415551234'})
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        data = self.datos(self.client.get('/'))
        self.assertEqual(data['preguntas'][0]['respuesta'], 'Respuesta nueva')
        self.assertEqual(data['whatsapp'], 'https://wa.me/5493415551234')

    def test_visitante_no_puede_editar_preguntas(self):
        response = self.client.post(reverse('admin:frontend_preguntafrecuente_add'), {'pregunta': 'No autorizada'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PreguntaFrecuente.objects.filter(pregunta='No autorizada').exists())
