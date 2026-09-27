from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("creditos", "0003_pago_external_reference_pago_mp_payment_id_and_more")]

    operations = [
        migrations.AddField(
            model_name="credito",
            name="solicitud",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="credito_otorgado", to="creditos.solicitudcredito"),
        ),
    ]
