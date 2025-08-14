from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion
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
            
            # Obtener configuración
            config = ConfiguracionNotificacion.get_config()
            if not config.activo:
                return JsonResponse({
                    'success': False,
                    'message': 'Las notificaciones están desactivadas en la configuración'
                })
            
            # Crear servicio de WhatsApp
            whatsapp_service = WhatsAppService()
            
            # Mensaje de prueba
            mensaje = f"🔔 *Mensaje de Prueba - Eglis*\n\n" \
                     f"Hola {destinatario.nombre},\n\n" \
                     f"Este es un mensaje de prueba del sistema de notificaciones.\n\n" \
                     f"📅 Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}\n" \
                     f"✅ Tu número está configurado correctamente.\n\n" \
                     f"_Sistema de gestión de remesas Eglis_"
            
            # Enviar mensaje
            exito = whatsapp_service.enviar_mensaje(destinatario.telefono, mensaje)
            
            if exito:
                # Registrar en log
                LogNotificacion.objects.create(
                    tipo_evento='TEST',
                    destinatario=destinatario.nombre,
                    telefono=destinatario.telefono,
                    mensaje=mensaje,
                    exito=True
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Mensaje de prueba enviado correctamente a {destinatario.nombre}'
                })
            else:
                # Registrar error en log
                LogNotificacion.objects.create(
                    tipo_evento='TEST',
                    destinatario=destinatario.nombre,
                    telefono=destinatario.telefono,
                    mensaje=mensaje,
                    exito=False,
                    error='Error al enviar mensaje'
                )
                
                return JsonResponse({
                    'success': False,
                    'message': f'Error al enviar mensaje de prueba a {destinatario.nombre}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al enviar mensaje de prueba: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


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
