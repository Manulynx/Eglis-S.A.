from django.core.management.base import BaseCommand
from notificaciones.models import ConfiguracionNotificacion, DestinatarioNotificacion


class Command(BaseCommand):
    help = 'Configura las notificaciones de WhatsApp de forma rápida'

    def add_arguments(self, parser):
        parser.add_argument('--callmebot-key', type=str, help='API Key de CallMeBot')
        parser.add_argument('--twilio-sid', type=str, help='Account SID de Twilio')
        parser.add_argument('--twilio-token', type=str, help='Auth Token de Twilio')
        parser.add_argument('--twilio-phone', type=str, help='Número de WhatsApp de Twilio (+1234567890)')
        parser.add_argument('--whatsapp-token', type=str, help='Token de WhatsApp Business API')
        parser.add_argument('--whatsapp-phone-id', type=str, help='Phone Number ID de WhatsApp Business API')
        parser.add_argument('--add-destinatario', type=str, nargs=2, metavar=('NOMBRE', 'TELEFONO'), 
                          help='Agregar destinatario: nombre telefono')
        parser.add_argument('--set-destinatario-key', type=str, nargs=2, metavar=('TELEFONO', 'API_KEY'), 
                          help='Asignar API Key de CallMeBot a un destinatario específico')
        parser.add_argument('--activar', action='store_true', help='Activar el sistema de notificaciones')
        parser.add_argument('--test', type=str, help='Enviar mensaje de prueba a este número')

    def handle(self, *args, **options):
        config = ConfiguracionNotificacion.get_config()
        
        # Configurar CallMeBot
        if options['callmebot_key']:
            config.callmebot_api_key = options['callmebot_key']
            self.stdout.write(f'CallMeBot API Key configurado: {options["callmebot_key"]}')
        
        # Configurar Twilio
        if options['twilio_sid']:
            config.twilio_account_sid = options['twilio_sid']
            self.stdout.write(f'Twilio SID configurado: {options["twilio_sid"]}')
        
        if options['twilio_token']:
            config.twilio_auth_token = options['twilio_token']
            self.stdout.write('Twilio Auth Token configurado')
        
        if options['twilio_phone']:
            config.twilio_phone_number = options['twilio_phone']
            self.stdout.write(f'Número WhatsApp configurado: {options["twilio_phone"]}')
        
        # Configurar WhatsApp Business API
        if options['whatsapp_token']:
            config.whatsapp_business_token = options['whatsapp_token']
            self.stdout.write('WhatsApp Business Token configurado')
        
        if options['whatsapp_phone_id']:
            config.whatsapp_business_phone_id = options['whatsapp_phone_id']
            self.stdout.write(f'WhatsApp Phone ID configurado: {options["whatsapp_phone_id"]}')
        
        # Activar sistema
        if options['activar']:
            config.activo = True
            config.notificar_remesas = True
            config.notificar_pagos = True
            config.notificar_cambios_estado = True
            self.stdout.write(self.style.SUCCESS('Sistema de notificaciones activado'))
        
        config.save()
        
        # Agregar destinatario
        if options['add_destinatario']:
            nombre, telefono = options['add_destinatario']
            destinatario, created = DestinatarioNotificacion.objects.get_or_create(
                telefono=telefono,
                defaults={'nombre': nombre}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Destinatario agregado: {nombre} - {telefono}'))
            else:
                self.stdout.write(f'Destinatario ya existe: {nombre} - {telefono}')
        
        # Configurar API Key individual para un destinatario
        if options['set_destinatario_key']:
            telefono, api_key = options['set_destinatario_key']
            try:
                destinatario = DestinatarioNotificacion.objects.get(telefono=telefono)
                destinatario.callmebot_api_key = api_key
                destinatario.save()
                self.stdout.write(self.style.SUCCESS(f'API Key configurada para {destinatario.nombre} ({telefono})'))
            except DestinatarioNotificacion.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Destinatario {telefono} no encontrado. Agrégalo primero con --add-destinatario'))
        
        # Enviar mensaje de prueba
        if options['test']:
            from notificaciones.services import WhatsAppService
            whatsapp_service = WhatsAppService()
            
            mensaje = """🧪 *MENSAJE DE PRUEBA*

Este es un mensaje de prueba del sistema de notificaciones EGLIS.

Si recibes este mensaje, la configuración está funcionando correctamente.

Sistema EGLIS - Configuración completada"""
            
            try:
                if hasattr(config, 'callmebot_api_key') and config.callmebot_api_key:
                    success, response = whatsapp_service._enviar_con_callmebot(options['test'], mensaje)
                elif config.twilio_account_sid and config.twilio_auth_token:
                    success, response = whatsapp_service._enviar_con_twilio(options['test'], mensaje)
                elif config.whatsapp_business_token:
                    success, response = whatsapp_service._enviar_con_whatsapp_business(options['test'], mensaje)
                else:
                    success = False
                    response = "No hay configuración de API válida"
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'Mensaje de prueba enviado a {options["test"]}'))
                else:
                    self.stdout.write(self.style.ERROR(f'Error enviando mensaje: {response}'))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {e}'))
        
        # Mostrar estado actual
        self.stdout.write('\n--- CONFIGURACIÓN ACTUAL ---')
        self.stdout.write(f'Sistema activo: {config.activo}')
        self.stdout.write(f'CallMeBot configurado: {"Sí" if hasattr(config, "callmebot_api_key") and config.callmebot_api_key else "No"}')
        self.stdout.write(f'Twilio configurado: {"Sí" if config.twilio_account_sid else "No"}')
        self.stdout.write(f'WhatsApp Business API configurado: {"Sí" if config.whatsapp_business_token else "No"}')
        self.stdout.write(f'Notificar remesas: {config.notificar_remesas}')
        self.stdout.write(f'Notificar pagos: {config.notificar_pagos}')
        self.stdout.write(f'Destinatarios activos: {DestinatarioNotificacion.objects.filter(activo=True).count()}')
        
        self.stdout.write('\n--- EJEMPLOS DE USO ---')
        self.stdout.write('Configuración con CallMeBot (SÚPER FÁCIL):')
        self.stdout.write('python manage.py setup_notificaciones --callmebot-key "TU_API_KEY" --add-destinatario "Admin" "+5358270033" --activar')
        self.stdout.write('\nConfigurar API Key individual para un destinatario:')
        self.stdout.write('python manage.py setup_notificaciones --set-destinatario-key "+5355513196" "API_KEY_DEL_SEGUNDO_NUMERO"')
        self.stdout.write('\nConfiguración con WhatsApp Business API (GRATIS):')
        self.stdout.write('python manage.py setup_notificaciones --whatsapp-token "EAAxxxx" --whatsapp-phone-id "123456" --add-destinatario "Admin" "+5358270033" --activar')
        self.stdout.write('\nConfiguración con Twilio:')
        self.stdout.write('python manage.py setup_notificaciones --twilio-sid "ACxxx" --twilio-token "xxx" --twilio-phone "+1234567890" --add-destinatario "Admin" "+5358270033" --activar')
        self.stdout.write('\nEnviar prueba:')
        self.stdout.write('python manage.py setup_notificaciones --test "+5358270033"')
