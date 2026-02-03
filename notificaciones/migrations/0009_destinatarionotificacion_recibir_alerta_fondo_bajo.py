from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notificaciones", "0008_destinatarionotificacion_monedas_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="destinatarionotificacion",
            name="recibir_alerta_fondo_bajo",
            field=models.BooleanField(
                default=True,
                help_text="Recibir notificación de alerta de fondo de caja bajo",
            ),
        ),
    ]