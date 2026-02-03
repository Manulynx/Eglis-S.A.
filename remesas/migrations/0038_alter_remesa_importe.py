from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("remesas", "0037_cancelado_por_tiempo_y_reactivacion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remesa",
            name="importe",
            field=models.DecimalField(
                blank=True, decimal_places=2, help_text="Importe", max_digits=15, null=True
            ),
        ),
    ]
