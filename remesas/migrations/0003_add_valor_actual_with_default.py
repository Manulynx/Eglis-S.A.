# Generated manually to add valor_actual field with default value

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('remesas', '0002_remove_moneda_cantidad_remove_moneda_valor_actual_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='moneda',
            name='valor_actual',
            field=models.DecimalField(
                blank=True, 
                decimal_places=2, 
                default=1.0, 
                help_text='Valor actual de la moneda', 
                max_digits=10, 
                null=True
            ),
        ),
    ]
