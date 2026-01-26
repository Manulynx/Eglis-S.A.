from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('remesas', '0038_alter_remesa_importe'),
    ]

    operations = [
        migrations.AddField(
            model_name='moneda',
            name='alerta_fondo_bajo_enviada',
            field=models.BooleanField(
                default=False,
                help_text='Evita enviar alertas repetidas mientras el fondo permanezca bajo el mínimo',
                verbose_name='Alerta Fondo Bajo Enviada',
            ),
        ),
        migrations.AddField(
            model_name='moneda',
            name='alerta_fondo_bajo_enviada_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Última fecha en la que se emitió la alerta de fondo bajo',
                null=True,
                verbose_name='Fecha Alerta Fondo Bajo',
            ),
        ),
    ]
