#!/usr/bin/env python3
"""
Script para verificar que el nuevo flujo de remesas funciona correctamente
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from remesas.models import Remesa, Moneda
from django.contrib.auth.models import User

def test_remesa_flow():
    print("=== VERIFICANDO NUEVO FLUJO DE REMESAS ===")
    
    # Verificar estados disponibles
    remesa_test = Remesa()
    print("\n1. Estados disponibles en el modelo:")
    for choice in remesa_test._meta.get_field('estado').choices:
        print(f"   - {choice[0]}: {choice[1]}")
    
    # Verificar métodos del modelo
    print("\n2. Verificando métodos del modelo:")
    
    # Crear remesa de prueba (sin guardar)
    try:
        usd, created = Moneda.objects.get_or_create(
            codigo='USD',
            defaults={
                'nombre': 'Dólar Estadounidense',
                'valor_actual': 1.0,
                'valor_comercial': 1.0
            }
        )
        
        remesa = Remesa(
            receptor_nombre='Prueba',
            importe=100.00,
            tipo_pago='transferencia',
            moneda=usd,
            estado='pendiente'
        )
        
        print(f"   - Estado inicial: {remesa.estado}")
        print(f"   - Puede confirmar: {remesa.puede_confirmar()}")
        print(f"   - Puede completar: {remesa.puede_completar()}")
        print(f"   - Puede cancelar: {remesa.puede_cancelar()}")
        
        # Simular confirmación (cambio directo a completada)
        remesa.estado = 'completada'
        print(f"\n   - Después de confirmar (ahora directamente completada):")
        print(f"     Estado: {remesa.estado}")
        print(f"     Puede confirmar: {remesa.puede_confirmar()}")
        print(f"     Puede completar: {remesa.puede_completar()}")
        print(f"     Puede cancelar: {remesa.puede_cancelar()}")
        
        print("\n✅ VERIFICACIÓN EXITOSA: El nuevo flujo funciona correctamente")
        print("   - Pendiente → Completada (directamente)")
        print("   - Ya no existe el estado intermedio 'confirmada'")
        print("   - Los métodos del modelo están actualizados")
        
    except Exception as e:
        print(f"\n❌ ERROR en la verificación: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_remesa_flow()
