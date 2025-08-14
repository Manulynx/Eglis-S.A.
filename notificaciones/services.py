import requests
import json
from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Servicio para enviar notificaciones por WhatsApp"""
    
    def __init__(self):
        self.config = ConfiguracionNotificacion.get_config()
    
    def enviar_notificacion(self, tipo, remesa=None, pago=None, estado_anterior=None):
        """
        Envía notificaciones a todos los destinatarios activos
        
        Args:
            tipo: Tipo de notificación ('remesa_nueva', 'remesa_estado', 'pago_nuevo', 'pago_estado')
            remesa: Objeto Remesa (opcional)
            pago: Objeto Pago (opcional)
            estado_anterior: Estado anterior para cambios de estado (opcional)
        """
        if not self.config.activo:
            logger.info("Notificaciones desactivadas")
            return
        
        # Verificar si debe enviar este tipo de notificación
        if tipo in ['remesa_nueva', 'remesa_estado'] and not self.config.notificar_remesas:
            return
        if tipo in ['pago_nuevo', 'pago_estado'] and not self.config.notificar_pagos:
            return
        if tipo in ['remesa_estado', 'pago_estado'] and not self.config.notificar_cambios_estado:
            return
        
        # Generar mensaje
        mensaje = self._generar_mensaje(tipo, remesa, pago, estado_anterior)
        
        # Obtener destinatarios activos
        destinatarios = self._obtener_destinatarios(tipo)
        
        # Enviar a cada destinatario
        for destinatario in destinatarios:
            self._enviar_mensaje_individual(destinatario, mensaje, tipo, remesa, pago)
    
    def _generar_mensaje(self, tipo, remesa, pago, estado_anterior):
        """Genera el mensaje según el tipo de notificación"""
        
        if tipo == 'remesa_nueva' and remesa:
            return f"""🚀 *NUEVA REMESA CREADA*

🎯 *Destinatario:* {remesa.moneda.nombre if remesa.moneda else 'Dólar Americano'}
💰 *Importe:* ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}

📞 *Remitente:* {remesa.receptor_nombre or 'N/A'}

📊 *Estado:* Pendiente

📋 *ID:* {remesa.remesa_id}
👤 *Gestor:* {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}

📅 *Fecha:* {remesa.fecha.strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""

        elif tipo == 'remesa_estado' and remesa:
            return f"""🔄 *CAMBIO DE ESTADO - REMESA*

📋 *ID:* {remesa.remesa_id}
👤 *Gestor:* {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
💰 *Importe:* ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}
📊 *Estado anterior:* {estado_anterior or 'N/A'}
✅ *Estado actual:* {remesa.get_estado_display()}
📅 *Actualizado:* {timezone.now().strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""

        elif tipo == 'pago_nuevo' and pago:
            # Verificar el tipo de pago y generar mensaje específico
            if pago.tipo_pago == 'transferencia':
                # Mensaje para transferencia - número de tarjeta ANTES del título
                mensaje = ""
                
                # Mostrar número de tarjeta PRIMERO, antes del título (sin icono)
                if hasattr(pago, 'tarjeta') and pago.tarjeta:
                    mensaje += f"*{pago.tarjeta}*\n\n"
                
                mensaje += f"""💳 *Nuevo pago creado*

💰 *Cantidad:* ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}

👤 *Gestor:* {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
💳 *Tipo:* Transferencia
🎯 *Destinatario:* {'N/A'}
📞 *Teléfono:* {pago.telefono or 'N/A'}
📍 *Dirección:* {pago.direccion or 'N/A'}
📅 *Fecha:* {pago.fecha_creacion.strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""
                
            elif pago.tipo_pago == 'efectivo':
                # Mensaje para efectivo
                mensaje = f"""💳 *Nuevo pago creado*

💰 *Cantidad:* ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}

👤 *Gestor:* {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
💳 *Tipo:* Efectivo
🎯 *Destinatario:* {pago.destinatario}
📞 *Teléfono:* {pago.telefono or 'N/A'}
📍 *Dirección:* {pago.direccion or 'N/A'}
📅 *Fecha:* {pago.fecha_creacion.strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""
            
            else:
                # Mensaje genérico para otros tipos
                mensaje = f"""💳 *Nuevo pago creado*

💰 *Cantidad:* ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}

👤 *Gestor:* {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
💳 *Tipo:* {pago.get_tipo_pago_display()}
🎯 *Destinatario:* {pago.destinatario}
📞 *Teléfono:* {pago.telefono or 'N/A'}
📍 *Dirección:* {pago.direccion or 'N/A'}
📅 *Fecha:* {pago.fecha_creacion.strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""
            
            return mensaje

        elif tipo == 'pago_estado' and pago:
            return f"""🔄 *CAMBIO DE ESTADO - PAGO*

💳 *ID Pago:* {pago.id}
👤 *Usuario:* {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
💰 *Cantidad:* ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}
🎯 *Destinatario:* {pago.destinatario}
📊 *Estado anterior:* {estado_anterior or 'N/A'}
✅ *Estado actual:* Actualizado
📅 *Actualizado:* {timezone.now().strftime('%d/%m/%Y %H:%M')}

Sistema EGLIS - Notificación automática"""

        return "Notificación del sistema EGLIS"
    
    def _obtener_destinatarios(self, tipo):
        """Obtiene los destinatarios que deben recibir este tipo de notificación"""
        destinatarios = DestinatarioNotificacion.objects.filter(activo=True)
        
        if tipo in ['remesa_nueva', 'remesa_estado']:
            destinatarios = destinatarios.filter(recibir_remesas=True)
        elif tipo in ['pago_nuevo', 'pago_estado']:
            destinatarios = destinatarios.filter(recibir_pagos=True)
        
        if tipo in ['remesa_estado', 'pago_estado']:
            destinatarios = destinatarios.filter(recibir_cambios_estado=True)
        
        return destinatarios
    
    def _enviar_mensaje_individual(self, destinatario, mensaje, tipo, remesa, pago):
        """Envía un mensaje a un destinatario específico"""
        
        # Crear log de notificación
        log = LogNotificacion.objects.create(
            tipo=tipo,
            destinatario=destinatario,
            mensaje=mensaje,
            remesa_id=remesa.remesa_id if remesa else None,
            pago_id=pago.id if pago else None,
        )
        
        try:
            # Usar CallMeBot con API Key individual del destinatario (prioridad)
            if hasattr(destinatario, 'callmebot_api_key') and destinatario.callmebot_api_key:
                success, response = self._enviar_con_callmebot_individual(destinatario, mensaje)
            # Usar CallMeBot global como fallback
            elif hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                success, response = self._enviar_con_callmebot(destinatario.telefono, mensaje)
            # Fallback a Twilio
            elif self.config.twilio_account_sid and self.config.twilio_auth_token:
                success, response = self._enviar_con_twilio(destinatario.telefono, mensaje)
            # Fallback a WhatsApp Business API
            elif self.config.whatsapp_business_token:
                success, response = self._enviar_con_whatsapp_business(destinatario.telefono, mensaje)
            else:
                success = False
                response = "No hay configuración válida de API"
            
            # Actualizar log
            if success:
                log.estado = 'enviado'
                log.fecha_envio = timezone.now()
                log.respuesta_api = str(response)
                logger.info(f"Notificación enviada a {destinatario.nombre}: {tipo}")
            else:
                log.estado = 'fallido'
                log.error_mensaje = str(response)
                logger.error(f"Error enviando notificación a {destinatario.nombre}: {response}")
            
            log.save()
            
        except Exception as e:
            log.estado = 'fallido'
            log.error_mensaje = str(e)
            log.save()
            logger.error(f"Excepción enviando notificación a {destinatario.nombre}: {e}")
    
    def _enviar_con_twilio(self, telefono, mensaje):
        """Envía mensaje usando Twilio WhatsApp API"""
        try:
            client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
            
            message = client.messages.create(
                body=mensaje,
                from_=f'whatsapp:{self.config.twilio_phone_number}',
                to=f'whatsapp:{telefono}'
            )
            
            return True, f"SID: {message.sid}"
            
        except Exception as e:
            return False, str(e)
    
    def _enviar_con_whatsapp_business(self, telefono, mensaje):
        """Envía mensaje usando WhatsApp Business API"""
        try:
            url = f"https://graph.facebook.com/v18.0/{self.config.whatsapp_business_phone_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.config.whatsapp_business_token}',
                'Content-Type': 'application/json',
            }
            
            # Limpiar número de teléfono (remover + y espacios)
            telefono_limpio = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            data = {
                'messaging_product': 'whatsapp',
                'to': telefono_limpio,
                'type': 'text',
                'text': {
                    'body': mensaje
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def _enviar_con_callmebot(self, telefono, mensaje):
        """Envía mensaje usando CallMeBot API (GRATIS y SIMPLE)"""
        try:
            # CallMeBot es una API gratuita para WhatsApp
            # Documentación: https://www.callmebot.com/blog/free-api-whatsapp-messages/
            
            # Limpiar número de teléfono
            telefono_limpio = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            # URL de CallMeBot
            url = "https://api.callmebot.com/whatsapp.php"
            
            params = {
                'phone': telefono_limpio,
                'text': mensaje,
                'apikey': self.config.callmebot_api_key
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def _enviar_con_callmebot_individual(self, destinatario, mensaje):
        """Envía mensaje usando la API Key individual del destinatario"""
        try:
            # Limpiar número de teléfono
            telefono_limpio = destinatario.telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            # URL de CallMeBot
            url = "https://api.callmebot.com/whatsapp.php"
            
            params = {
                'phone': telefono_limpio,
                'text': mensaje,
                'apikey': destinatario.callmebot_api_key
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def test_conexion(self):
        """Prueba la conexión con la API configurada"""
        if hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
            return self._test_callmebot()
        elif self.config.twilio_account_sid and self.config.twilio_auth_token:
            return self._test_twilio()
        elif self.config.whatsapp_business_token:
            return self._test_whatsapp_business()
        else:
            return False, "No hay configuración de API"
    
    def _test_twilio(self):
        """Prueba la conexión con Twilio"""
        try:
            client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
            # Obtener información de la cuenta para verificar credenciales
            account = client.api.accounts(self.config.twilio_account_sid).fetch()
            return True, f"Conexión exitosa. Cuenta: {account.friendly_name}"
        except Exception as e:
            return False, str(e)
    
    def _test_whatsapp_business(self):
        """Prueba la conexión con WhatsApp Business API"""
        try:
            url = f"https://graph.facebook.com/v18.0/{self.config.whatsapp_business_phone_id}"
            headers = {
                'Authorization': f'Bearer {self.config.whatsapp_business_token}',
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return True, "Conexión exitosa con WhatsApp Business API"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def _test_callmebot(self):
        """Prueba la conexión con CallMeBot API"""
        try:
            # CallMeBot no tiene endpoint de verificación, 
            # pero podemos verificar que la API key esté configurada
            if hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                return True, "CallMeBot API configurada correctamente"
            else:
                return False, "API Key de CallMeBot no configurada"
        except Exception as e:
            return False, str(e)
