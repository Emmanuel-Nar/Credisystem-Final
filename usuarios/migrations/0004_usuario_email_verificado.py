from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("usuarios", "0003_usuario_notificaciones_push_activas_and_more")]
    operations = [migrations.AddField(model_name="usuario", name="email_verificado", field=models.BooleanField(default=True))]
