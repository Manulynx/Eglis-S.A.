"""
Script para poblar los valores históricos en registros existentes
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from remesas.models import Pago, Remesa
from decimal import Decimal

def populate_historical_values():
    """Rellena los valores históricos para registros existentes que no los tienen"""
    
    print("Iniciando población de valores históricos...")
    
    # Actualizar Pagos sin valores históricos
    pagos_sin_historico = Pago.objects.filter(
        monto_usd_historico__isnull=True,
        valor_moneda_historico__isnull=True
    ).exclude(
        tipo_moneda__isnull=True
    ).exclude(
        cantidad__isnull=True
    ).exclude(
        usuario__isnull=True
    )
    
    print(f"Encontrados {pagos_sin_historico.count()} pagos sin valores históricos")
    
    for pago in pagos_sin_historico:
        try:
            # Obtener el valor actual de la moneda para el usuario
            valor_moneda = pago.tipo_moneda.get_valor_para_usuario(pago.usuario)
            pago.valor_moneda_historico = valor_moneda
            
            # Calcular monto USD
            if pago.tipo_moneda.codigo == 'USD':
                pago.monto_usd_historico = pago.cantidad
            else:
                if valor_moneda > 0:
                    pago.monto_usd_historico = pago.cantidad / Decimal(str(valor_moneda))
                else:
                    pago.monto_usd_historico = Decimal('0')
            
            pago.save()
            print(f"✓ Pago {pago.pago_id}: {pago.cantidad} -> ${pago.monto_usd_historico} USD")
            
        except Exception as e:
            print(f"✗ Error procesando pago {pago.pago_id}: {e}")
    
    # Actualizar Remesas sin valores históricos
    remesas_sin_historico = Remesa.objects.filter(
        monto_usd_historico__isnull=True,
        valor_moneda_historico__isnull=True
    ).exclude(
        moneda__isnull=True
    ).exclude(
        importe__isnull=True
    ).exclude(
        gestor__isnull=True
    )
    
    print(f"Encontradas {remesas_sin_historico.count()} remesas sin valores históricos")
    
    for remesa in remesas_sin_historico:
        try:
            # Obtener el valor actual de la moneda para el gestor
            valor_moneda = remesa.moneda.get_valor_para_usuario(remesa.gestor)
            remesa.valor_moneda_historico = valor_moneda
            
            # Calcular monto USD
            if remesa.moneda.codigo == 'USD':
                remesa.monto_usd_historico = remesa.importe
            else:
                if valor_moneda > 0:
                    remesa.monto_usd_historico = remesa.importe / Decimal(str(valor_moneda))
                else:
                    remesa.monto_usd_historico = Decimal('0')
            
            remesa.save()
            print(f"✓ Remesa {remesa.remesa_id}: {remesa.importe} -> ${remesa.monto_usd_historico} USD")
            
        except Exception as e:
            print(f"✗ Error procesando remesa {remesa.remesa_id}: {e}")
    
    print("Población de valores históricos completada.")

if __name__ == "__main__":
    populate_historical_values()
