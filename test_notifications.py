#!/usr/bin/env python
"""
Script para probar notificaciones al crear remesas
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.contrib.auth.models import User
from remesas.models import Remesa, Moneda
from notificaciones.models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
from notificaciones.services import WhatsAppService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_notifications():
    print("=== PRUEBA DE NOTIFICACIONES ===")
    
    # 1. Verificar configuración
    print("\n1. Verificando configuración...")
    config = ConfiguracionNotificacion.get_config()
    print(f"   - Notificaciones activas: {config.activo}")
    print(f"   - Notificar remesas: {config.notificar_remesas}")
    print(f"   - CallMeBot API Key: {'Configurado' if config.callmebot_api_key else 'No configurado'}")
    
    # 2. Verificar destinatarios
    print("\n2. Verificando destinatarios...")
    destinatarios = DestinatarioNotificacion.objects.filter(activo=True)
    print(f"   - Destinatarios activos: {destinatarios.count()}")
    for dest in destinatarios:
        print(f"     * {dest.nombre} - {dest.telefono} - Recibe remesas: {dest.recibir_remesas}")
    
    # 3. Crear una remesa de prueba
    print("\n3. Creando remesa de prueba...")
    try:
        # Obtener usuario de prueba
        user = User.objects.first()
        if not user:
            print("   ERROR: No hay usuarios en el sistema")
            return
        
        # Obtener moneda
        moneda = Moneda.objects.filter(activa=True).first()
        if not moneda:
            print("   ERROR: No hay monedas activas")
            return
        
        # Crear remesa
        remesa = Remesa.objects.create(
            receptor_nombre="Test Receptor",
            importe=100.00,
            tipo_pago="Test",
            moneda=moneda,
            gestor=user
        )
        
        print(f"   ✅ Remesa creada: {remesa.remesa_id}")
        
        # 4. Verificar logs de notificación
        print("\n4. Verificando logs de notificación...")
        logs = LogNotificacion.objects.filter(remesa_id=remesa.remesa_id).order_by('-fecha_creacion')
        
        if logs.exists():
            print(f"   ✅ Se encontraron {logs.count()} logs de notificación")
            for log in logs:
                print(f"     * {log.tipo} - {log.destinatario.nombre} - {log.estado}")
                if log.error_mensaje:
                    print(f"       Error: {log.error_mensaje}")
        else:
            print("   ❌ No se encontraron logs de notificación")
            print("   🔍 Verificando señales...")
            
            # Probar manualmente el servicio
            try:
                whatsapp_service = WhatsAppService()
                whatsapp_service.enviar_notificacion('remesa_nueva', remesa=remesa)
                print("   ✅ Servicio de notificaciones ejecutado manualmente")
            except Exception as e:
                print(f"   ❌ Error en servicio de notificaciones: {e}")
        
        # Limpiar remesa de prueba
        remesa.delete()
        print(f"   🧹 Remesa de prueba eliminada")
        
    except Exception as e:
        print(f"   ❌ Error creando remesa de prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_notifications()
