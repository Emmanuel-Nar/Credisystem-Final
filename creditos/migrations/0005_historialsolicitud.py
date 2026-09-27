from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("creditos", "0004_credito_solicitud"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistorialSolicitud",
            fields=[
                ("id_historial", models.AutoField(primary_key=True, serialize=False)),
                ("estado_anterior", models.CharField(choices=[("aprobada", "Aprobada"), ("rechazada", "Rechazada"), ("en_revision", "En revisión")], max_length=20)),
                ("estado_nuevo", models.CharField(choices=[("aprobada", "Aprobada"), ("rechazada", "Rechazada"), ("en_revision", "En revisión")], max_length=20)),
                ("observacion", models.CharField(blank=True, max_length=255, null=True)),
                ("fecha_cambio", models.DateTimeField(auto_now_add=True)),
                ("administrador", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cambios_solicitudes", to=settings.AUTH_USER_MODEL)),
                ("solicitud", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial_administrativo", to="creditos.solicitudcredito")),
            ],
            options={"db_table": "historial_solicitud", "ordering": ["-fecha_cambio", "-id_historial"]},
        ),
        migrations.AddIndex(
            model_name="historialsolicitud",
            index=models.Index(fields=["solicitud", "fecha_cambio"], name="historial_s_solicit_72c8db_idx"),
        ),
    ]
