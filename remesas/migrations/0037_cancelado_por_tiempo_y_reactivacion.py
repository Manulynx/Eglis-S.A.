from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("remesas", "0036_notificado_pendiente_23h_en"),
    ]

    operations = [
        migrations.AddField(
            model_name="remesa",
            name="cancelado_por_tiempo",
            field=models.BooleanField(default=False, help_text="Indica si la remesa fue cancelada automáticamente por tiempo"),
        ),
        migrations.AddField(
            model_name="remesa",
            name="cancelado_por_tiempo_en",
            field=models.DateTimeField(blank=True, help_text="Fecha/hora en que la remesa fue cancelada automáticamente por tiempo", null=True),
        ),
        migrations.AddField(
            model_name="remesa",
            name="reactivado_desde",
            field=models.ForeignKey(
                blank=True,
                help_text="Remesa original de la cual se reactivó este registro",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reactivaciones",
                to="remesas.remesa",
            ),
        ),
        migrations.AddField(
            model_name="pago",
            name="cancelado_por_tiempo",
            field=models.BooleanField(default=False, help_text="Indica si el pago fue cancelado automáticamente por tiempo"),
        ),
        migrations.AddField(
            model_name="pago",
            name="cancelado_por_tiempo_en",
            field=models.DateTimeField(blank=True, help_text="Fecha/hora en que el pago fue cancelado automáticamente por tiempo", null=True),
        ),
        migrations.AddField(
            model_name="pago",
            name="reactivado_desde",
            field=models.ForeignKey(
                blank=True,
                help_text="Pago original del cual se reactivó este registro",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reactivaciones",
                to="remesas.pago",
            ),
        ),
        migrations.AddField(
            model_name="pagoremesa",
            name="cancelado_por_tiempo",
            field=models.BooleanField(
                default=False,
                help_text="Indica si el pago de remesa fue cancelado automáticamente por tiempo",
            ),
        ),
        migrations.AddField(
            model_name="pagoremesa",
            name="cancelado_por_tiempo_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha/hora en que el pago de remesa fue cancelado automáticamente por tiempo",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="pagoremesa",
            name="reactivado_desde",
            field=models.ForeignKey(
                blank=True,
                help_text="Pago de remesa original del cual se reactivó este registro",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reactivaciones",
                to="remesas.pagoremesa",
            ),
        ),
    ]
