from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from remesas.models import Remesa, Pago
from .services import WhatsAppService
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Remesa)
def detectar_cambio_estado_remesa(sender, instance, **kwargs):
    """Detecta cambios de estado en remesas"""
    if instance.pk:  # Solo si ya existe
        try:
            # Obtener el estado anterior
            remesa_anterior = Remesa.objects.get(pk=instance.pk)
            estado_anterior = remesa_anterior.estado
            
            # Guardar en el objeto para usar en post_save
            instance._estado_anterior = estado_anterior
            
        except Remesa.DoesNotExist:
            instance._estado_anterior = None


@receiver(post_save, sender=Remesa)
def manejar_notificaciones_remesa(sender, instance, created, **kwargs):
    """Maneja todas las notificaciones de remesas (creación y cambio de estado)"""
    try:
        whatsapp_service = WhatsAppService()
        
        if created:
            # Nueva remesa creada
            whatsapp_service.enviar_notificacion(
                tipo='remesa_nueva',
                remesa=instance
            )
            logger.info(f"Notificación enviada para nueva remesa: {instance.remesa_id}")
        else:
            # Verificar cambio de estado
            if hasattr(instance, '_estado_anterior'):
                estado_anterior = instance._estado_anterior
                
                # Solo notificar si realmente cambió el estado
                if estado_anterior != instance.estado:
                    whatsapp_service.enviar_notificacion(
                        tipo='remesa_estado',
                        remesa=instance,
                        estado_anterior=estado_anterior
                    )
                    logger.info(f"Notificación enviada para cambio de estado remesa: {instance.remesa_id} - {estado_anterior} -> {instance.estado}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de remesa: {e}")


@receiver(post_save, sender=Pago)
def notificar_pago(sender, instance, created, **kwargs):
    """Envía notificación cuando se crea un nuevo pago"""
    try:
        whatsapp_service = WhatsAppService()
        
        if created:
            # Nuevo pago creado
            whatsapp_service.enviar_notificacion(
                tipo='pago_nuevo',
                pago=instance
            )
            logger.info(f"Notificación enviada para nuevo pago: {instance.id}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de pago: {e}")


# Nota: Los pagos no tienen campo de estado en el modelo actual,
# pero se puede agregar si es necesario en el futuro
