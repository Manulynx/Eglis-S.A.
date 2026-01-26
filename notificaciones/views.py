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
from remesas.models import Moneda


def _is_true(value):
    return str(value).lower() == 'true'


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
    monedas = Moneda.objects.filter(activa=True).order_by('codigo')
    
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            telefono = request.POST.get('telefono')
            callmebot_api_key = request.POST.get('callmebot_api_key', '')
            activo = _is_true(request.POST.get('activo'))

            # Flags granulares
            flags = {
                'recibir_remesa_nueva': _is_true(request.POST.get('recibir_remesa_nueva')),
                'recibir_remesa_confirmada': _is_true(request.POST.get('recibir_remesa_confirmada')),
                'recibir_remesa_completada': _is_true(request.POST.get('recibir_remesa_completada')),
                'recibir_remesa_cancelada': _is_true(request.POST.get('recibir_remesa_cancelada')),
                'recibir_remesa_editada': _is_true(request.POST.get('recibir_remesa_editada')),
                'recibir_remesa_eliminada': _is_true(request.POST.get('recibir_remesa_eliminada')),

                'recibir_pago_nuevo': _is_true(request.POST.get('recibir_pago_nuevo')),
                'recibir_pago_confirmado': _is_true(request.POST.get('recibir_pago_confirmado')),
                'recibir_pago_cancelado': _is_true(request.POST.get('recibir_pago_cancelado')),
                'recibir_pago_editado': _is_true(request.POST.get('recibir_pago_editado')),
                'recibir_pago_eliminado': _is_true(request.POST.get('recibir_pago_eliminado')),
            }

            moneda_ids = request.POST.getlist('monedas')
            
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
                **flags,

                # Campos legacy (se mantienen por compatibilidad)
                recibir_remesas=any([
                    flags['recibir_remesa_nueva'], flags['recibir_remesa_confirmada'], flags['recibir_remesa_completada'],
                    flags['recibir_remesa_cancelada'], flags['recibir_remesa_editada'], flags['recibir_remesa_eliminada'],
                ]),
                recibir_pagos=any([
                    flags['recibir_pago_nuevo'], flags['recibir_pago_confirmado'], flags['recibir_pago_cancelado'],
                    flags['recibir_pago_editado'], flags['recibir_pago_eliminado'],
                ]),
                recibir_cambios_estado=any([
                    flags['recibir_remesa_confirmada'], flags['recibir_remesa_completada'], flags['recibir_remesa_cancelada'],
                    flags['recibir_pago_confirmado'], flags['recibir_pago_cancelado'],
                ]),
                recibir_ediciones=any([
                    flags['recibir_remesa_editada'], flags['recibir_pago_editado'],
                ]),
            )

            if moneda_ids:
                destinatario.monedas.set(moneda_ids)
            else:
                destinatario.monedas.clear()
            
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
        'form': form,
        'monedas': monedas,
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
            destinatario.activo = _is_true(request.POST.get('activo'))

            # Flags granulares
            flags = {
                'recibir_remesa_nueva': _is_true(request.POST.get('recibir_remesa_nueva')),
                'recibir_remesa_confirmada': _is_true(request.POST.get('recibir_remesa_confirmada')),
                'recibir_remesa_completada': _is_true(request.POST.get('recibir_remesa_completada')),
                'recibir_remesa_cancelada': _is_true(request.POST.get('recibir_remesa_cancelada')),
                'recibir_remesa_editada': _is_true(request.POST.get('recibir_remesa_editada')),
                'recibir_remesa_eliminada': _is_true(request.POST.get('recibir_remesa_eliminada')),

                'recibir_pago_nuevo': _is_true(request.POST.get('recibir_pago_nuevo')),
                'recibir_pago_confirmado': _is_true(request.POST.get('recibir_pago_confirmado')),
                'recibir_pago_cancelado': _is_true(request.POST.get('recibir_pago_cancelado')),
                'recibir_pago_editado': _is_true(request.POST.get('recibir_pago_editado')),
                'recibir_pago_eliminado': _is_true(request.POST.get('recibir_pago_eliminado')),
            }

            for key, value in flags.items():
                setattr(destinatario, key, value)

            # Campos legacy (se mantienen por compatibilidad)
            destinatario.recibir_remesas = any([
                flags['recibir_remesa_nueva'], flags['recibir_remesa_confirmada'], flags['recibir_remesa_completada'],
                flags['recibir_remesa_cancelada'], flags['recibir_remesa_editada'], flags['recibir_remesa_eliminada'],
            ])
            destinatario.recibir_pagos = any([
                flags['recibir_pago_nuevo'], flags['recibir_pago_confirmado'], flags['recibir_pago_cancelado'],
                flags['recibir_pago_editado'], flags['recibir_pago_eliminado'],
            ])
            destinatario.recibir_cambios_estado = any([
                flags['recibir_remesa_confirmada'], flags['recibir_remesa_completada'], flags['recibir_remesa_cancelada'],
                flags['recibir_pago_confirmado'], flags['recibir_pago_cancelado'],
            ])
            destinatario.recibir_ediciones = any([
                flags['recibir_remesa_editada'], flags['recibir_pago_editado'],
            ])

            moneda_ids = request.POST.getlist('monedas')
            
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

            if moneda_ids:
                destinatario.monedas.set(moneda_ids)
            else:
                destinatario.monedas.clear()
            
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
@require_GET
def destinatario_json(request, destinatario_id):
    """Devuelve la configuración completa del destinatario para poblar el modal de edición."""
    destinatario = get_object_or_404(DestinatarioNotificacion, id=destinatario_id)

    return JsonResponse({
        'success': True,
        'destinatario': {
            'id': destinatario.id,
            'nombre': destinatario.nombre,
            'telefono': destinatario.telefono,
            'callmebot_api_key': destinatario.callmebot_api_key or '',
            'activo': bool(destinatario.activo),

            'recibir_remesa_nueva': bool(destinatario.recibir_remesa_nueva),
            'recibir_remesa_confirmada': bool(destinatario.recibir_remesa_confirmada),
            'recibir_remesa_completada': bool(destinatario.recibir_remesa_completada),
            'recibir_remesa_cancelada': bool(destinatario.recibir_remesa_cancelada),
            'recibir_remesa_editada': bool(destinatario.recibir_remesa_editada),
            'recibir_remesa_eliminada': bool(destinatario.recibir_remesa_eliminada),

            'recibir_pago_nuevo': bool(destinatario.recibir_pago_nuevo),
            'recibir_pago_confirmado': bool(destinatario.recibir_pago_confirmado),
            'recibir_pago_cancelado': bool(destinatario.recibir_pago_cancelado),
            'recibir_pago_editado': bool(destinatario.recibir_pago_editado),
            'recibir_pago_eliminado': bool(destinatario.recibir_pago_eliminado),

            'moneda_ids': list(destinatario.monedas.values_list('id', flat=True)),
        }
    })


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
                # LogNotificacion.objects.create(
                #     tipo='TEST',
                #     destinatario=destinatario,
                #     mensaje=mensaje,
                #     estado='enviado',
                #     respuesta_api=respuesta
                # )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Mensaje de prueba enviado correctamente a {destinatario.nombre}'
                })
            else:
                # Registrar error en log
                # LogNotificacion.objects.create(
                #     tipo='TEST',
                #     destinatario=destinatario,
                #     mensaje=mensaje,
                #     estado='fallido',
                #     respuesta_api=respuesta,
                #     error_mensaje=respuesta
                # )
                
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
