import requests
from twilio.rest import Client
from django.utils import timezone
from django.db.models import Q
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Servicio para enviar notificaciones por WhatsApp"""

    SIGNATURE = "Sistema EGLIS - Notificacion automatica"
    
    def __init__(self):
        self.config = ConfiguracionNotificacion.get_config()

    @staticmethod
    def _format_money(value) -> str:
        """Formatea montos monetarios de forma consistente.

        Evita salidas tipo '1000.0'.
        Importante: no usa separador de miles (coma) para evitar que algunos
        gateways (p.ej. CallMeBot/WhatsApp) muestren/trunquen el prefijo.
        """
        if value is None:
            return "0.00"

        try:
            if isinstance(value, str):
                # Normaliza entradas comunes (p.ej. '1.234,56' o '1234,56')
                normalized = value.strip().replace(' ', '')
                if normalized.count(',') == 1 and normalized.count('.') >= 1:
                    # Asumir formato ES: miles '.' y decimal ','
                    normalized = normalized.replace('.', '').replace(',', '.')
                else:
                    normalized = normalized.replace(',', '.')
                amount = Decimal(normalized)
            else:
                amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return "0.00"

        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Si es entero, mostrar sin decimales (ej: 1000 en vez de 1000.00)
        if amount == amount.to_integral_value():
            return str(int(amount))

        return f"{amount:.2f}"

    @staticmethod
    def _moneda_codigo(moneda, default: str = 'USD') -> str:
        """Normaliza el código de moneda para mensajes.

        En la BD puede existir un "codigo" con espacios (p.ej. 'CUP TRANFE').
        Para notificaciones se usa el primer token ('CUP') para evitar ruido.
        """
        try:
            codigo = getattr(moneda, 'codigo', None)
        except Exception:
            codigo = None

        if not codigo:
            return default

        codigo = str(codigo).strip()
        if not codigo:
            return default

        return codigo.split()[0]
    
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
        # Verificar si las notificaciones están habilitadas globalmente
        if not self.config.activo:
            return
        
        # Verificar si debe enviar este tipo de notificación (flags globales)
        if tipo in [
            'remesa_nueva', 'remesa_estado', 'remesa_confirmada', 'remesa_completada', 'remesa_cancelada',
            'remesa_editada', 'remesa_eliminada'
        ] and not getattr(self.config, 'notificar_remesas', True):
            return
        if tipo in [
            'pago_nuevo', 'pago_estado', 'pago_confirmado', 'pago_cancelado', 'pago_editado', 'pago_eliminado'
        ] and not getattr(self.config, 'notificar_pagos', True):
            return
        if tipo in ['remesa_estado', 'remesa_confirmada', 'remesa_completada', 'remesa_cancelada', 'pago_estado', 'pago_confirmado', 'pago_cancelado'] and not getattr(self.config, 'notificar_cambios_estado', True):
            return

        if tipo in ['remesa_editada', 'pago_editado'] and not getattr(self.config, 'notificar_ediciones', True):
            return
        
        # Generar mensaje
        mensaje = self._generar_mensaje(tipo, remesa, pago, estado_anterior, **kwargs)
        
        # Obtener destinatarios activos
        moneda_evento = self._resolver_moneda_evento(remesa=remesa, pago=pago, moneda=kwargs.get('moneda'))
        destinatarios = self._obtener_destinatarios(tipo, moneda_evento)
        
        # Enviar a cada destinatario
        for destinatario in destinatarios:
            self._enviar_mensaje_individual(destinatario, mensaje, tipo, remesa, pago)

    @staticmethod
    def _limpiar_telefono(telefono: str) -> str:
        """Normaliza teléfono para CallMeBot.

        - Acepta formatos con '+', espacios, guiones.
        - Devuelve solo dígitos (CallMeBot espera sin '+').
        """
        if not telefono:
            return ''
        return re.sub(r'\D+', '', str(telefono))

    @staticmethod
    def _telefono_normalizado(telefono: str) -> str:
        """Normaliza teléfono para comparar en BD."""
        if not telefono:
            return ''
        return re.sub(r'\D+', '', str(telefono))

    @staticmethod
    def _normalizar_texto_callmebot(mensaje: str) -> str:
        """Normaliza texto para CallMeBot.

        Observación: en algunos casos CallMeBot/stack intermedio no maneja bien caracteres con
        tilde/diacríticos y pueden "desaparecer". Para evitar omisiones, se aplica:
        - Normalización NFC
        - Remoción de marcas diacríticas (á->a, ñ->n)

        Nota: esto solo se usa para CallMeBot; Twilio/WhatsApp Business mantienen Unicode.
        """
        if mensaje is None:
            return ''

        text = str(mensaje).replace('\r\n', '\n').replace('\r', '\n')
        text = unicodedata.normalize('NFC', text)

        # Quitar diacríticos (Mn) para maximizar compatibilidad.
        decomposed = unicodedata.normalize('NFKD', text)
        text = ''.join(ch for ch in decomposed if unicodedata.category(ch) != 'Mn')

        return text

    @staticmethod
    def _mensaje_callmebot_seguro(mensaje: str, limite: int = 1200) -> str:
        """Recorta el texto para CallMeBot evitando truncados dentro del URL-encoding.

        CallMeBot usa endpoint tipo querystring. Si algún proxy/servidor corta una URL demasiado
        larga, puede truncar en medio de un %XX (o de una secuencia multibyte como %C3%A1) y
        aparentar "letras omitidas". Por eso el límite se aplica sobre el texto URL-encoded.
        """
        if mensaje is None:
            return ''

        mensaje = WhatsAppService._normalizar_texto_callmebot(mensaje)

        encoded = quote_plus(mensaje, safe='', encoding='utf-8', errors='strict')
        if len(encoded) <= limite:
            return mensaje

        suffix = '...'
        suffix_encoded_len = len(quote_plus(suffix, safe='', encoding='utf-8', errors='strict'))
        target = max(1, limite - suffix_encoded_len)

        # Buscar por bisección el prefijo más largo cuyo URL-encoding entre en `target`.
        lo = 0
        hi = len(mensaje)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(quote_plus(mensaje[:mid], safe='', encoding='utf-8', errors='strict')) <= target:
                lo = mid
            else:
                hi = mid - 1

        return mensaje[:lo] + suffix

    @classmethod
    def _with_signature(cls, mensaje: str) -> str:
        """Unifica la firma final para todos los mensajes enviados por WhatsApp."""
        if mensaje is None:
            mensaje = ''

        text = str(mensaje).rstrip()
        if not text:
            return cls.SIGNATURE

        lines = text.splitlines()

        # Eliminar líneas vacías al final
        while lines and not lines[-1].strip():
            lines.pop()

        # Si ya termina con la firma exacta, dejarlo tal cual.
        if lines and lines[-1].strip().lower() == cls.SIGNATURE.lower():
            return '\n'.join(lines)

        # Si termina con variantes antiguas, reemplazar.
        if lines and lines[-1].strip().lower() in {
            'sistema eglis',
            'notificacion del sistema eglis',
        }:
            lines.pop()

        base = '\n'.join(lines).rstrip()
        return base + '\n\n' + cls.SIGNATURE
    
    def _generar_mensaje(self, tipo, remesa, pago, estado_anterior, **kwargs):
        """Genera el mensaje según el tipo de notificación"""
        
        if tipo == 'remesa_nueva' and remesa:
            # WhatsApp: aviso a administradores/destinatarios de que se creó una REMESA nueva.
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"
            
            return self._with_signature(f"""NUEVA REMESA

Moneda: {(remesa.moneda.nombre or '').strip() if remesa.moneda else 'Dólar Americano'}


Importe: {self._format_money(remesa.importe)} {self._moneda_codigo(remesa.moneda)}

Remitente: {remesa.receptor_nombre or 'N/A'}

Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}

ID: {remesa_id_formateado}{observaciones_texto}""")

        elif tipo == 'remesa_estado' and remesa:
            # WhatsApp: aviso de CAMBIO DE ESTADO genérico en una remesa.
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]
            
            # Agregar observaciones si existen
            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"
                
            return self._with_signature(f"""CAMBIO DE ESTADO - REMESA

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: {self._format_money(remesa.importe)} {self._moneda_codigo(remesa.moneda)}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {remesa.estado.title()}
Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo in ['remesa_confirmada', 'remesa_completada', 'remesa_cancelada'] and remesa:
            # WhatsApp: aviso explícito de CONFIRMACIÓN / COMPLETADO / CANCELACIÓN de una remesa.
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

            return self._with_signature(f"""{titulo}

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: {self._format_money(remesa.importe)} {self._moneda_codigo(remesa.moneda)}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {remesa.estado.title()}
Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo == 'remesa_editada' and remesa:
            # WhatsApp: aviso de que una remesa fue EDITADA (cambio de datos, no necesariamente de estado).
            remesa_id_formateado = remesa.remesa_id
            if len(remesa_id_formateado) >= 6:
                remesa_id_formateado = remesa_id_formateado[:-6] + '#' + remesa_id_formateado[-6:]

            observaciones_texto = ""
            if remesa.observaciones and remesa.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {remesa.observaciones.strip()}"

            editor = getattr(remesa, 'usuario_editor', None)
            editor_nombre = editor.get_full_name() if editor else 'N/A'

            return self._with_signature(f"""REMESA EDITADA

ID: {remesa_id_formateado}
Gestor: {remesa.gestor.get_full_name() if remesa.gestor else 'N/A'}
Importe: {self._format_money(remesa.importe)} {self._moneda_codigo(remesa.moneda)}
Receptor: {remesa.receptor_nombre or 'N/A'}
Estado: {remesa.get_estado_display()}
Editado por: {editor_nombre}
Fecha edición: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo == 'pago_nuevo' and pago:
            # WhatsApp: aviso de creación de un PAGO nuevo (varía el cuerpo según tipo_pago).
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
                # WhatsApp: alta de pago por TRANSFERENCIA (muestra tarjeta primero y formato compacto).
                # Mensaje para transferencia - formato simplificado
                mensaje = ""
                
                # Mostrar número de tarjeta PRIMERO (sin asteriscos)
                if hasattr(pago, 'tarjeta') and pago.tarjeta:
                    mensaje += f"{pago.tarjeta}\n\n"
                
                # Formato simplificado
                mensaje += f"""Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)} TRANSFERENCIA

Destinatario: {pago.destinatario}

Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}

ID: {pago_id_formateado}{observaciones_texto}"""
                
            elif pago.tipo_pago == 'efectivo':
                # WhatsApp: alta de pago en EFECTIVO (incluye datos de contacto/dirección/CI).
                # Mensaje para efectivo - formato simplificado
                mensaje = f"""NUEVO PAGO CREADO


Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)} EFECTIVO


Tipo: Efectivo
Destinatario: {pago.destinatario}
Telefono: {pago.telefono or 'N/A'}
CI: {pago.carnet_identidad or 'N/A'}
Direccion: {pago.direccion or 'N/A'}


Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
ID: {pago_id_formateado}{observaciones_texto}"""
            
            else:
                # WhatsApp: alta de pago OTROS (plantilla genérica con nota de balance).
                # Mensaje genérico para otros tipos
                mensaje = f"""NUEVO PAGO CREADO

ID: {pago_id_formateado}
Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)}
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
            
            return self._with_signature(mensaje)

        elif tipo == 'pago_estado' and pago:
            # WhatsApp: aviso de CAMBIO DE ESTADO en un pago (usa estado actual para el texto).
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
            
            return self._with_signature(f"""CAMBIO DE ESTADO - PAGO

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}

Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {pago.get_estado_display()}

{mensaje_estado}

Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo in ['pago_confirmado', 'pago_cancelado'] and pago:
            # WhatsApp: aviso explícito de CONFIRMACIÓN / CANCELACIÓN de pago (título más directo).
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

            return self._with_signature(f"""{titulo}

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}

Estado anterior: {estado_anterior or 'N/A'}
Estado actual: {pago.get_estado_display()}

{mensaje_estado}

Actualizado: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo == 'pago_editado' and pago:
            # WhatsApp: aviso de que un pago fue EDITADO (cambio de datos).
            pago_id_formateado = str(pago.pago_id)
            if len(pago_id_formateado) >= 6:
                pago_id_formateado = pago_id_formateado[:-6] + '#' + pago_id_formateado[-6:]

            observaciones_texto = ""
            if pago.observaciones and pago.observaciones.strip():
                observaciones_texto = f"\n\nObservaciones: {pago.observaciones.strip()}"

            editor = getattr(pago, 'usuario_editor', None)
            editor_nombre = editor.get_full_name() if editor else 'N/A'

            return self._with_signature(f"""PAGO EDITADO

ID Pago: {pago_id_formateado}
Gestor: {pago.usuario.get_full_name() if pago.usuario else 'N/A'}
Cantidad: {self._format_money(pago.cantidad)} {self._moneda_codigo(pago.tipo_moneda)}
Destinatario: {pago.destinatario}
Tipo: {pago.get_tipo_pago_display()}
Estado: {pago.get_estado_display()}
Editado por: {editor_nombre}
Fecha edición: {timezone.now().strftime('%d/%m/%Y %H:%M')}{observaciones_texto}

Sistema EGLIS - Notificacion automatica""")

        elif tipo == 'remesa_eliminada':
            # WhatsApp: aviso de que una remesa fue ELIMINADA (incluye ajustes de balance si aplica).
            # Formatear el ID con # antes de los últimos 6 dígitos
            remesa_id = str(kwargs.get('remesa_id', 'N/A'))
            if remesa_id != 'N/A' and len(remesa_id) >= 6:
                remesa_id_formateado = remesa_id[:-6] + '#' + remesa_id[-6:]
            else:
                remesa_id_formateado = remesa_id
                
            return self._with_signature(f"""REMESA ELIMINADA

ID: {remesa_id_formateado}
Monto: {kwargs.get('monto', 'N/A')}
Administrador: {kwargs.get('admin_name', 'N/A')}
Balance actualizado: {kwargs.get('balance_change', 'N/A')}
Fecha eliminacion: {timezone.now().strftime('%d/%m/%Y %H:%M')}

ATENCION: Esta remesa ha sido eliminada del sistema y el balance ha sido ajustado automaticamente.

Sistema EGLIS - Notificacion automatica""")

        elif tipo == 'pago_eliminado':
            # WhatsApp: aviso de que un pago fue ELIMINADO (incluye ajustes de balance si aplica).
            # Formatear el ID con # antes de los últimos 6 dígitos
            pago_id = str(kwargs.get('pago_id', 'N/A'))
            if pago_id != 'N/A' and len(pago_id) >= 6:
                pago_id_formateado = pago_id[:-6] + '#' + pago_id[-6:]
            else:
                pago_id_formateado = pago_id
                
            return self._with_signature(f"""PAGO ELIMINADO

ID: {pago_id_formateado}
Monto: {kwargs.get('monto', 'N/A')}
Destinatario: {kwargs.get('destinatario', 'N/A')}
Administrador: {kwargs.get('admin_name', 'N/A')}
Balance actualizado: {kwargs.get('balance_change', 'N/A')}
Fecha eliminacion: {timezone.now().strftime('%d/%m/%Y %H:%M')}

ATENCION: Este pago ha sido eliminado del sistema y el balance ha sido ajustado automaticamente.

Sistema EGLIS - Notificacion automatica""")

        if tipo == 'alerta_fondo_bajo':
            # WhatsApp: alerta operativa cuando el fondo de caja cae por debajo del mínimo configurado.
            moneda = kwargs.get('moneda')
            codigo = getattr(moneda, 'codigo', None) if moneda is not None else kwargs.get('codigo', 'N/A')
            fondo_txt = self._format_money(getattr(moneda, 'fondo_caja', None) if moneda is not None else kwargs.get('fondo'))
            minimo_txt = self._format_money(getattr(moneda, 'alerta_fondo_minimo', None) if moneda is not None else kwargs.get('minimo'))

            return self._with_signature(
                (
                "ALERTA - FONDO DE CAJA BAJO\n\n"
                f"Moneda: {codigo}\n"
                f"Fondo actual: {fondo_txt}\n"
                f"Mínimo: {minimo_txt}\n\n"
                f"Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}\n"
                "Sistema EGLIS"
                )
            )

        # WhatsApp: mensaje por defecto si se invoca un tipo desconocido.
        return self._with_signature("Notificacion del sistema EGLIS")
    
    def _resolver_moneda_evento(self, remesa=None, pago=None, moneda=None):
        """Intenta resolver la moneda usada en la operación para filtrar destinatarios."""
        if moneda is None:
            if remesa is not None:
                moneda = getattr(remesa, 'moneda', None)
            elif pago is not None:
                moneda = getattr(pago, 'tipo_moneda', None)

        if moneda is not None:
            # Normalizar códigos defectuosos con espacios (p.ej. 'CUP TRANFE')
            # a un código canónico ('CUP') si existe en la tabla de Monedas.
            codigo_normalizado = self._moneda_codigo(moneda, default='')
            try:
                codigo_actual = (getattr(moneda, 'codigo', '') or '').strip()
            except Exception:
                codigo_actual = ''

            if codigo_normalizado and codigo_actual and codigo_normalizado != codigo_actual:
                try:
                    from remesas.models import Moneda

                    moneda_normalizada = Moneda.objects.filter(codigo=codigo_normalizado).first()
                    if moneda_normalizada is not None:
                        return moneda_normalizada
                except Exception:
                    pass

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

            'alerta_fondo_bajo': 'recibir_alerta_fondo_bajo',
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
        log_data = {
            'tipo': tipo,
            'destinatario': destinatario,
            'mensaje': mensaje,
            'estado': 'pendiente'
        }

        if remesa:
            log_data['remesa_id'] = remesa.remesa_id
        if pago:
            log_data['pago_id'] = pago.id

        log = LogNotificacion.objects.create(**log_data)

        try:
            if destinatario.callmebot_api_key:
                exito, respuesta = self._enviar_con_callmebot_individual(destinatario, mensaje)
            elif hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                exito, respuesta = self._enviar_con_callmebot_global(destinatario, mensaje)
            elif self.config.twilio_account_sid and self.config.twilio_auth_token:
                exito, respuesta = self._enviar_con_twilio(destinatario, mensaje)
            elif self.config.whatsapp_business_token:
                exito, respuesta = self._enviar_con_whatsapp_business(destinatario, mensaje)
            else:
                exito = False
                respuesta = "No hay configuración de API disponible"

            log.fecha_envio = timezone.now()
            if exito:
                log.estado = 'enviado'
                log.respuesta_api = respuesta
            else:
                log.estado = 'fallido'
                log.respuesta_api = respuesta
                log.error_mensaje = respuesta
                
        except Exception as e:
            log.estado = 'fallido'
            log.respuesta_api = str(e)
            log.error_mensaje = str(e)
            log.fecha_envio = timezone.now()
            logger.exception("Excepción enviando WhatsApp (%s) a %s", tipo, getattr(destinatario, 'telefono', ''))

        log.save()

    def _enviar_con_callmebot_global(self, destinatario, mensaje):
        """Envía mensaje usando la API Key global"""
        try:
            telefono_limpio = self._limpiar_telefono(destinatario.telefono)
            if not telefono_limpio:
                return False, 'Teléfono inválido o vacío para CallMeBot'
            mensaje = self._mensaje_callmebot_seguro(mensaje)

            url = "https://api.callmebot.com/whatsapp.php"

            params = {
                'phone': telefono_limpio,
                'text': mensaje,
                'apikey': self.config.callmebot_api_key
            }

            # CallMeBot funciona vía querystring; algunos despliegues ignoran el body en POST.
            response = requests.get(url, params=params, timeout=(5, 15))

            if response.status_code == 200:
                return True, response.text

            return False, f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, str(e)
    
    def _enviar_con_callmebot_individual(self, destinatario, mensaje):
        """Envía mensaje usando la API Key individual del destinatario"""
        try:
            telefono_limpio = self._limpiar_telefono(destinatario.telefono)
            if not telefono_limpio:
                return False, 'Teléfono inválido o vacío para CallMeBot'
            mensaje = self._mensaje_callmebot_seguro(mensaje)
            
            # URL de CallMeBot
            url = "https://api.callmebot.com/whatsapp.php"
            
            params = {
                'phone': telefono_limpio,
                'text': mensaje,
                'apikey': destinatario.callmebot_api_key
            }

            # CallMeBot funciona vía querystring; algunos despliegues ignoran el body en POST.
            response = requests.get(url, params=params, timeout=(5, 15))

            if response.status_code == 200:
                return True, response.text

            return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def _enviar_con_twilio(self, destinatario, mensaje):
        """Envía mensaje usando Twilio"""
        try:
            client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)

            from_number = getattr(self.config, 'twilio_phone_number', None) or getattr(self.config, 'twilio_from_number', None)
            if not from_number:
                return False, 'Twilio no configurado: falta twilio_phone_number'
            
            message = client.messages.create(
                body=mensaje,
                from_=f'whatsapp:{from_number}',
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
                'to': self._limpiar_telefono(destinatario.telefono),
                'type': 'text',
                'text': {'body': mensaje}
            }
            

            response = requests.post(url, headers=headers, json=data, timeout=(5, 15))

            if 200 <= response.status_code < 300:
                return True, response.text

            return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def enviar_mensaje(self, telefono, mensaje):
        """
        Método público para enviar un mensaje directo a un número específico
        Usado para mensajes de prueba y envíos directos
        """
        try:
            # Buscar destinatario para usar su API Key individual
            destinatario = DestinatarioNotificacion.objects.filter(telefono=telefono).first()
            if not destinatario:
                telefono_norm = self._telefono_normalizado(telefono)
                for cand in DestinatarioNotificacion.objects.all():
                    if self._telefono_normalizado(cand.telefono) == telefono_norm:
                        destinatario = cand
                        break

            if destinatario and destinatario.callmebot_api_key:
                return self._enviar_con_callmebot_individual(destinatario, mensaje)

            if hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                destinatario_temp = type('obj', (object,), {
                    'telefono': telefono,
                    'callmebot_api_key': self.config.callmebot_api_key
                })
                return self._enviar_con_callmebot_individual(destinatario_temp, mensaje)

            if self.config.twilio_account_sid and self.config.twilio_auth_token:
                destinatario_temp = type('obj', (object,), {'telefono': telefono})
                return self._enviar_con_twilio(destinatario_temp, mensaje)

            if self.config.whatsapp_business_token:
                destinatario_temp = type('obj', (object,), {'telefono': telefono})
                return self._enviar_con_whatsapp_business(destinatario_temp, mensaje)

            return False, "No hay configuración de API disponible"
                
        except Exception as e:
            return False, str(e)
    
    def test_conexion(self):
        """
        Prueba la conexión con las APIs configuradas
        """
        try:
            existe_destinatario = DestinatarioNotificacion.objects.filter(
                activo=True,
                callmebot_api_key__isnull=False,
            ).exclude(callmebot_api_key='').exists()

            if existe_destinatario:
                return True, "CallMeBot configurado en destinatarios"

            if hasattr(self.config, 'callmebot_api_key') and self.config.callmebot_api_key:
                return True, "CallMeBot API configurada correctamente"

            if self.config.twilio_account_sid and self.config.twilio_auth_token:
                client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
                account = client.api.accounts(self.config.twilio_account_sid).fetch()
                return True, f"Twilio conectado: {account.friendly_name}"

            if self.config.whatsapp_business_token:
                return True, "WhatsApp Business API configurada"

            return False, "No hay configuración de API disponible"
        except Exception as e:
            return False, str(e)
