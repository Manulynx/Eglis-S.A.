from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("remesas", "0035_moneda_alerta_fondo_minimo"),
    ]

    operations = [
        migrations.AddField(
            model_name="pago",
            name="notificado_pendiente_23h_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en que se notificó a admins que el pago lleva 23h pendiente",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="pagoremesa",
            name="notificado_pendiente_23h_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en que se notificó a admins que el pago de remesa lleva 23h pendiente",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="remesa",
            name="notificado_pendiente_23h_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en que se notificó a admins que la remesa lleva 23h pendiente",
                null=True,
            ),
        ),
    ]
