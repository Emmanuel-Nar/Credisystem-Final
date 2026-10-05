from django.db import migrations


PREGUNTAS = [
    ('¿Cómo solicito un crédito?', 'Creá tu cuenta, verificá tu correo e iniciá sesión. En Solicitar crédito completá el monto, el plazo, tus ingresos y el CUIL/CUIT, adjuntá el comprobante de ingresos y autorizá la consulta. Al enviar verás el resultado o si la solicitud queda en revisión.', 'solicitud'),
    ('¿Qué documentación necesito?', 'La solicitud requiere tu CUIL/CUIT y un comprobante de ingresos en PDF, JPG o PNG. Los datos de identidad deben coincidir con los registrados en tu cuenta. El formulario indica el tamaño máximo del archivo y los campos obligatorios.', 'solicitud'),
    ('¿Qué significa que mi solicitud está en revisión?', 'Significa que necesita una evaluación administrativa antes de tener una decisión. Podés consultar su estado en Mis solicitudes. Cuando administración la apruebe o rechace, recibirás una notificación dentro de CREDISYSTEM. No implica una aprobación ni tiene un plazo garantizado.', 'solicitudes'),
    ('¿Dónde consulto mis cuotas y pagos?', 'Iniciá sesión y entrá en Estado de cuenta para consultar tus créditos, cuotas, vencimientos y pagos confirmados. El detalle de cada crédito también muestra sus cuotas.', 'cuotas'),
    ('¿Cómo recupero mi contraseña?', 'En el inicio de sesión elegí la opción para recuperar tu contraseña e ingresá el correo de tu cuenta. Revisá la bandeja de entrada y Spam; seguí las instrucciones del mensaje para establecer una contraseña nueva.', 'recuperar'),
    ('No recibí el código de activación, ¿qué hago?', 'Revisá que el correo sea correcto y buscá el mensaje en Spam. En la pantalla de verificación podés solicitar un reenvío cuando se habilite el botón. Si la cuenta ya fue creada, no necesitás registrarte de nuevo.', ''),
    ('¿Puedo corregir mis datos personales?', 'Desde Perfil podés actualizar tu teléfono y dirección. Para corregir nombre, apellido, DNI o email, solicitá asistencia a administración. No envíes contraseñas ni códigos de verificación.', ''),
]


def cargar_preguntas(apps, schema_editor):
    Pregunta = apps.get_model('frontend', 'PreguntaFrecuente')
    Configuracion = apps.get_model('frontend', 'ConfiguracionAsistente')
    alias = schema_editor.connection.alias
    Configuracion.objects.using(alias).get_or_create(pk=1)
    for orden, (pregunta, respuesta, destino) in enumerate(PREGUNTAS, 1):
        Pregunta.objects.using(alias).get_or_create(pregunta=pregunta, defaults={'respuesta': respuesta, 'destino': destino, 'orden': orden})


class Migration(migrations.Migration):
    dependencies = [('frontend', '0001_initial')]
    operations = [migrations.RunPython(cargar_preguntas, migrations.RunPython.noop)]
