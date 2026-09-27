from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("creditos", "0006_cuota")]

    operations = [
        migrations.AddField(
            model_name="cuota",
            name="monto_pagado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.CreateModel(
            name="ImputacionPago",
            fields=[
                ("id_imputacion", models.AutoField(primary_key=True, serialize=False)),
                ("monto", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("fecha_imputacion", models.DateTimeField(auto_now_add=True)),
                ("cuota", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="imputaciones", to="creditos.cuota")),
                ("pago", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="imputaciones", to="creditos.pago")),
            ],
            options={"db_table": "imputacion_pago"},
        ),
        migrations.AddConstraint(
            model_name="imputacionpago",
            constraint=models.UniqueConstraint(fields=("pago", "cuota"), name="uq_imputacion_pago_cuota"),
        ),
        migrations.AddIndex(
            model_name="imputacionpago",
            index=models.Index(fields=["pago", "cuota"], name="imputacion__pago_id_6dca2e_idx"),
        ),
    ]
