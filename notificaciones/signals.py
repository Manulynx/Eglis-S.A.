from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from remesas.models import Remesa, Pago, PagoRemesa
from .services import WhatsAppService
from .internal import (
    notify_user_admins_and_domicilios,
    create_internal_notification,
    get_admin_users_queryset,
    get_domicilio_users_queryset_for_moneda,
)
from django.urls import reverse
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
            instance._fecha_edicion_anterior = remesa_anterior.fecha_edicion
            
            # Guardar en el objeto para usar en post_save
            instance._estado_anterior = estado_anterior
            
        except Remesa.DoesNotExist:
            instance._estado_anterior = None
            instance._fecha_edicion_anterior = None


@receiver(post_save, sender=Remesa)
def manejar_notificaciones_remesa(sender, instance, created, **kwargs):
    """Maneja todas las notificaciones de remesas (creación y cambio de estado)"""
    try:
        if bool(getattr(instance, '_skip_notifications', False)):
            return
        # Permite suprimir WhatsApp en operaciones automáticas (ej: cancelación por tiempo)
        skip_whatsapp = bool(getattr(instance, '_skip_whatsapp', False))
        whatsapp_service = None if skip_whatsapp else WhatsAppService()
        
        if created:
            # Nueva remesa creada
            if whatsapp_service:
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
                    tipo_estado = {
                        'confirmada': 'remesa_confirmada',
                        'completada': 'remesa_completada',
                        'cancelada': 'remesa_cancelada',
                    }.get(instance.estado, 'remesa_estado')

                    if whatsapp_service:
                        whatsapp_service.enviar_notificacion(
                            tipo=tipo_estado,
                            remesa=instance,
                            estado_anterior=estado_anterior
                        )
                        logger.info(f"Notificación enviada para cambio de estado remesa: {instance.remesa_id} - {estado_anterior} -> {instance.estado}")

            # Notificar edición (si cambió fecha_edicion)
            try:
                fecha_edicion_anterior = getattr(instance, '_fecha_edicion_anterior', None)
                if instance.fecha_edicion and instance.fecha_edicion != fecha_edicion_anterior:
                    if whatsapp_service:
                        whatsapp_service.enviar_notificacion(
                            tipo='remesa_editada',
                            remesa=instance,
                        )
                        logger.info(f"Notificación enviada para remesa editada: {instance.remesa_id}")
            except Exception as e:
                logger.error(f"Error enviando notificación de remesa editada: {e}")

        # Notificaciones internas
        try:
            if created:
                link = reverse('remesas:detalle_remesa', args=[instance.id])
                notify_user_admins_and_domicilios(
                    recipient=instance.gestor,
                    moneda=getattr(instance, 'moneda', None),
                    actor=instance.gestor,
                    verb='remesa_creada',
                    message=f"Nueva remesa {instance.remesa_id} creada",
                    link=link,
                    level='info',
                    content_object=instance,
                )
            else:
                if hasattr(instance, '_estado_anterior'):
                    estado_anterior = instance._estado_anterior
                    if estado_anterior != instance.estado:
                        link = reverse('remesas:detalle_remesa', args=[instance.id])
                        notify_user_admins_and_domicilios(
                            recipient=instance.gestor,
                            moneda=getattr(instance, 'moneda', None),
                            actor=getattr(instance, 'usuario_editor', None) or instance.gestor,
                            verb='remesa_estado',
                            message=(
                                f"Remesa {instance.remesa_id} cambió de {estado_anterior} a {instance.estado}"
                            ),
                            link=link,
                            level='warning' if instance.estado in ['cancelada'] else 'info',
                            content_object=instance,
                        )
        except Exception as e:
            logger.error(f"Error creando notificación interna de remesa: {e}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de remesa: {e}")


@receiver(pre_save, sender=Pago)
def detectar_cambio_estado_pago(sender, instance, **kwargs):
    """Detecta cambios de estado en pagos."""
    if instance.pk:
        try:
            pago_anterior = Pago.objects.get(pk=instance.pk)
            instance._estado_anterior = pago_anterior.estado
            instance._fecha_edicion_anterior = pago_anterior.fecha_edicion
        except Pago.DoesNotExist:
            instance._estado_anterior = None
            instance._fecha_edicion_anterior = None


@receiver(post_save, sender=Pago)
def notificar_pago(sender, instance, created, **kwargs):
    """Envía notificación cuando se crea un nuevo pago y cuando cambia de estado"""
    try:
        if bool(getattr(instance, '_skip_notifications', False)):
            return
        # Permite suprimir WhatsApp en operaciones automáticas (ej: cancelación por tiempo)
        skip_whatsapp = bool(getattr(instance, '_skip_whatsapp', False))
        whatsapp_service = None if skip_whatsapp else WhatsAppService()
        
        if created:
            # Nuevo pago creado
            if whatsapp_service:
                whatsapp_service.enviar_notificacion(
                    tipo='pago_nuevo',
                    pago=instance
                )
                logger.info(f"Notificación enviada para nuevo pago: {instance.id}")

        # Cambios de estado y ediciones
        if not created and hasattr(instance, '_estado_anterior'):
            estado_anterior = instance._estado_anterior
            if estado_anterior != instance.estado:
                tipo_estado = {
                    'confirmado': 'pago_confirmado',
                    'cancelado': 'pago_cancelado',
                }.get(instance.estado, 'pago_estado')

                if whatsapp_service:
                    whatsapp_service.enviar_notificacion(
                        tipo=tipo_estado,
                        pago=instance,
                        estado_anterior=estado_anterior,
                    )
                    logger.info(f"Notificación enviada para cambio de estado pago: {instance.pago_id} - {estado_anterior} -> {instance.estado}")

        if not created:
            try:
                fecha_edicion_anterior = getattr(instance, '_fecha_edicion_anterior', None)
                if instance.fecha_edicion and instance.fecha_edicion != fecha_edicion_anterior:
                    if whatsapp_service:
                        whatsapp_service.enviar_notificacion(
                            tipo='pago_editado',
                            pago=instance,
                        )
                        logger.info(f"Notificación enviada para pago editado: {instance.pago_id}")
            except Exception as e:
                logger.error(f"Error enviando notificación de pago editado: {e}")

        # Notificaciones internas
        try:
            link = reverse('remesas:detalle_pago', args=[instance.id])
            if created:
                notify_user_admins_and_domicilios(
                    recipient=instance.usuario,
                    moneda=getattr(instance, 'tipo_moneda', None),
                    actor=instance.usuario,
                    verb='pago_creado',
                    message=f"Pago {instance.pago_id} creado (estado: {instance.estado})",
                    link=link,
                    level='info',
                    content_object=instance,
                )
            else:
                if hasattr(instance, '_estado_anterior'):
                    estado_anterior = instance._estado_anterior
                    if estado_anterior != instance.estado:
                        notify_user_admins_and_domicilios(
                            recipient=instance.usuario,
                            moneda=getattr(instance, 'tipo_moneda', None),
                            actor=getattr(instance, 'usuario_editor', None) or instance.usuario,
                            verb='pago_estado',
                            message=f"Pago {instance.pago_id} cambió de {estado_anterior} a {instance.estado}",
                            link=link,
                            level='warning' if instance.estado in ['cancelado'] else 'info',
                            content_object=instance,
                        )
        except Exception as e:
            logger.error(f"Error creando notificación interna de pago: {e}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de pago: {e}")

@receiver(pre_save, sender=PagoRemesa)
def detectar_cambio_estado_pago_remesa(sender, instance, **kwargs):
    """Detecta cambios de estado en pagos de remesa."""
    if instance.pk:
        try:
            pago_anterior = PagoRemesa.objects.get(pk=instance.pk)
            instance._estado_anterior = pago_anterior.estado
            instance._fecha_edicion_anterior = pago_anterior.fecha_edicion
        except PagoRemesa.DoesNotExist:
            instance._estado_anterior = None
            instance._fecha_edicion_anterior = None


@receiver(post_save, sender=PagoRemesa)
def notificar_pago_remesa(sender, instance, created, **kwargs):
    """Envía notificación WhatsApp para pagos enlazados a remesas (como pagos generales)."""
    try:
        if bool(getattr(instance, '_skip_notifications', False)):
            return
        skip_whatsapp = bool(getattr(instance, '_skip_whatsapp', False))
        whatsapp_service = None if skip_whatsapp else WhatsAppService()

        if created and whatsapp_service:
            whatsapp_service.enviar_notificacion(
                tipo='pago_nuevo',
                pago=instance,
            )

        if not created and hasattr(instance, '_estado_anterior'):
            estado_anterior = instance._estado_anterior
            if estado_anterior != instance.estado:
                tipo_estado = {
                    'confirmado': 'pago_confirmado',
                    'cancelado': 'pago_cancelado',
                }.get(instance.estado, 'pago_estado')

                if whatsapp_service:
                    whatsapp_service.enviar_notificacion(
                        tipo=tipo_estado,
                        pago=instance,
                        estado_anterior=estado_anterior,
                    )

        if not created:
            try:
                fecha_edicion_anterior = getattr(instance, '_fecha_edicion_anterior', None)
                if instance.fecha_edicion and instance.fecha_edicion != fecha_edicion_anterior:
                    if whatsapp_service:
                        whatsapp_service.enviar_notificacion(
                            tipo='pago_editado',
                            pago=instance,
                        )
            except Exception as e:
                logger.error(f"Error enviando notificación de pago remesa editado: {e}")
    except Exception as e:
        logger.error(f"Error enviando notificación de pago remesa: {e}")


@receiver(post_save, sender=PagoRemesa)
def notificar_pago_remesa_interno(sender, instance, created, **kwargs):
    """Notificaciones internas para pagos enlazados a remesas."""
    try:
        if bool(getattr(instance, '_skip_notifications', False)):
            return
        remesa = getattr(instance, 'remesa', None)
        link = reverse('remesas:detalle_remesa', args=[remesa.id]) if remesa else reverse('remesas:registro_transacciones')

        # Notificar al usuario que creó/editó el pago, al gestor dueño de la remesa, a los admins,
        # y a domicilios cuya moneda asignada coincida.
        actor = getattr(instance, 'usuario_editor', None) or getattr(instance, 'usuario', None)
        recipients = []
        if getattr(instance, 'usuario', None):
            recipients.append(instance.usuario)
        if remesa and getattr(remesa, 'gestor', None):
            recipients.append(remesa.gestor)
        recipients.extend(list(get_admin_users_queryset()))

        moneda_notif = getattr(instance, 'tipo_moneda', None) or getattr(remesa, 'moneda', None)
        recipients.extend(list(get_domicilio_users_queryset_for_moneda(moneda_notif)))

        if created:
            msg = f"Pago {instance.pago_id} agregado a remesa {remesa.remesa_id if remesa else ''}".strip()
            create_internal_notification(
                recipients=recipients,
                actor=actor,
                verb='pago_remesa_creado',
                message=msg,
                link=link,
                level='info',
                content_object=instance,
            )
        else:
            if hasattr(instance, '_estado_anterior'):
                estado_anterior = instance._estado_anterior
                if estado_anterior != instance.estado:
                    msg = f"Pago {instance.pago_id} cambió de {estado_anterior} a {instance.estado}"
                    create_internal_notification(
                        recipients=recipients,
                        actor=actor,
                        verb='pago_remesa_estado',
                        message=msg,
                        link=link,
                        level='warning' if instance.estado in ['cancelado'] else 'info',
                        content_object=instance,
                    )
    except Exception as e:
        logger.error(f"Error creando notificación interna de pago remesa: {e}")
