from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.urls import reverse
from django.utils import timezone
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion, NotificacionInterna
from .services import WhatsAppService
from .forms import ConfiguracionForm, DestinatarioForm


@staff_member_required
def configuracion_notificaciones(request):
    """Vista para configurar las notificaciones de WhatsApp"""
    config = ConfiguracionNotificacion.get_config()
    
    if request.method == 'POST':
        form = ConfiguracionForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada correctamente')
            return redirect('notificaciones:configuracion')
    else:
        form = ConfiguracionForm(instance=config)
    
    return render(request, 'notificaciones/configuracion.html', {
        'form': form,
        'config': config
    })


@staff_member_required
def destinatarios_notificaciones(request):
    """Vista para gestionar destinatarios de notificaciones"""
    destinatarios = DestinatarioNotificacion.objects.all().order_by('nombre')
    
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            telefono = request.POST.get('telefono')
            callmebot_api_key = request.POST.get('callmebot_api_key', '')
            activo = request.POST.get('activo') == 'true'
            recibir_remesas = request.POST.get('recibir_remesas') == 'true'
            recibir_pagos = request.POST.get('recibir_pagos') == 'true'
            recibir_cambios_estado = request.POST.get('recibir_cambios_estado') == 'true'
            
            if not nombre or not telefono:
                return JsonResponse({
                    'success': False,
                    'message': 'Nombre y teléfono son requeridos'
                })
            
            # Verificar si el teléfono ya existe
            if DestinatarioNotificacion.objects.filter(telefono=telefono).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Ya existe un destinatario con el teléfono {telefono}'
                })
            
            destinatario = DestinatarioNotificacion.objects.create(
                nombre=nombre,
                telefono=telefono,
                callmebot_api_key=callmebot_api_key if callmebot_api_key else None,
                activo=activo,
                recibir_remesas=recibir_remesas,
                recibir_pagos=recibir_pagos,
                recibir_cambios_estado=recibir_cambios_estado
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Destinatario {nombre} agregado correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al agregar destinatario: {str(e)}'
            })
    else:
        form = DestinatarioForm()
    
    return render(request, 'notificaciones/destinatarios.html', {
        'destinatarios': destinatarios,
        'form': form
    })


@staff_member_required
def editar_destinatario(request, destinatario_id):
    """Vista para editar un destinatario"""
    destinatario = get_object_or_404(DestinatarioNotificacion, id=destinatario_id)
    
    if request.method == 'POST':
        try:
            destinatario.nombre = request.POST.get('nombre')
            destinatario.telefono = request.POST.get('telefono')
            callmebot_api_key = request.POST.get('callmebot_api_key', '')
            destinatario.callmebot_api_key = callmebot_api_key if callmebot_api_key else None
            destinatario.activo = request.POST.get('activo') == 'true'
            destinatario.recibir_remesas = request.POST.get('recibir_remesas') == 'true'
            destinatario.recibir_pagos = request.POST.get('recibir_pagos') == 'true'
            destinatario.recibir_cambios_estado = request.POST.get('recibir_cambios_estado') == 'true'
            
            if not destinatario.nombre or not destinatario.telefono:
                return JsonResponse({
                    'success': False,
                    'message': 'Nombre y teléfono son requeridos'
                })
            
            # Verificar si el teléfono ya existe (excluyendo el actual)
            if DestinatarioNotificacion.objects.filter(
                telefono=destinatario.telefono
            ).exclude(id=destinatario.id).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Ya existe otro destinatario con el teléfono {destinatario.telefono}'
                })
            
            destinatario.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Destinatario {destinatario.nombre} actualizado correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al actualizar destinatario: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@staff_member_required
def toggle_estado_destinatario(request, destinatario_id):
    """Vista para cambiar el estado de un destinatario"""
    if request.method == 'POST':
        try:
            destinatario = get_object_or_404(DestinatarioNotificacion, id=destinatario_id)
            destinatario.activo = not destinatario.activo
            destinatario.save()
            
            estado_texto = 'activado' if destinatario.activo else 'desactivado'
            
            return JsonResponse({
                'success': True,
                'message': f'Destinatario {destinatario.nombre} {estado_texto} correctamente',
                'nuevo_estado': destinatario.activo
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al cambiar estado: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@staff_member_required
def eliminar_destinatario(request, destinatario_id):
    """Vista para eliminar un destinatario"""
    if request.method == 'POST':
        try:
            destinatario = get_object_or_404(DestinatarioNotificacion, id=destinatario_id)
            nombre = destinatario.nombre
            destinatario.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Destinatario {nombre} eliminado correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al eliminar destinatario: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@staff_member_required
def enviar_test_destinatario(request, destinatario_id):
    """Vista para enviar mensaje de prueba a un destinatario"""
    if request.method == 'POST':
        try:
            destinatario = get_object_or_404(DestinatarioNotificacion, id=destinatario_id)
            
            if not destinatario.activo:
                return JsonResponse({
                    'success': False,
                    'message': f'El destinatario {destinatario.nombre} está inactivo'
                })
            
            # Verificar que hay alguna configuración disponible
            config = ConfiguracionNotificacion.get_config()
            has_global_config = (
                config.callmebot_api_key or 
                (config.twilio_account_sid and config.twilio_auth_token) or 
                config.whatsapp_business_token
            )
            
            if not destinatario.callmebot_api_key and not has_global_config:
                return JsonResponse({
                    'success': False,
                    'message': 'No hay configuración de API disponible. Configure CallMeBot API Key individual o global.'
                })
            
            # Crear servicio de WhatsApp
            whatsapp_service = WhatsAppService()
            
            # Mensaje de prueba
            mensaje = f"""🔔 *Mensaje de Prueba - Eglis*

Hola {destinatario.nombre},

Este es un mensaje de prueba del sistema de notificaciones.

📅 Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}
✅ Tu número está configurado correctamente.

_Sistema de gestión de remesas Eglis_"""
            
            # Enviar mensaje usando el método público
            exito, respuesta = whatsapp_service.enviar_mensaje(destinatario.telefono, mensaje)
            
            if exito:
                # Registrar en log
                LogNotificacion.objects.create(
                    tipo='TEST',
                    destinatario=destinatario,
                    mensaje=mensaje,
                    estado='enviado',
                    respuesta_api=respuesta
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Mensaje de prueba enviado correctamente a {destinatario.nombre}'
                })
            else:
                # Registrar error en log
                LogNotificacion.objects.create(
                    tipo='TEST',
                    destinatario=destinatario,
                    mensaje=mensaje,
                    estado='fallido',
                    respuesta_api=respuesta,
                    error_mensaje=respuesta
                )
                
                return JsonResponse({
                    'success': False,
                    'message': f'Error al enviar mensaje: {respuesta}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al enviar mensaje de prueba: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
def internas(request):
    """Inbox/página de notificaciones internas."""
    return render(request, 'notificaciones/internas.html', {})


@login_required
@require_GET
def internas_api_unread_count(request):
    count = NotificacionInterna.objects.filter(recipient=request.user, read_at__isnull=True).count()
    return JsonResponse({'count': count})


def _serialize_notificacion(request, n: NotificacionInterna):
    created_local = timezone.localtime(n.created_at)
    return {
        'id': n.id,
        'message': n.message,
        'level': n.level,
        'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'created_at_human': created_local.strftime('%d/%m/%Y %H:%M'),
        'mark_read_url': reverse('notificaciones:internas_api_mark_read', args=[n.id]),
    }


@login_required
@require_GET
def internas_api_list(request):
    try:
        limit = int(request.GET.get('limit', '10'))
        offset = int(request.GET.get('offset', '0'))
    except ValueError:
        limit = 10
        offset = 0

    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    qs = NotificacionInterna.objects.filter(recipient=request.user).order_by('-created_at')
    total_unread = qs.filter(read_at__isnull=True).count()
    items = list(qs[offset:offset + limit])

    return JsonResponse({
        'unread_count': total_unread,
        'notifications': [_serialize_notificacion(request, n) for n in items],
    })


@login_required
@require_POST
def internas_api_mark_read(request, notificacion_id: int):
    notificacion = get_object_or_404(NotificacionInterna, id=notificacion_id, recipient=request.user)
    notificacion.mark_read()
    unread = NotificacionInterna.objects.filter(recipient=request.user, read_at__isnull=True).count()
    return JsonResponse({'success': True, 'unread_count': unread})


@login_required
@require_POST
def internas_api_mark_all_read(request):
    now = timezone.now()
    NotificacionInterna.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=now)
    return JsonResponse({'success': True, 'unread_count': 0})


@staff_member_required
def logs_notificaciones(request):
    """Vista para ver el historial de notificaciones"""
    logs = LogNotificacion.objects.all()[:100]  # Últimas 100 notificaciones
    
    return render(request, 'notificaciones/logs.html', {
        'logs': logs
    })


@staff_member_required
def test_conexion(request):
    """Prueba la conexión con la API de WhatsApp"""
    whatsapp_service = WhatsAppService()
    success, message = whatsapp_service.test_conexion()
    
    return JsonResponse({
        'success': success,
        'message': message
    })


@staff_member_required
def enviar_test(request):
    """Envía un mensaje de prueba"""
    if request.method == 'POST':
        telefono = request.POST.get('telefono')
        if telefono:
            whatsapp_service = WhatsAppService()
            
            # Crear un mensaje de prueba
            mensaje = """🧪 *MENSAJE DE PRUEBA*

Este es un mensaje de prueba del sistema de notificaciones EGLIS.

Si recibes este mensaje, la configuración está funcionando correctamente.

📅 Enviado: {fecha}

Sistema EGLIS - Notificación de prueba""".format(
                fecha=timezone.now().strftime('%d/%m/%Y %H:%M')
            )
            
            # Enviar directamente sin usar signals
            try:
                config = whatsapp_service.config
                if config.twilio_account_sid and config.twilio_auth_token:
                    success, response = whatsapp_service._enviar_con_twilio(telefono, mensaje)
                elif config.whatsapp_business_token:
                    success, response = whatsapp_service._enviar_con_whatsapp_business(telefono, mensaje)
                else:
                    success = False
                    response = "No hay configuración válida de API"
                
                return JsonResponse({
                    'success': success,
                    'message': response if not success else 'Mensaje de prueba enviado correctamente'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    })
