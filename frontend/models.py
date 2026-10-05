from django.core.validators import RegexValidator
from django.db import models


class PreguntaFrecuente(models.Model):
    class Destino(models.TextChoices):
        NINGUNO = '', 'Sin enlace'
        REGISTRO = 'registro', 'Crear cuenta'
        SOLICITUD = 'solicitud', 'Solicitar crédito (iniciar sesión)'
        SOLICITUDES = 'solicitudes', 'Mis solicitudes (iniciar sesión)'
        CUOTAS = 'cuotas', 'Estado de cuenta (iniciar sesión)'
        RECUPERAR = 'recuperar', 'Recuperar contraseña'

    pregunta = models.CharField(max_length=180)
    respuesta = models.TextField(max_length=2000, help_text='Texto público. No incluir datos personales ni HTML.')
    destino = models.CharField(max_length=20, choices=Destino.choices, blank=True, default='')
    orden = models.PositiveSmallIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'pk']
        verbose_name = 'pregunta frecuente'
        verbose_name_plural = 'preguntas frecuentes'

    def __str__(self):
        return self.pregunta


class ConfiguracionAsistente(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    activo = models.BooleanField(default=True)
    numero_whatsapp = models.CharField(
        'número de WhatsApp', max_length=15, blank=True,
        validators=[RegexValidator(r'\A[1-9][0-9]{7,14}\Z', 'Usá entre 8 y 15 dígitos, con código de país, sin +, espacios ni guiones.')],
        help_text='Número público de atención, en formato internacional. Vacío: no aparece el botón de WhatsApp.',
    )

    class Meta:
        verbose_name = 'configuración del asistente'
        verbose_name_plural = 'configuración del asistente'
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='asistente_config_unica')]

    def __str__(self):
        return 'Asistente de la landing'
