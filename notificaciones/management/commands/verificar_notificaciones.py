from django.core.management.base import BaseCommand
from notificaciones.models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
from django.contrib.auth.models import User
from remesas.models import Remesa, Moneda


class Command(BaseCommand):
    help = 'Verifica y configura el sistema de notificaciones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Crea una remesa de prueba para verificar notificaciones',
        )
        parser.add_argument(
            '--setup',
            action='store_true',
            help='Configura el sistema de notificaciones básico',
        )

    def handle(self, *args, **options):
        self.stdout.write("=== VERIFICACIÓN DEL SISTEMA DE NOTIFICACIONES ===\n")
        
        # 1. Verificar configuración
        self.stdout.write("1. Verificando configuración...")
        config = ConfiguracionNotificacion.get_config()
        self.stdout.write(f"   - Notificaciones activas: {config.activo}")
        self.stdout.write(f"   - Notificar remesas: {config.notificar_remesas}")
        self.stdout.write(f"   - Notificar cambios estado: {config.notificar_cambios_estado}")
        self.stdout.write(f"   - CallMeBot API Key: {'Configurado' if config.callmebot_api_key else 'No configurado'}")
        self.stdout.write(f"   - Twilio configurado: {'Sí' if config.twilio_account_sid else 'No'}")
        
        # 2. Verificar destinatarios
        self.stdout.write("\n2. Verificando destinatarios...")
        destinatarios = DestinatarioNotificacion.objects.filter(activo=True)
        self.stdout.write(f"   - Destinatarios activos: {destinatarios.count()}")
        for dest in destinatarios:
            self.stdout.write(f"     * {dest.nombre} - {dest.telefono}")
            self.stdout.write(f"       Recibe remesas: {dest.recibir_remesas}")
            self.stdout.write(f"       API Key personal: {'Sí' if dest.callmebot_api_key else 'No'}")
        
        # 3. Verificar logs recientes
        self.stdout.write("\n3. Verificando logs recientes...")
        logs_recientes = LogNotificacion.objects.all().order_by('-fecha_creacion')[:5]
        if logs_recientes:
            self.stdout.write(f"   - Últimos {logs_recientes.count()} logs:")
            for log in logs_recientes:
                self.stdout.write(f"     * {log.fecha_creacion.strftime('%Y-%m-%d %H:%M')} - {log.tipo} - {log.estado}")
                if log.error_mensaje:
                    self.stdout.write(f"       Error: {log.error_mensaje}")
        else:
            self.stdout.write("   - No hay logs de notificaciones")
        
        # 4. Configuración básica si se solicita
        if options['setup']:
            self.stdout.write("\n4. Configurando sistema básico...")
            self.setup_basic_config()
        
        # 5. Prueba con remesa si se solicita
        if options['test']:
            self.stdout.write("\n5. Creando remesa de prueba...")
            self.test_notification()
        
        self.stdout.write(self.style.SUCCESS("\n✅ Verificación completada"))

    def setup_basic_config(self):
        """Configura la configuración básica"""
        config = ConfiguracionNotificacion.get_config()
        
        if not config.activo:
            config.activo = True
            config.save()
            self.stdout.write("   ✅ Notificaciones activadas")
        
        if not config.notificar_remesas:
            config.notificar_remesas = True
            config.save()
            self.stdout.write("   ✅ Notificaciones de remesas activadas")
        
        # Crear destinatario de prueba si no existe
        if not DestinatarioNotificacion.objects.exists():
            dest = DestinatarioNotificacion.objects.create(
                nombre="Administrador",
                telefono="+1234567890",  # Número de ejemplo
                activo=False,  # Inactivo por defecto hasta configurar
                recibir_remesas=True,
                recibir_pagos=True,
                recibir_cambios_estado=True
            )
            self.stdout.write(f"   ✅ Destinatario de ejemplo creado: {dest}")
            self.stdout.write(f"      ⚠️ Configurar teléfono real y activar manualmente")

    def test_notification(self):
        """Crea una remesa de prueba para verificar notificaciones"""
        try:
            # Obtener usuario
            user = User.objects.first()
            if not user:
                self.stdout.write("   ❌ No hay usuarios en el sistema")
                return
            
            # Obtener moneda
            moneda = Moneda.objects.filter(activa=True).first()
            if not moneda:
                self.stdout.write("   ❌ No hay monedas activas")
                return
            
            # Crear remesa de prueba
            remesa = Remesa.objects.create(
                receptor_nombre="Test Notificación",
                importe=100.00,
                tipo_pago="Prueba",
                moneda=moneda,
                gestor=user
            )
            
            self.stdout.write(f"   ✅ Remesa de prueba creada: {remesa.remesa_id}")
            
            # Verificar si se crearon logs
            import time
            time.sleep(1)  # Esperar un poco para que se procesen las señales
            
            logs = LogNotificacion.objects.filter(remesa_id=remesa.remesa_id)
            if logs.exists():
                self.stdout.write(f"   ✅ Se generaron {logs.count()} logs de notificación")
                for log in logs:
                    self.stdout.write(f"     * {log.destinatario.nombre} - {log.estado}")
                    if log.error_mensaje:
                        self.stdout.write(f"       Error: {log.error_mensaje}")
            else:
                self.stdout.write("   ❌ No se generaron logs de notificación")
                self.stdout.write("   🔍 Posibles causas:")
                self.stdout.write("      - Notificaciones desactivadas")
                self.stdout.write("      - No hay destinatarios activos")
                self.stdout.write("      - Error en las señales de Django")
            
            # Limpiar
            remesa.delete()
            self.stdout.write("   🧹 Remesa de prueba eliminada")
            
        except Exception as e:
            self.stdout.write(f"   ❌ Error: {e}")
