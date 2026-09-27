from django.db import migrations, models
import django.core.validators
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("creditos", "0005_historialsolicitud")]
    operations = [
        migrations.CreateModel(
            name="Cuota",
            fields=[
                ("id_cuota", models.AutoField(primary_key=True, serialize=False)),
                ("numero", models.PositiveIntegerField()),
                ("importe", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("fecha_vencimiento", models.DateField()),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("pagada", "Pagada"), ("vencida", "Vencida")], default="pendiente", max_length=20)),
                ("fecha_pago", models.DateTimeField(blank=True, null=True)),
                ("credito", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cuotas", to="creditos.credito")),
            ],
            options={"db_table":"cuota", "ordering":["numero"]},
        ),
        migrations.AddConstraint(model_name="cuota", constraint=models.UniqueConstraint(fields=("credito", "numero"), name="uq_cuota_credito_numero")),
        migrations.AddIndex(model_name="cuota", index=models.Index(fields=["credito", "estado", "fecha_vencimiento"], name="cuota_cred_est_venc_idx")),
    ]
