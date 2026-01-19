import requests
import json
from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Servicio para enviar notificaciones por WhatsApp"""
    
    def __init__(self):
        self.config = ConfiguracionNotificacion.get_config()
    
    def enviar_notificacion(self, tipo, remesa=None, pago=None, estado_anterior=None, **kwargs):
        """
        Envía notificaciones a todos los destinatarios activos
        
        Args:
            tipo: Tipo de notificación ('remesa_nueva', 'remesa_estado', 'pago_nuevo', 'pago_estado', 'remesa_eliminada', 'pago_eliminado')
            remesa: Objeto Remesa (opcional)
            pago: Objeto Pago (opcional)
            estado_anterior: Estado anterior para cambios de estado
            **kwargs: Argumentos adicionales para tipos específicos
        """
        print(f"DEBUG: WhatsAppService.enviar_notificacion llamado con tipo='{tipo}', kwargs={kwargs}")
        
        # Verificar si las notificaciones están habilitadas globalmente
        if not self.config.activo:
            print(f"DEBUG: Notificaciones globalmente desactivadas")
            return
        
        # Verificar si debe enviar este tipo de notificación (flags globales)
        if tipo in [
            'remesa_nueva', 'remesa_estado', 'remesa_confirmada', 'remesa_completada', 'remesa_cancelada',
            'remesa_editada', 'remesa_eliminada'
        ] and not getattr(self.config, 'notificar_remesas', True):
            print(f"DEBUG: Notificaciones de remesas desactivadas")
            return
        if tipo in [
            'pago_nuevo', 'pago_estado', 'pago_confirmado', 'pago_cancelado', 'pago_editado', 'pago_eliminado'
        ] and not getattr(self.config, 'notificar_pagos', True):
            print(f"DEBUG: Notificaciones de pagos desactivadas")
            return
        if tipo in ['remesa_estado', 'remesa_confirmada', 'remesa_completada', 'remesa_cancelada', 'pago_estado', 'pago_confirmado', 'pago_cancelado'] and not getattr(self.config, 'notificar_cambios_estado', True):
            print(f"DEBUG: Notificaciones de cambios de estado desactivadas")
            return

        if tipo in ['remesa_editada', 'pago_editado'] and not getattr(self.config, 'notificar_ediciones', True):
            print("DEBUG: Notificaciones de ediciones desactivadas")
            return
        
        # Generar mensaje
        print(f"DEBUG: Generando mensaje para tipo '{tipo}'")
        mensaje = self._generar_mensaje(tipo, remesa, pago, estado_anterior, **kwargs)
        print(f"DEBUG: Mensaje generado: {mensaje[:100]}...")
        
        # Obtener destinatarios activos
        moneda_evento = self._resolver_moneda_evento(remesa=remesa, pago=pago)
        print(f"DEBUG: Obteniendo destinatarios para tipo '{tipo}'")
        destinatarios = self._obtener_destinatarios(tipo, moneda_evento)
        print(f"DEBUG: Destinatarios encontrados: {destinatarios.count()}")
        
        # Enviar a cada destinatario
        for destinatario in destinatarios:
            print(f"DEBUG: Enviando a {destinatario.nombre}")
            self._enviar_mensaje_individual(destinatario, mensaje, tipo, remesa, pago)
    
    def _generar_mensaje(self, tipo, remesa, pago, estado_anterior, **kwargs):
        """Genera el mensaje según el tipo de notificación"""
        
        if tipo == 'remesa_nueva' and remesa:
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"
            
            return f"""NUEVA REMESA

Destinatario: {remesa.moneda.nombre if remesa.moneda else 'Dólar Americano'}


Importe: ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}

Remitente: {remesa.receptor_nombre or 'N/A'}

Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}

ID: {remesa_id_formateado}{observaciones_texto}"""

        elif tipo == 'remesa_estado' and remesa:
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"
                
            return f"""CAMBIO DE ESTADO - REMESA

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {remesa.estado.title()}
Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo in ['remesa_confirmada', 'remesa_completada', 'remesa_cancelada'] and remesa:
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]

            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"

            titulo = {
                'remesa_confirmada': 'REMESA CONFIRMADA',
                'remesa_completada': 'REMESA COMPLETADA',
                'remesa_cancelada': 'REMESA CANCELADA',
            }.get(tipo, 'CAMBIO DE ESTADO - REMESA')

            return f"""{titulo}

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {remesa.estado.title()}
Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo == 'remesa_editada' and remesa:
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]

            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"

            editor = getattr(remesa, 'usuario_editor', None)
            editor_nombre = editor.get_full_name() if editor else 'N/A'

            return f"""REMESA EDITADA

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: ${remesa.importe} {remesa.moneda.codigo if remesa.moneda else 'USD'}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado: {remesa.get_estado_display()}
Editado por: {editor_nombre}
Fecha edición: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo == 'pago_nuevo' and pago:
            # Formatear el ID con # antes de los últimos 6 dígitos
            pago_id_formateado = str(pago.pago_id)
            if len(pago_id_formateado) >= 6:
                pago_id_formateado = pago_id_formateado[:-6] + '#' + pago_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if pago.observaciones and pago.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {pago.observaciones.strip()}"
            
            # Verificar el tipo de pago y generar mensaje específico
            if pago.tipo_pago == 'transferencia':
                # Mensaje para transferencia - formato simplificado
                mensaje = ""
                
                # Mostrar número de tarjeta PRIMERO (sin asteriscos)
                if hasattr(pago, 'tarjeta') and pago.tarjeta:
                    mensaje += f"{pago.tarjeta}\n\n"
                
                # Formato simplificado
                mensaje += f"""Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'} TRANSFERENCIA

Destinatario: {pago.destinatario}

Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}

{pago_id_formateado}{observaciones_texto}"""
                
            elif pago.tipo_pago == 'efectivo':
                # Mensaje para efectivo - formato simplificado
                mensaje = f"""NUEVO PAGO CREADO


Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'} EFECTIVO


Tipo: Efectivo
Destinatario: {pago.destinatario}
Telefono: {pago.telefono or 'N/A'}
CI: {pago.carnet_identidad or 'N/A'}
Direccion: {pago.direccion or 'N/A'}


Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
ID: {pago_id_formateado}{observaciones_texto}"""
            
            else:
                # Mensaje genérico para otros tipos
                mensaje = f"""NUEVO PAGO CREADO

ID: {pago_id_formateado}
Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}
Estado: {pago.get_estado_display()}

Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Tipo: {pago.get_tipo_pago_display()}
Destinatario: {pago.destinatario}
Telefono: {pago.telefono or 'N/A'}
CI: {pago.carnet_identidad or 'N/A'}
Direccion: {pago.direccion or 'N/A'}
Fecha: {pago.fecha_creacion.strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Nota: El balance se descontara cuando el pago sea confirmado.

Sistema EGLIS - Notificacion automatica"""
            
            return mensaje

        elif tipo == 'pago_estado' and pago:
            # Formatear el ID con # antes de los últimos 6 dígitos
            pago_id_formateado = str(pago.pago_id)
            if len(pago_id_formateado) >= 6:
                pago_id_formateado = pago_id_formateado[:-6] + '#' + pago_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if pago.observaciones and pago.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {pago.observaciones.strip()}"
                
            # Mensaje específico según el estado
            if pago.estado == 'confirmado':
                mensaje_estado = "El pago ha sido CONFIRMADO y el balance ha sido descontado."
            elif pago.estado == 'cancelado':
                mensaje_estado = "El pago ha sido CANCELADO. No se desconto balance."
            else:
                mensaje_estado = f"El pago cambio al estado: {pago.get_estado_display()}"
            
            return f"""CAMBIO DE ESTADO - PAGO

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}

Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {pago.get_estado_display()}

{mensaje_estado}

Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo in ['pago_confirmado', 'pago_cancelado'] and pago:
            # Reutilizar la plantilla de pago_estado (más explícita en título)
            pago_id_formateado = str(pago.pago_id)
            if len(pago_id_formateado) >= 6:
                pago_id_formateado = pago_id_formateado[:-6] + '#' + pago_id_formateado[-6:]

            observaciones_texto = ""
            if pago.observaciones and pago.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {pago.observaciones.strip()}"

            titulo = {
                'pago_confirmado': 'PAGO CONFIRMADO',
                'pago_cancelado': 'PAGO CANCELADO',
            }.get(tipo, 'CAMBIO DE ESTADO - PAGO')

            if pago.estado == 'confirmado':
                mensaje_estado = "El pago ha sido CONFIRMADO y el balance ha sido descontado."
            elif pago.estado == 'cancelado':
                mensaje_estado = "El pago ha sido CANCELADO. No se desconto balance."
            else:
                mensaje_estado = f"El pago cambio al estado: {pago.get_estado_display()}"

            return f"""{titulo}

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}

Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {pago.get_estado_display()}

{mensaje_estado}

Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo == 'pago_editado' and pago:
            pago_id_formateado = str(pago.pago_id)
            if len(pago_id_formateado) >= 6:
                pago_id_formateado = pago_id_formateado[:-6] + '#' + pago_id_formateado[-6:]

            observaciones_texto = ""
            if pago.observaciones and pago.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {pago.observaciones.strip()}"

            editor = getattr(pago, 'usuario_editor', None)
            editor_nombre = editor.get_full_name() if editor else 'N/A'

            return f"""PAGO EDITADO

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: ${pago.cantidad} {pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD'}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}
Estado: {pago.get_estado_display()}
Editado por: {editor_nombre}
Fecha edición: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica"""

        elif tipo == 'remesa_eliminada':
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id = str(kwargs.get('remesa_id', 'N/A'))
            if remesa_id != 'N/A' and len(remesa_id) >= 6:
                remesa_id_formateado = remesa_id[:-6] + '#' + remesa_id[-6:]
            else:
                remesa_id_formateado = remesa_id
                
            return f"""REMESA ELIMINADA

ID: {remesa_id_formateado}
Monto: {kwargs.get('monto', 'N/A')}
Administrador: {kwargs.get('admin_name', 'N/A')}
Balance actualizado: {kwargs.get('balance_change', 'N/A')}
Fecha eliminacion: {timezone.now().strftime('%d/%m/%Y %H:%M')}

ATENCION: Esta remesa ha sido eliminada del sistema y el balance ha sido ajustado automaticamente.

Sistema EGLIS - Notificacion automatica"""

        elif tipo == 'pago_eliminado':
            # Formatear el ID con # antes de los últimos 6 dígitos
            pago_id = str(kwargs.get('pago_id', 'N/A'))
            if pago_id != 'N/A' and len(pago_id) >= 6:
                pago_id_formateado = pago_id[:-6] + '#' + pago_id[-6:]
            else:
                pago_id_formateado = pago_id
                
            return f"""PAGO ELIMINADO

ID: {pago_id_formateado}
Monto: {kwargs.get('monto', 'N/A')}
Destinatario: {kwargs.get('destinatario', 'N/A')}
Administrador: {kwargs.get('admin_name', 'N/A')}
Balance actualizado: {kwargs.get('balance_change', 'N/A')}
Fecha eliminacion: {timezone.now().strftime('%d/%m/%Y %H:%M')}

ATENCION: Este pago ha sido eliminado del sistema y el balance ha sido ajustado automaticamente.

Sistema EGLIS - Notificacion automatica"""

        return "Notificacion del sistema EGLIS"
    
    def _resolver_moneda_evento(self, remesa=None, pago=None):
        """Intenta resolver la moneda usada en la operación para filtrar destinatarios."""
        moneda = None
        if remesa is not None:
            moneda = getattr(remesa, 'moneda', None)
        elif pago is not None:
            moneda = getattr(pago, 'tipo_moneda', None)

        if moneda is not None:
            return moneda

        # Fallback: si el modelo no trae moneda explícita, asumir USD si existe.
        try:
            from remesas.models import Moneda

            return Moneda.objects.filter(codigo='USD').first()
        except Exception:
            return None

    def _obtener_destinatarios(self, tipo, moneda=None):
        """Obtiene los destinatarios que deben recibir este tipo de notificación.

        Regla de monedas: si el destinatario no tiene monedas seleccionadas => recibe todo.
        Si tiene monedas seleccionadas => solo recibe si coincide la moneda de la operación.
        """
        destinatarios = DestinatarioNotificacion.objects.filter(activo=True)

        tipo_to_flag = {
            'remesa_nueva': 'recibir_remesa_nueva',
            'remesa_confirmada': 'recibir_remesa_confirmada',
            'remesa_completada': 'recibir_remesa_completada',
            'remesa_cancelada': 'recibir_remesa_cancelada',
            'remesa_editada': 'recibir_remesa_editada',
            'remesa_eliminada': 'recibir_remesa_eliminada',

            'pago_nuevo': 'recibir_pago_nuevo',
            'pago_confirmado': 'recibir_pago_confirmado',
            'pago_cancelado': 'recibir_pago_cancelado',
            'pago_editado': 'recibir_pago_editado',
            'pago_eliminado': 'recibir_pago_eliminado',
        }

        flag = tipo_to_flag.get(tipo)
        if flag:
            destinatarios = destinatarios.filter(**{flag: True})
        else:
            # Fallback retrocompatible (tipos antiguos o genéricos)
            if tipo in ['remesa_nueva', 'remesa_estado', 'remesa_eliminada']:
                destinatarios = destinatarios.filter(recibir_remesas=True)
            elif tipo in ['pago_nuevo', 'pago_estado', 'pago_eliminado']:
                destinatarios = destinatarios.filter(recibir_pagos=True)

            if tipo in ['remesa_estado', 'pago_estado']:
                destinatarios = destinatarios.filter(recibir_cambios_estado=True)

        if moneda is not None:
            destinatarios = destinatarios.filter(Q(monedas__isnull=True) | Q(monedas=moneda)).distinct()

        return destinatarios
    
    def _enviar_mensaje_individual(self, destinatario, mensaje, tipo, remesa, pago):
        """Envía mensaje a un destinatario específico"""
        print(f"DEBUG: _enviar_mensaje_individual a {destinatario.nombre}")
        
        # Crear log inicial
        log_data = {
            'tipo': tipo,
            'destinatario': destinatario,
            'mensaje': mensaje,
            'estado': 'pendiente'
        }
        
        # Agregar referencia según el tipo
        if remesa:
            log_data['remesa_id'] = remesa.remesa_id
        if pago:
            log_data['pago_id'] = pago.id
            
        log = LogNotificacion.objects.create(**log_data)
        print(f"DEBUG: Log creado con ID {log.id}")
        
        try:
            # Intentar envío según la configuración
            if destinatario.callmebot_api_key:
                print(f"DEBUG: Usando CallMeBot individual para {destinatario.nombre}")
                exito, respuesta = self._enviar_con_callmebot_individual(destinatario, mensaje)
            elif hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                print(f"DEBUG: Usando CallMeBot global para {destinatario.nombre}")
                exito, respuesta = self._enviar_con_callmebot_global(destinatario, mensaje)
            elif self.config.twilio_account_sid and self.config.twilio_auth_token:
                print(f"DEBUG: Usando Twilio para {destinatario.nombre}")
                exito, respuesta = self._enviar_con_twilio(destinatario, mensaje)
            elif self.config.whatsapp_business_token:
                print(f"DEBUG: Usando WhatsApp Business para {destinatario.nombre}")
                exito, respuesta = self._enviar_con_whatsapp_business(destinatario, mensaje)
            else:
                exito = False
                respuesta = "No hay configuración de API disponible"
            
            # Actualizar log
            if exito:
                log.estado = 'enviado'
                log.respuesta_api = respuesta
                print(f"DEBUG: Mensaje enviado exitosamente a {destinatario.nombre}")
            else:
                log.estado = 'fallido'
                log.respuesta_api = respuesta
                print(f"DEBUG: Error enviando mensaje a {destinatario.nombre}: {respuesta}")
                
        except Exception as e:
            log.estado = 'error'
            log.respuesta_api = str(e)
            print(f"DEBUG: Excepción enviando mensaje a {destinatario.nombre}: {e}")
        
        log.save()
    
    def _enviar_con_callmebot_global(self, destinatario, mensaje):
        """Envía mensaje usando la API Key global"""
        try:
            # Limpiar número de teléfono
            telefono_limpio = destinatario.telefono.replace('+', '').replace(' ', '').replace('-', '')
            
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
    
    def _enviar_con_twilio(self, destinatario, mensaje):
        """Envía mensaje usando Twilio"""
        try:
            client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
            
            message = client.messages.create(
                body=mensaje,
                from_=f'whatsapp:{self.config.twilio_from_number}',
                to=f'whatsapp:{destinatario.telefono}'
            )
            
            return True, f"Mensaje enviado con SID: {message.sid}"
            
        except Exception as e:
            return False, str(e)
    
    def _enviar_con_whatsapp_business(self, destinatario, mensaje):
        """Envía mensaje usando WhatsApp Business API"""
        try:
            url = f"https://graph.facebook.com/v18.0/{self.config.whatsapp_business_phone_id}/messages"
            headers = {
                'Authorization': f'Bearer {self.config.whatsapp_business_token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'to': destinatario.telefono.replace('+', ''),
                'type': 'text',
                'text': {'body': mensaje}
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def enviar_mensaje(self, telefono, mensaje):
        """
        Método público para enviar un mensaje directo a un número específico
        Usado para mensajes de prueba y envíos directos
        """
        try:
            # Buscar destinatario para usar su API Key individual si existe
            destinatario = DestinatarioNotificacion.objects.filter(telefono=telefono).first()
            
            if destinatario and destinatario.callmebot_api_key:
                # Usar API Key individual
                return self._enviar_con_callmebot_individual(destinatario, mensaje)
            elif hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                # Usar API Key global - crear objeto temporal para compatibilidad
                destinatario_temp = type('obj', (object,), {
                    'telefono': telefono,
                    'callmebot_api_key': self.config.callmebot_api_key
                })
                return self._enviar_con_callmebot_individual(destinatario_temp, mensaje)
            elif self.config.twilio_account_sid and self.config.twilio_auth_token:
                # Usar Twilio - crear objeto temporal
                destinatario_temp = type('obj', (object,), {'telefono': telefono})
                return self._enviar_con_twilio(destinatario_temp, mensaje)
            elif self.config.whatsapp_business_token:
                # Usar WhatsApp Business - crear objeto temporal
                destinatario_temp = type('obj', (object,), {'telefono': telefono})
                return self._enviar_con_whatsapp_business(destinatario_temp, mensaje)
            else:
                return False, "No hay configuración de API disponible"
                
        except Exception as e:
            return False, str(e)
    
    def test_conexion(self):
        """
        Prueba la conexión con las APIs configuradas
        """
        try:
            if hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                # Test básico de CallMeBot (solo verificar que la API key existe)
                return True, "CallMeBot API configurada correctamente"
            elif self.config.twilio_account_sid and self.config.twilio_auth_token:
                # Test de Twilio
                client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
                account = client.api.accounts(self.config.twilio_account_sid).fetch()
                return True, f"Twilio conectado: {account.friendly_name}"
            elif self.config.whatsapp_business_token:
                # Test básico de WhatsApp Business
                return True, "WhatsApp Business API configurada"
            else:
                return False, "No hay configuración de API disponible"
        except Exception as e:
            return False, str(e)
