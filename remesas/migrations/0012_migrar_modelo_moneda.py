# Generated manually
from django.db import migrations, models
import django.utils.timezone


def migrar_datos_moneda(apps, schema_editor):
    """
    Migrar datos existentes al nuevo formato
    """
    Moneda = apps.get_model('remesas', 'Moneda')
    
    # Eliminar todas las monedas existentes para evitar conflictos
    Moneda.objects.all().delete()
    
    # Crear monedas por defecto
    Moneda.objects.create(
        codigo='USD',
        nombre='Dólar Estadounidense',
        valor_actual=1.00,
        valor_comercial=1.00,
        activa=True
    )
    
    Moneda.objects.create(
        codigo='EUR',
        nombre='Euro',
        valor_actual=0.85,
        valor_comercial=0.85,
        activa=True
    )
    
    Moneda.objects.create(
        codigo='COP',
        nombre='Peso Colombiano',
        valor_actual=4000.00,
        valor_comercial=4050.00,
        activa=True
    )


def reverse_migrar_datos_moneda(apps, schema_editor):
    """
    Reversar la migración
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('remesas', '0011_pago'),
    ]

    operations = [
        # Primero agregar los campos sin restricciones
        migrations.AddField(
            model_name='moneda',
            name='codigo',
            field=models.CharField(max_length=3, null=True, verbose_name='Código'),
        ),
        migrations.AddField(
            model_name='moneda',
            name='activa',
            field=models.BooleanField(default=True, verbose_name='Activa'),
        ),
        migrations.AddField(
            model_name='moneda',
            name='fecha_creacion',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='moneda',
            name='fecha_actualizacion',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='moneda',
            name='valor_comercial',
            field=models.DecimalField(decimal_places=2, default=1.0, help_text='Valor comercial de la moneda para transacciones', max_digits=10, verbose_name='Valor Comercial'),
        ),
        
        # Migrar datos
        migrations.RunPython(migrar_datos_moneda, reverse_migrar_datos_moneda),
        
        # Ahora agregar la restricción unique
        migrations.AlterField(
            model_name='moneda',
            name='codigo',
            field=models.CharField(max_length=3, unique=True, verbose_name='Código'),
        ),
        
        # Actualizar otros campos
        migrations.AlterField(
            model_name='moneda',
            name='nombre',
            field=models.CharField(max_length=50, verbose_name='Nombre'),
        ),
        migrations.AlterField(
            model_name='moneda',
            name='valor_actual',
            field=models.DecimalField(decimal_places=2, help_text='Valor actual de la moneda respecto al USD', max_digits=10, verbose_name='Valor Actual'),
        ),
        
        # Agregar meta opciones
        migrations.AlterModelOptions(
            name='moneda',
            options={'ordering': ['codigo'], 'verbose_name': 'Moneda', 'verbose_name_plural': 'Monedas'},
        ),
    ]
