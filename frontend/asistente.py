import re
from urllib.parse import urlencode

from django.urls import reverse

from .models import ConfiguracionAsistente, PreguntaFrecuente


def datos_asistente():
    configuracion = ConfiguracionAsistente.objects.filter(pk=1).first()
    if configuracion and not configuracion.activo:
        return None
    destinos = {
        'registro': ('Crear cuenta', reverse('registro')),
        'recuperar': ('Recuperar contraseña', reverse('recuperar_password')),
    }
    for clave, etiqueta, ruta in [
        ('solicitud', 'Ir a solicitar crédito', 'solicitar_credito'),
        ('solicitudes', 'Ver mis solicitudes', 'mis_solicitudes'),
        ('cuotas', 'Ver mi estado de cuenta', 'estado_cuenta'),
    ]:
        destinos[clave] = (etiqueta, reverse('login') + '?' + urlencode({'next': reverse(ruta)}))
    preguntas = []
    for pregunta in PreguntaFrecuente.objects.filter(activa=True):
        etiqueta, url = destinos.get(pregunta.destino, ('', ''))
        preguntas.append({'pregunta': pregunta.pregunta, 'respuesta': pregunta.respuesta, 'enlace': url, 'etiqueta': etiqueta})
    numero = configuracion.numero_whatsapp if configuracion else ''
    whatsapp = f'https://wa.me/{numero}' if re.fullmatch(r'[1-9][0-9]{7,14}', numero) else ''
    return {'preguntas': preguntas, 'whatsapp': whatsapp}
