#!/usr/bin/env python
"""
Script para corregir balances de usuarios basado en su historial de transacciones
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.contrib.auth.models import User
from login.models import PerfilUsuario
from remesas.models import Remesa, Pago


def calcular_balance_correcto(usuario):
    """
    Calcula el balance correcto basado en el historial de transacciones
    """
    # Sumar remesas confirmadas (ingresos)
    remesas_confirmadas = Remesa.objects.filter(gestor=usuario, estado='confirmada')
    total_remesas = sum(remesa.calcular_monto_en_usd() for remesa in remesas_confirmadas)
    
    # Restar pagos realizados (egresos)
    pagos = Pago.objects.filter(usuario=usuario)
    total_pagos = sum(pago.calcular_monto_en_usd() for pago in pagos)
    
    return total_remesas - total_pagos


def verificar_balance_usuario(usuario):
    """
    Verifica si el balance de un usuario es correcto
    """
    if not hasattr(usuario, 'perfil'):
        return False, "Usuario no tiene perfil"
    
    balance_actual = usuario.perfil.balance
    balance_correcto = calcular_balance_correcto(usuario)
    
    diferencia = balance_actual - balance_correcto
    
    return abs(diferencia) < Decimal('0.01'), {
        'balance_actual': balance_actual,
        'balance_correcto': balance_correcto,
        'diferencia': diferencia
    }


def corregir_balance_usuario(usuario):
    """
    Corrige el balance de un usuario específico
    """
    if not hasattr(usuario, 'perfil'):
        print(f"❌ {usuario.username}: No tiene perfil")
        return False
    
    es_correcto, info = verificar_balance_usuario(usuario)
    
    if es_correcto:
        print(f"✅ {usuario.username}: Balance correcto (${info['balance_actual']:.2f})")
        return True
    
    print(f"🔧 {usuario.username}: Corrigiendo balance...")
    print(f"   Balance anterior: ${info['balance_actual']:.2f}")
    print(f"   Balance correcto: ${info['balance_correcto']:.2f}")
    print(f"   Diferencia: ${info['diferencia']:.2f}")
    
    # Actualizar balance
    usuario.perfil.balance = info['balance_correcto']
    usuario.perfil.save()
    
    print(f"✅ {usuario.username}: Balance corregido exitosamente")
    return True


def verificar_todos_los_balances():
    """
    Verifica y corrige los balances de todos los usuarios
    """
    print("=== VERIFICACIÓN DE BALANCES DE TODOS LOS USUARIOS ===\n")
    
    usuarios_con_perfil = User.objects.filter(perfil__isnull=False)
    usuarios_corregidos = 0
    usuarios_correctos = 0
    usuarios_con_error = 0
    
    for usuario in usuarios_con_perfil:
        try:
            if corregir_balance_usuario(usuario):
                es_correcto, _ = verificar_balance_usuario(usuario)
                if es_correcto:
                    usuarios_correctos += 1
                else:
                    usuarios_corregidos += 1
            else:
                usuarios_con_error += 1
        except Exception as e:
            print(f"❌ {usuario.username}: Error - {e}")
            usuarios_con_error += 1
    
    print(f"\n=== RESUMEN ===")
    print(f"✅ Usuarios con balance correcto: {usuarios_correctos}")
    print(f"🔧 Usuarios corregidos: {usuarios_corregidos}")
    print(f"❌ Usuarios con error: {usuarios_con_error}")
    print(f"📊 Total usuarios verificados: {usuarios_con_perfil.count()}")


def verificar_usuario_especifico(username):
    """
    Verifica y corrige el balance de un usuario específico
    """
    try:
        usuario = User.objects.get(username=username)
        print(f"=== VERIFICACIÓN DE BALANCE: {username} ===\n")
        
        # Mostrar historial de transacciones
        print("HISTORIAL DE REMESAS CONFIRMADAS:")
        remesas = Remesa.objects.filter(gestor=usuario, estado='confirmada')
        for remesa in remesas:
            monto_usd = remesa.calcular_monto_en_usd()
            print(f"  + {remesa.remesa_id}: ${remesa.importe} = ${monto_usd:.2f} USD")
        
        print("\nHISTORIAL DE PAGOS:")
        pagos = Pago.objects.filter(usuario=usuario)
        for pago in pagos:
            monto_usd = pago.calcular_monto_en_usd()
            print(f"  - {pago.pago_id}: ${pago.cantidad} = ${monto_usd:.2f} USD")
        
        print()
        corregir_balance_usuario(usuario)
        
    except User.DoesNotExist:
        print(f"❌ Usuario '{username}' no encontrado")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Verificar usuario específico
        username = sys.argv[1]
        verificar_usuario_especifico(username)
    else:
        # Verificar todos los usuarios
        verificar_todos_los_balances()
