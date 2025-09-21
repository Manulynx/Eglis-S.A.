from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db import transaction
from . import models
from .models import Pago
from .forms import PagoForm
from django.core.paginator import Paginator
from django.contrib import messages
import logging
import json
import decimal
from urllib.parse import quote
from django.db.models import Sum
from decimal import Decimal

logger = logging.getLogger(__name__)

@login_required
def registro_transacciones(request):
    """Vista para el registro de transacciones"""
    # Determinar el tipo de usuario
    user_tipo = None
    if request.user.is_authenticated:
        if request.user.is_superuser:
            user_tipo = 'admin'
        elif hasattr(request.user, 'perfil'):
            user_tipo = request.user.perfil.tipo_usuario
        else:
            user_tipo = 'gestor'  # Default
    
    # Filtrar transacciones según el tipo de usuario
    if user_tipo == 'admin':
        # Admin ve todas las transacciones
        remesas = models.Remesa.objects.all()
        pagos = models.Pago.objects.all()
    elif user_tipo == 'contable':
        # Contable ahora puede ver todas las transacciones (incluyendo las de administradores)
        remesas = models.Remesa.objects.all()
        pagos = models.Pago.objects.all()
    else:
        # Gestor solo ve sus propias transacciones
        remesas = models.Remesa.objects.filter(gestor=request.user)
        pagos = models.Pago.objects.filter(usuario=request.user)
    
    # Conteos
    remesas_count = remesas.count()
    pagos_count = pagos.count()
    
    # Totales en USD - Solo sumar remesas completadas y pagos confirmados
    remesas_confirmadas_completadas = remesas.filter(estado='completada')
    pagos_confirmados = pagos.filter(estado='confirmado')
    total_remesas = sum(remesa.calcular_monto_en_usd() for remesa in remesas_confirmadas_completadas)
    total_pagos = sum(pago.calcular_monto_en_usd() for pago in pagos_confirmados)
    
    # Obtener monedas para filtros
    monedas = models.Moneda.objects.filter(activa=True)

    context = {
        'remesas': remesas.order_by('-fecha'),
        'pagos': pagos.order_by('-fecha_creacion'),
        'remesas_count': remesas_count,
        'pagos_count': pagos_count,
        'total_remesas': total_remesas,
        'total_pagos': total_pagos,
        'monedas': monedas,
        'user_tipo': user_tipo,
    }

    return render(request, 'remesas/registro_transacciones.html', context)

@login_required
def remesas_admin(request):
    logger.info(f"Request method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"POST data: {dict(request.POST)}")
    
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Moneda
        if 'nombre_moneda' in request.POST:
            nombre = request.POST.get('nombre_moneda')
            valor_actual = request.POST.get('valor_actual')
            if nombre:
                try:
                    # Si no se proporciona valor_actual, usar el valor por defecto del modelo
                    if valor_actual:
                        models.Moneda.objects.create(
                            nombre=nombre,
                            valor_actual=valor_actual
                        )
                    else:
                        models.Moneda.objects.create(nombre=nombre)
                    return JsonResponse({'success': True, 'message': 'Moneda guardada correctamente.'})
                except Exception as e:
                    return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
            return JsonResponse({'success': False, 'message': 'Nombre de moneda es requerido.'})
        # Método de pago
        elif 'nombre_pago' in request.POST:
            logger.info("Processing método de pago")
            nombre = request.POST.get('nombre_pago')
            logger.info(f"Nombre pago: {nombre}")
            if nombre:
                try:
                    pago = models.TipodePago.objects.create(nombre=nombre)
                    logger.info(f"Método de pago creado: {pago}")
                    return JsonResponse({'success': True, 'message': 'Método de pago guardado correctamente.'})
                except Exception as e:
                    logger.error(f"Error creating TipodePago: {e}")
                    return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
            return JsonResponse({'success': False, 'message': 'Datos incompletos para método de pago.'})
        return JsonResponse({'success': False, 'message': 'Formulario no reconocido.'})

    # GET: Renderizar template normalmente
    monedas = models.Moneda.objects.filter(activa=True)
    metodos_pago = models.TipodePago.objects.all()
    return render(request, 'remesas/remesas_Admin.html', {
        'monedas': monedas,
        'metodos_pago': metodos_pago,
    })

@login_required
def remesas(request):
    if request.method == 'POST':
        # Debug: verificar que llegue el POST
        print("=== DEBUG POST ===")
        print("Headers:", dict(request.headers))
        print("POST data completo:", dict(request.POST))
        print("FILES:", dict(request.FILES))
        
        # Verificar específicamente los campos de clientes
        print("\n=== CAMPOS DE CLIENTES ===")
        for key in request.POST:
            if 'receptor' in key or 'destinatario' in key:
                print(f"{key}: '{request.POST.get(key)}'")
        
        # Verificar si es AJAX
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        print(f"Es AJAX: {is_ajax}")
        
        if is_ajax:
            from django.db import transaction
            
            try:
                with transaction.atomic():
                    print("\n=== INICIANDO PROCESAMIENTO ===")
                    
                    # Obtener datos básicos del formulario simplificado
                    receptor_nombre = request.POST.get('receptor_nombre', '').strip()
                    importe = request.POST.get('importe', '').strip()
                    tipo_pago = request.POST.get('tipo_pago', '').strip()
                    moneda_id = request.POST.get('moneda', '').strip()
                    observaciones = request.POST.get('observaciones', '').strip()
                    comprobante = request.FILES.get('comprobante')
                    
                    print(f"\n=== DATOS EXTRAÍDOS ===")
                    print(f"receptor_nombre: '{receptor_nombre}'")
                    print(f"importe: '{importe}'")
                    print(f"tipo_pago: '{tipo_pago}'")
                    print(f"moneda_id: '{moneda_id}'")
                    print(f"observaciones: '{observaciones}'")
                    print(f"comprobante: {comprobante}")
                    
                    # Validación de campos obligatorios
                    if not receptor_nombre or not importe or not tipo_pago or not moneda_id:
                        print("=== ERROR: FALTAN CAMPOS OBLIGATORIOS ===")
                        print(f"receptor_nombre válido: {bool(receptor_nombre)}")
                        print(f"importe válido: {bool(importe)}")
                        print(f"tipo_pago válido: {bool(tipo_pago)}")
                        print(f"moneda_id válido: {bool(moneda_id)}")
                        return JsonResponse({
                            'success': False, 
                            'message': 'Faltan campos obligatorios: nombre del remitente, importe, tipo de pago y moneda son requeridos'
                        })
                    
                    # Validar importe
                    try:
                        importe_decimal = float(importe)
                        if importe_decimal <= 0:
                            return JsonResponse({'success': False, 'message': 'El importe debe ser mayor a 0'})
                        print(f"Importe convertido: {importe_decimal}")
                    except (ValueError, TypeError) as e:
                        print(f"Error convirtiendo importe: {e}")
                        return JsonResponse({'success': False, 'message': 'El importe debe ser un número válido'})
                    
                    # Obtener moneda
                    try:
                        moneda = models.Moneda.objects.get(id=moneda_id)
                        print(f"Moneda encontrada: {moneda}")
                    except models.Moneda.DoesNotExist:
                        return JsonResponse({'success': False, 'message': 'La moneda seleccionada no existe'})
                    
                    # Crear remesa con el modelo simplificado
                    print(f"\n=== CREANDO REMESA ===")
                    
                    remesa_data = {
                        'receptor_nombre': receptor_nombre,
                        'importe': importe_decimal,
                        'tipo_pago': tipo_pago,
                        'moneda': moneda,
                        'gestor': request.user if request.user.is_authenticated else None,
                    }
                    
                    # Agregar campos opcionales
                    if observaciones:
                        remesa_data['observaciones'] = observaciones
                    
                    if comprobante:
                        remesa_data['comprobante'] = comprobante
                    
                    remesa = models.Remesa.objects.create(**remesa_data)
                    
                    print(f"Remesa creada:")
                    print(f"  ID: {remesa.id}")
                    print(f"  RemesaID: '{remesa.remesa_id}'")
                    print(f"  Importe: {remesa.importe}")
                    print(f"  Receptor: '{remesa.receptor_nombre}'")
                    print(f"  Tipo de pago: '{remesa.tipo_pago}'")
                    print(f"  Moneda: {remesa.moneda}")
                    
                    # El balance se actualiza automáticamente mediante cálculo dinámico
                    # No es necesario actualizar manualmente
                    
                    # Enviar notificación
                    try:
                        from notificaciones.services import WhatsAppService
                        from notificaciones.models import LogNotificacion
                        from django.utils import timezone
                        
                        # Crear registro de notificación interna
                        LogNotificacion.objects.create(
                            tipo='remesa_creada',
                            mensaje=f"Se ha creado exitosamente la remesa {remesa.remesa_id} por un monto de {remesa.importe} {remesa.moneda.codigo}.",
                            usuario=request.user,
                            fecha_envio=timezone.now(),
                            exitoso=True
                        )
                        
                        # También intentar enviar por WhatsApp si está configurado
                        whatsapp_service = WhatsAppService()
                        whatsapp_service.enviar_notificacion('remesa_creada', remesa=remesa)
                        
                        print(f"Notificación registrada para remesa {remesa.remesa_id}")
                    except Exception as e:
                        print(f"Error enviando notificación: {e}")
                    
                    print("\n=== ÉXITO ===")
                    from django.urls import reverse
                    detalle_url = reverse('remesas:detalle_remesa', kwargs={'remesa_id': remesa.id})
                    
                    return JsonResponse({
                        'success': True, 
                        'message': f'Remesa {remesa.remesa_id} guardada correctamente.',
                        'remesa_id': remesa.remesa_id,
                        'remesa_pk': remesa.id,
                        'detalle_url': detalle_url
                    })
                    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"\n=== ERROR COMPLETO ===")
                print(error_detail)
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
        
        else:
            print("No es una petición AJAX")
            return JsonResponse({'success': False, 'message': 'Petición no válida'})
    
    # GET request: renderizar template
    print("GET request - renderizando template")
    from django.contrib.auth.models import User
    import json
    
    # Obtener monedas para cálculos con valores específicos del usuario
    monedas = models.Moneda.objects.filter(activa=True)
    monedas_data = []
    for moneda in monedas:
        valor_usuario = moneda.get_valor_para_usuario(request.user)
        monedas_data.append({
            'id': moneda.id,
            'codigo': moneda.codigo,
            'nombre': moneda.nombre,
            'valor_usuario': float(valor_usuario)
        })
    
    # Obtener balance del usuario usando cálculo dinámico
    user_balance = 0
    if request.user.is_authenticated:
        try:
            # Intentar obtener el perfil del usuario
            if hasattr(request.user, 'perfil'):
                balance_calculado = request.user.perfil.calcular_balance_real()
                # Actualizar balance almacenado si difiere del calculado
                if request.user.perfil.balance != balance_calculado:
                    request.user.perfil.actualizar_balance()
                user_balance = float(balance_calculado)
            else:
                # Si no hay perfil, buscar en el modelo Balance
                from login.models import PerfilUsuario
                perfil, created = PerfilUsuario.objects.get_or_create(
                    user=request.user,
                    defaults={'balance': 0.0}
                )
                balance_calculado = perfil.calcular_balance_real()
                user_balance = float(balance_calculado)
        except Exception as e:
            print(f"Error obteniendo balance del usuario: {e}")
            user_balance = 0
    
    context = {
        'gestores': User.objects.filter(is_active=True),
        'monedas_json': json.dumps(monedas_data),
        'user_balance': user_balance
    }
    return render(request, 'remesas/remesas.html', context)

# API endpoints para formularios dinámicos
@login_required
def api_monedas(request):
    tipo_moneda = request.GET.get('tipo_moneda', None)
    
    # Filtrar monedas activas
    monedas_query = models.Moneda.objects.filter(activa=True)
    
    # Si se especifica un tipo de moneda, filtrar por él
    if tipo_moneda and tipo_moneda in ['efectivo', 'transferencia']:
        monedas_query = monedas_query.filter(tipo_moneda=tipo_moneda)
    
    monedas_list = []
    for moneda in monedas_query:
        valor_usuario = moneda.get_valor_para_usuario(request.user)
        monedas_list.append({
            'id': moneda.id,
            'nombre': f"{moneda.nombre} - {valor_usuario}",
            'codigo': moneda.codigo,
            'valor_usuario': float(valor_usuario),
            'tipo_moneda': moneda.tipo_moneda
        })
    
    return JsonResponse(monedas_list, safe=False)

@login_required
def api_gestores(request):
    # Importar aquí para evitar problemas de importación circular
    from django.contrib.auth.models import User
    
    # Obtener usuarios activos que pueden ser gestores
    usuarios = User.objects.filter(is_active=True).values('id', 'first_name', 'last_name', 'username')
    usuarios_list = [
        {
            'id': u['id'], 
            'nombre': f"{u['first_name']} {u['last_name']}" if u['first_name'] and u['last_name'] else u['username']
        }
        for u in usuarios
    ]
    return JsonResponse(usuarios_list, safe=False)

@login_required
def api_metodos_pago(request):
    metodos = models.TipodePago.objects.all().values('id', 'nombre')
    return JsonResponse(list(metodos), safe=False)

def registrar_estado_remesa(remesa, tipo, request, detalles=None):
    """Función auxiliar para registrar cambios de estado en remesas"""
    models.RegistroRemesas.objects.create(
        remesa=remesa,
        tipo=tipo,
        usuario_registro=request.user,
        monto=remesa.importe,
        detalles=detalles
    )

@login_required
def confirmar_remesa(request, remesa_id):
    if request.method == 'POST':
        try:
            remesa = get_object_or_404(models.Remesa, id=remesa_id)
            
            if not remesa.puede_confirmar():
                return JsonResponse({
                    'success': False, 
                    'message': f'La remesa {remesa.remesa_id} no puede ser confirmada porque está en estado: {remesa.get_estado_display()}'
                })
            
            # Cambiar directamente de pendiente a completada (eliminando el estado intermedio confirmada)
            remesa.estado = 'completada'
            remesa.save()
            
            # Registrar el cambio como procesada exitosamente
            models.RegistroRemesas.objects.create(
                remesa=remesa,
                tipo='procesada',
                usuario_registro=request.user if request.user.is_authenticated else None,
                detalles=f'Remesa {remesa.remesa_id} confirmada y completada exitosamente',
                monto=remesa.importe or 0
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Remesa {remesa.remesa_id} confirmada y completada exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Error al confirmar la remesa: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

# FUNCIÓN ELIMINADA - La lógica de completar remesa se movió a confirmar_remesa
# La acción de completar remesa ya no es necesaria como paso separado

@login_required
def eliminar_remesa(request, remesa_id):
    """
    Vista para eliminar una remesa - Solo administradores
    """
    if request.method == 'POST':
        # Verificar que el usuario es administrador o contable
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        if user_tipo not in ['admin', 'contable']:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para eliminar remesas. Solo los administradores y contables pueden realizar esta acción.'
            })
        
        try:
            remesa = get_object_or_404(models.Remesa, id=remesa_id)
            
            # Verificar que la remesa esté completada
            if remesa.estado != 'completada':
                return JsonResponse({
                    'success': False,
                    'message': f'Solo se pueden eliminar remesas completadas. Esta remesa está en estado: {remesa.get_estado_display()}'
                })
            
            # Guardar información para la notificación y balance
            remesa_info = {
                'id': remesa.remesa_id,
                'importe': remesa.importe,
                'moneda': remesa.moneda,
                'receptor': remesa.receptor_nombre,
                'gestor': remesa.gestor,
                'fecha': remesa.fecha
            }
            
            # Calcular monto en USD para revertir el balance
            monto_usd = remesa.calcular_monto_en_usd()
            
            # Revertir el balance del gestor (restar el monto que se había agregado)
            if remesa.gestor:
                # Verificar si el gestor tiene perfil, si no, crearlo
                if not hasattr(remesa.gestor, 'perfil'):
                    from login.models import PerfilUsuario
                    from remesas.models import TipoValorMoneda
                    tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
                    PerfilUsuario.objects.create(
                        user=remesa.gestor,
                        tipo_usuario='admin' if remesa.gestor.is_superuser else 'gestor',
                        tipo_valor_moneda=tipo_valor_defecto
                    )
                
                perfil_gestor = remesa.gestor.perfil
                perfil_gestor.balance -= monto_usd
                perfil_gestor.save()
            
            # Eliminar la remesa
            remesa.delete()
            
            # Crear notificación
            try:
                print(f"DEBUG: Iniciando creación de notificación para remesa eliminada #{remesa_info['id']}")
                from notificaciones.models import LogNotificacion, DestinatarioNotificacion
                from notificaciones.services import WhatsAppService
                
                # Mensaje de notificación
                mensaje_notificacion = f"🗑️ REMESA ELIMINADA: La remesa #{remesa_info['id']} por ${remesa_info['importe']} {remesa_info['moneda'].codigo if remesa_info['moneda'] else 'USD'} ha sido eliminada por el administrador {request.user.get_full_name() or request.user.username}. Balance actualizado: -${monto_usd:.2f} USD"
                
                # Crear logs de notificación para destinatarios activos
                destinatarios = DestinatarioNotificacion.objects.filter(activo=True, recibir_remesas=True)
                print(f"DEBUG: Destinatarios encontrados: {destinatarios.count()}")
                
                for destinatario in destinatarios:
                    log_created = LogNotificacion.objects.create(
                        tipo='remesa_eliminada',
                        destinatario=destinatario,
                        mensaje=mensaje_notificacion,
                        remesa_id=remesa_info['id'],
                        estado='pendiente'
                    )
                    print(f"DEBUG: Log creado ID {log_created.id} para {destinatario.nombre}")
                
                # Intentar enviar por WhatsApp
                print(f"DEBUG: Iniciando envío de WhatsApp...")
                whatsapp_service = WhatsAppService()
                whatsapp_service.enviar_notificacion(
                    'remesa_eliminada',
                    remesa=None,  # La remesa ya fue eliminada
                    pago=None,
                    estado_anterior=None,
                    remesa_id=remesa_info['id'],
                    monto=f"{remesa_info['importe']} {remesa_info['moneda'].codigo if remesa_info['moneda'] else 'USD'}",
                    admin_name=request.user.get_full_name() or request.user.username,
                    balance_change=f"-${monto_usd:.2f} USD"
                )
                print(f"DEBUG: Notificación WhatsApp completada")
                
            except Exception as e:
                print(f"Error enviando notificación de eliminación de remesa: {e}")
                import traceback
                traceback.print_exc()
            
            return JsonResponse({
                'success': True,
                'message': f'Remesa #{remesa_info["id"]} eliminada exitosamente. Balance actualizado: -${monto_usd:.2f} USD'
            })
            
        except Exception as e:
            import traceback
            error_detail = f'Error al eliminar la remesa: {str(e)}'
            print(f"ERROR en eliminar_remesa: {error_detail}")
            print(f"TRACEBACK: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'message': error_detail
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)

@login_required
def eliminar_pago(request, pago_id):
    """
    Vista para eliminar un pago - Solo administradores
    """
    if request.method == 'POST':
        # Verificar que el usuario es administrador o contable
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        if user_tipo not in ['admin', 'contable']:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para eliminar pagos. Solo los administradores y contables pueden realizar esta acción.'
            })
        
        try:
            pago = get_object_or_404(models.Pago, id=pago_id)
            
            # Guardar información para la notificación y balance
            pago_info = {
                'id': pago.pago_id,
                'cantidad': pago.cantidad,
                'moneda': pago.tipo_moneda,
                'destinatario': pago.destinatario,
                'usuario': pago.usuario,
                'fecha': pago.fecha_creacion
            }
            
            # Calcular monto en USD para revertir el balance
            monto_usd = pago.calcular_monto_en_usd()
            
            # Revertir el balance del usuario (agregar el monto que se había descontado)
            if pago.usuario:
                # Verificar si el usuario tiene perfil, si no, crearlo
                if not hasattr(pago.usuario, 'perfil'):
                    from login.models import PerfilUsuario
                    from remesas.models import TipoValorMoneda
                    tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
                    PerfilUsuario.objects.create(
                        user=pago.usuario,
                        tipo_usuario='admin' if pago.usuario.is_superuser else 'gestor',
                        tipo_valor_moneda=tipo_valor_defecto
                    )
                
                perfil_usuario = pago.usuario.perfil
                perfil_usuario.balance += monto_usd
                perfil_usuario.save()
            
            # Eliminar el pago
            pago.delete()
            
            # SIEMPRE enviar notificación
            print(f"DEBUG: Enviando notificación para pago eliminado #{pago_info['id']}")
            try:
                from notificaciones.services import WhatsAppService
                
                # Mensaje de notificación
                moneda_codigo = pago_info['moneda'].codigo if pago_info['moneda'] else 'USD'
                
                # Enviar por WhatsApp
                whatsapp_service = WhatsAppService()
                monto_str = f"{pago_info['cantidad']} {moneda_codigo}"
                whatsapp_service.enviar_notificacion(
                    'pago_eliminado',
                    pago_id=pago_info['id'],
                    monto=monto_str,
                    destinatario=pago_info['destinatario'],
                    admin_name=request.user.get_full_name() or request.user.username,
                    balance_change=f"+${monto_usd:.2f} USD"
                )
                print(f"DEBUG: Notificación WhatsApp enviada exitosamente")
                
            except Exception as e:
                print(f"Error enviando notificación de eliminación de pago: {e}")
                import traceback
                traceback.print_exc()
            
            return JsonResponse({
                'success': True,
                'message': f'Pago #{pago_info["id"]} eliminado exitosamente. Balance actualizado: +${monto_usd:.2f} USD'
            })
            
        except Exception as e:
            import traceback
            error_detail = f'Error al eliminar el pago: {str(e)}'
            print(f"ERROR en eliminar_pago: {error_detail}")
            print(f"TRACEBACK: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'message': error_detail
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)

# FUNCIÓN ELIMINADA - Reemplazada por registro_transacciones en views_transacciones.py
# @login_required
# def lista_remesas(request):
#     from django.db.models import Q, Sum
#     from django.contrib.auth.models import User
#     
#     # Obtener todos los filtros
#     estado = request.GET.get('estado')
#     fecha_desde = request.GET.get('fecha_desde')
#     fecha_hasta = request.GET.get('fecha_hasta')
#     busqueda = request.GET.get('busqueda')
#     receptor_nombre = request.GET.get('receptor_nombre')
#     monto_min = request.GET.get('monto_min')
#     monto_max = request.GET.get('monto_max')
#     moneda = request.GET.get('moneda')
#     gestor = request.GET.get('gestor')
#     remesa_id = request.GET.get('remesa_id')
#     
#     # Query base
#     remesas = models.Remesa.objects.select_related('moneda', 'gestor').all().order_by('-fecha')
#     
#     # Aplicar filtros
#     if estado:
#         remesas = remesas.filter(estado=estado)
#         
#     if fecha_desde:
#         remesas = remesas.filter(fecha__date__gte=fecha_desde)
#         
#     if fecha_hasta:
#         remesas = remesas.filter(fecha__date__lte=fecha_hasta)
#         
#     if busqueda:
#         remesas = remesas.filter(
#             Q(remesa_id__icontains=busqueda) |
#             Q(receptor_nombre__icontains=busqueda)
#         )
#         
#     if receptor_nombre:
#         remesas = remesas.filter(receptor_nombre__icontains=receptor_nombre)
#         
#     if monto_min:
#         try:
#             remesas = remesas.filter(importe__gte=float(monto_min))
#         except ValueError:
#             pass
#             
#     if monto_max:
#         try:
#             remesas = remesas.filter(importe__lte=float(monto_max))
#         except ValueError:
#             pass
#             
#     if moneda:
#         try:
#             remesas = remesas.filter(moneda_id=int(moneda))
#         except ValueError:
#             pass
#             
#     if gestor:
#         try:
#             remesas = remesas.filter(gestor_id=int(gestor))
#         except ValueError:
#             pass
#             
#     if remesa_id:
#         remesas = remesas.filter(remesa_id__icontains=remesa_id)
#         
#     # Estadísticas generales (sin filtros aplicados) - deben mostrar el total general
#     todas_remesas = models.Remesa.objects.all()
#     total_pendientes = todas_remesas.filter(estado='pendiente').count()
#     total_confirmadas = todas_remesas.filter(estado='confirmada').count()
#     total_completadas = todas_remesas.filter(estado='completada').count()
#     total_canceladas = todas_remesas.filter(estado='cancelada').count()
#     
#     # Datos adicionales para los filtros
#     monedas = models.Moneda.objects.all().order_by('nombre')
#     gestores = User.objects.filter(
#         id__in=models.Remesa.objects.values_list('gestor_id', flat=True).distinct()
#     ).order_by('first_name', 'last_name', 'username')
#     
#     context = {
#         'remesas': remesas,
#         'total_pendientes': total_pendientes,
#         'total_confirmadas': total_confirmadas,
#         'total_completadas': total_completadas,
#         'total_canceladas': total_canceladas,
#         'monedas': monedas,
#         'gestores': gestores,
#     }
#     
#     # Paginación
#     paginator = Paginator(remesas, 15)  # Aumenté a 15 elementos por página
#     page = request.GET.get('page')
#     context['remesas'] = paginator.get_page(page)
#     
#     return render(request, 'remesas/lista_remesas.html', context)

@login_required
def cancelar_remesa(request, remesa_id):
    """
    Vista para cancelar una remesa
    """
    if request.method == 'POST':
        try:
            remesa = get_object_or_404(models.Remesa, id=remesa_id)
            
            if not remesa.puede_cancelar():
                return JsonResponse({
                    'success': False, 
                    'message': f'La remesa {remesa.remesa_id} no puede ser cancelada porque está en estado: {remesa.get_estado_display()}'
                })
            
            # Usar el método del modelo para cancelar
            if remesa.cancelar():
                # Registrar el cambio de estado en el historial
                models.RegistroRemesas.objects.create(
                    remesa=remesa,
                    tipo='cancelada',
                    usuario_registro=request.user if request.user.is_authenticated else None,
                    monto=remesa.importe or 0,
                    detalles=f'Remesa {remesa.remesa_id} cancelada por el usuario'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Remesa {remesa.remesa_id} cancelada exitosamente'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'No se pudo cancelar la remesa {remesa.remesa_id}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al cancelar la remesa: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)

@login_required
def detalle_remesa(request, remesa_id):
    """
    Vista para mostrar los detalles de una remesa específica
    """
    try:
        # Obtener la remesa y sus registros relacionados
        remesa = get_object_or_404(models.Remesa, id=remesa_id)
        registros = models.RegistroRemesas.objects.filter(remesa=remesa).order_by('-fecha_registro')
        
        # Determinar el tipo de usuario
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )

        context = {
            'remesa': remesa,
            'registros': registros,
            'user_tipo': user_tipo,
            'title': f'Detalle de la Remesa #{remesa.remesa_id}'
        }
        
        return render(request, 'remesas/detalle_remesa.html', context)
        
    except Exception as e:
        # En caso de error, redirigir a la lista con un mensaje de error
        messages.error(request, f'Error al obtener los detalles de la remesa: {str(e)}')
        return redirect('remesas:registro_transacciones')

@login_required
def editar_remesa(request, remesa_id):
    """
    Vista para editar una remesa existente
    """
    try:
        remesa = get_object_or_404(models.Remesa, id=remesa_id)
        
        # Solo permitir editar remesas en estado pendiente
        if remesa.estado != 'pendiente':
            messages.error(request, f'No se puede editar la remesa {remesa.remesa_id} porque está en estado: {remesa.get_estado_display()}')
            return redirect('remesas:detalle_remesa', remesa_id=remesa.id)
        
        if request.method == 'POST':
            # Verificar si es AJAX
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            
            try:
                # Obtener datos del formulario simplificado
                receptor_nombre = request.POST.get('receptor_nombre', '').strip()
                importe = request.POST.get('importe', '').strip()
                moneda_id = request.POST.get('moneda', '').strip()
                tipo_pago = request.POST.get('tipo_pago', '').strip()
                observaciones = request.POST.get('observaciones', '').strip()
                comprobante = request.FILES.get('comprobante')
                
                # Validaciones básicas
                if not receptor_nombre or not importe or not moneda_id or not tipo_pago:
                    error_msg = 'Todos los campos obligatorios deben ser completados'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    else:
                        messages.error(request, error_msg)
                        return redirect(request.path)
                
                # Validar importe
                try:
                    importe_decimal = float(importe)
                    if importe_decimal <= 0:
                        raise ValueError("El importe debe ser mayor a 0")
                except ValueError:
                    error_msg = 'El importe debe ser un número válido mayor que 0'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    else:
                        messages.error(request, error_msg)
                        return redirect(request.path)
                
                # Obtener la moneda
                try:
                    moneda = models.Moneda.objects.get(id=moneda_id)
                except models.Moneda.DoesNotExist:
                    error_msg = 'Moneda seleccionada no válida'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    else:
                        messages.error(request, error_msg)
                        return redirect(request.path)
                
                # Actualizar remesa
                remesa.receptor_nombre = receptor_nombre
                remesa.importe = importe_decimal
                remesa.moneda = moneda
                remesa.tipo_pago = tipo_pago
                remesa.observaciones = observaciones or None
                
                # Actualizar comprobante si se proporciona uno nuevo
                if comprobante:
                    remesa.comprobante = comprobante
                
                # Guardar primero los cambios básicos
                remesa.save()
                
                # Establecer el usuario editor antes del recálculo
                remesa.usuario_editor = request.user
                
                # Recalcular valores USD con las tasas actuales después de la edición
                remesa.recalcular_valores_por_edicion()
                
                success_msg = f'Remesa {remesa.remesa_id} actualizada exitosamente con nuevos valores USD'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': success_msg})
                else:
                    messages.success(request, success_msg)
                    return redirect('remesas:registro_transacciones')
                    
            except Exception as e:
                error_msg = f'Error al actualizar la remesa: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect('remesas:registro_transacciones')
        
        # GET request - mostrar formulario
        # Filtrar monedas según el tipo de pago de la remesa actual
        monedas = models.Moneda.objects.filter(
            activa=True, 
            tipo_moneda=remesa.tipo_pago
        ).order_by('nombre')
        
        context = {
            'remesa': remesa,
            'monedas': monedas,
            'title': f'Editar Remesa {remesa.remesa_id}'
        }
        return render(request, 'remesas/editar_remesa.html', context)
        
    except Exception as e:
        # En caso de error, redirigir a la lista con un mensaje de error
        messages.error(request, f'Error al obtener los detalles de la remesa: {str(e)}')
        return redirect('remesas:registro_transacciones')


# ==================== VISTAS PARA MONEDAS ====================

@login_required
def lista_monedas(request):
    """
    Vista para listar todas las monedas con sus valores por tipo
    """
    monedas = models.Moneda.objects.all().order_by('codigo')
    tipos_valores = models.TipoValorMoneda.objects.filter(activo=True).order_by('orden', 'nombre')
    
    # Preparar datos estructurados para la tabla
    monedas_con_valores = []
    for moneda in monedas:
        valores_por_tipo = {}
        for tipo in tipos_valores:
            try:
                valor_obj = models.ValorMoneda.objects.get(moneda=moneda, tipo_valor=tipo)
                valores_por_tipo[tipo.id] = valor_obj.valor
            except models.ValorMoneda.DoesNotExist:
                valores_por_tipo[tipo.id] = Decimal('0')
        
        monedas_con_valores.append({
            'moneda': moneda,
            'valores': valores_por_tipo
        })
    
    context = {
        'monedas_con_valores': monedas_con_valores,
        'tipos_valores': tipos_valores,
        'total_monedas': monedas.count(),
        'total_tipos': tipos_valores.count(),
    }
    
    return render(request, 'Monedas/lista_monedas.html', context)


@login_required
def crear_moneda(request):
    """
    Vista para crear una nueva moneda
    """
    if request.method == 'POST':
        try:
            codigo = request.POST.get('codigo', '').upper()
            nombre = request.POST.get('nombre', '')
            tipo_moneda = request.POST.get('tipo_moneda', 'transferencia')
            activa = request.POST.get('activa') == 'on'
            
            if not codigo or not nombre:
                return redirect(f'/remesas/monedas/?error=create&message={quote("El código y nombre son obligatorios")}')
            
            # Verificar si el código ya existe
            if models.Moneda.objects.filter(codigo=codigo).exists():
                return redirect(f'/remesas/monedas/?error=create&message={quote(f"Ya existe una moneda con el código {codigo}")}')

            # Crear la moneda sin valores (se asignarán después)
            moneda = models.Moneda.objects.create(
                codigo=codigo,
                nombre=nombre,
                tipo_moneda=tipo_moneda,
                activa=activa
            )
            
            # Crear valores con 0 para todos los tipos de valor existentes
            tipos_valores = models.TipoValorMoneda.objects.filter(activo=True)
            for tipo_valor in tipos_valores:
                models.ValorMoneda.objects.create(
                    moneda=moneda,
                    tipo_valor=tipo_valor,
                    valor=0,
                    actualizado_por=request.user
                )
            
            return redirect(f'/remesas/monedas/?success=create&codigo={quote(codigo)}&nombre={quote(nombre)}')
            
        except Exception as e:
            return redirect(f'/remesas/monedas/?error=create&message={quote(str(e))}')
    
    return render(request, 'Monedas/moneda_form.html', {'is_edit': False})


@login_required
def editar_moneda(request, moneda_id):
    """
    Vista para editar una moneda existente
    """
    moneda = get_object_or_404(models.Moneda, id=moneda_id)
    
    if request.method == 'POST':
        try:
            # Obtener el código original antes de cualquier cambio
            codigo_original = moneda.codigo
            
            # Permitir editar código solo si no es USD y no tiene registros asociados
            if moneda.codigo != 'USD':
                nuevo_codigo = request.POST.get('codigo', '').strip().upper()
                if nuevo_codigo and nuevo_codigo != moneda.codigo:
                    # Verificar que el nuevo código no esté en uso
                    if models.Moneda.objects.filter(codigo=nuevo_codigo).exclude(id=moneda.id).exists():
                        return redirect(f'/remesas/monedas/?error=edit&message={quote(f"El código {nuevo_codigo} ya está en uso")}')
                    
                    # Verificar si cambiar el código afectaría registros existentes
                    remesas_count = models.Remesa.objects.filter(moneda=moneda).count()
                    if remesas_count > 0:
                        messages.warning(request, f'⚠️ Esta moneda está siendo utilizada en {remesas_count} remesa(s). El cambio de código no afectará los registros históricos, pero se recomienda precaución.')
                    
                    balances_count = models.Balance.objects.filter(moneda=moneda).count()
                    if balances_count > 0:
                        messages.warning(request, f'⚠️ Esta moneda está siendo utilizada en {balances_count} balance(s) de usuario. El cambio no afectará los registros existentes.')
                    
                    moneda.codigo = nuevo_codigo
            
            moneda.nombre = request.POST.get('nombre', '')
            moneda.valor_actual = request.POST.get('valor_actual')
            moneda.valor_comercial = request.POST.get('valor_comercial')
            moneda.tipo_moneda = request.POST.get('tipo_moneda', 'transferencia')
            moneda.activa = request.POST.get('activa') == 'on'
            
            if not moneda.codigo or not moneda.nombre or not moneda.valor_actual or not moneda.valor_comercial or not moneda.tipo_moneda:
                return redirect(f'/remesas/monedas/?error=edit&message={quote("Todos los campos obligatorios deben ser completados")}')
            
            moneda.save()
            
            # Redireccionar con parámetro de éxito para mostrar SweetAlert2
            return redirect(f'/remesas/monedas/?success=edit&codigo={quote(moneda.codigo)}&nombre={quote(moneda.nombre)}')
            
        except Exception as e:
            # Redireccionar con parámetro de error
            return redirect(f'/remesas/monedas/?error=edit&message={quote(str(e))}')
            return redirect('remesas:editar_moneda', moneda_id=moneda_id)
    
    # Obtener información sobre el uso de la moneda para mostrar advertencias
    remesas_count = models.Remesa.objects.filter(moneda=moneda).count()
    balances_count = models.Balance.objects.filter(moneda=moneda).count()
    
    # Verificar pagos si el modelo existe
    pagos_count = 0
    try:
        pagos_count = models.Pago.objects.filter(tipo_moneda=moneda).count()
    except AttributeError:
        pass
    
    context = {
        'moneda': moneda,
        'is_edit': True,
        'remesas_count': remesas_count,
        'balances_count': balances_count,
        'pagos_count': pagos_count,
        'tiene_registros': remesas_count > 0 or balances_count > 0 or pagos_count > 0
    }
    
    return render(request, 'Monedas/moneda_form.html', context)


@login_required
def eliminar_moneda(request, moneda_id):
    """
    Vista para eliminar una moneda (AJAX)
    Los registros asociados se preservan con referencia NULL
    """
    if request.method == 'POST':
        try:
            moneda = get_object_or_404(models.Moneda, id=moneda_id)
            
            # Proteger la moneda USD
            if moneda.codigo == 'USD':
                return JsonResponse({
                    'success': False,
                    'message': 'No se puede eliminar la moneda USD ya que es la moneda base del sistema.'
                })
            
            # Contar registros asociados para mostrar información al usuario
            remesas_count = models.Remesa.objects.filter(moneda=moneda).count()
            balances_count = models.Balance.objects.filter(moneda=moneda).count()
            
            # Verificar pagos si el modelo existe
            pagos_count = 0
            try:
                pagos_count = models.Pago.objects.filter(tipo_moneda=moneda).count()
            except AttributeError:
                pass
            
            codigo = moneda.codigo
            nombre = moneda.nombre
            total_registros = remesas_count + balances_count + pagos_count
            
            # Eliminar la moneda (los registros se preservan con SET_NULL)
            moneda.delete()
            
            if total_registros > 0:
                mensaje = f'Moneda {codigo} - {nombre} eliminada exitosamente. Se preservaron {total_registros} registros históricos:'
                detalles = []
                if remesas_count > 0:
                    detalles.append(f'{remesas_count} remesa(s)')
                if balances_count > 0:
                    detalles.append(f'{balances_count} balance(s)')
                if pagos_count > 0:
                    detalles.append(f'{pagos_count} pago(s)')
                mensaje += ' ' + ', '.join(detalles) + '.'
            else:
                mensaje = f'Moneda {codigo} - {nombre} eliminada exitosamente.'
            
            return JsonResponse({
                'success': True,
                'message': mensaje
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al eliminar la moneda: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
def toggle_estado_moneda(request, moneda_id):
    """
    Vista para cambiar el estado (activa/inactiva) de una moneda (AJAX)
    """
    if request.method == 'POST':
        try:
            moneda = get_object_or_404(models.Moneda, id=moneda_id)
            
            # Proteger la moneda USD
            if moneda.codigo == 'USD':
                return JsonResponse({
                    'success': False,
                    'message': 'No se puede cambiar el estado de la moneda USD ya que es la moneda base del sistema.'
                })
            
            # Cambiar el estado
            moneda.activa = not moneda.activa
            moneda.save()
            
            estado_texto = 'activada' if moneda.activa else 'desactivada'
            
            return JsonResponse({
                'success': True,
                'message': f'Moneda {moneda.codigo} {estado_texto} correctamente.',
                'nuevo_estado': moneda.activa
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al cambiar el estado de la moneda: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ================================
# VISTAS PARA PAGOS
# ================================

from .forms import PagoForm
from .models import Pago

# FUNCIÓN ELIMINADA - Reemplazada por registro_transacciones en views_transacciones.py
# @login_required
# def lista_pagos(request):
#     """Vista para mostrar la lista de pagos"""
#     pagos = Pago.objects.all().order_by('-fecha_creacion')
#     
#     # Paginación
#     paginator = Paginator(pagos, 10)  # 10 pagos por página
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
#     
#     context = {
#         'pagos': page_obj,
#         'title': 'Lista de Pagos'
#     }
#     return render(request, 'remesas/pagos/lista_pagos.html', context)

@login_required
def crear_pago(request):
    """Vista para crear un nuevo pago"""
    if request.method == 'POST':
        # Procesar datos del formulario dual (transferencia/efectivo)
        form_data = request.POST.copy()
        
        # Determinar el tipo de pago seleccionado
        tipo_pago = form_data.get('tipo_pago')
        
        if tipo_pago == 'efectivo':
            # Para efectivo, usar los campos con sufijo _efectivo
            if 'tipo_moneda_efectivo' in form_data:
                form_data['tipo_moneda'] = form_data['tipo_moneda_efectivo']
            if 'cantidad_efectivo' in form_data:
                form_data['cantidad'] = form_data['cantidad_efectivo']
            if 'destinatario_efectivo' in form_data:
                form_data['destinatario'] = form_data['destinatario_efectivo']
            if 'telefono_efectivo' in form_data:
                form_data['telefono'] = form_data['telefono_efectivo']
            if 'direccion_efectivo' in form_data:
                form_data['direccion'] = form_data['direccion_efectivo']
            if 'carnet_identidad_efectivo' in form_data:
                form_data['carnet_identidad'] = form_data['carnet_identidad_efectivo']
        
        form = PagoForm(form_data, request.FILES)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.usuario = request.user  # Asignar el usuario actual
            pago.estado = 'pendiente'  # Los pagos inician en estado pendiente
            
            # Calcular el monto para mostrar en el mensaje
            monto_usd = pago.calcular_monto_en_usd()
            
            # Guardar el pago sin afectar el balance (pendiente)
            pago.save()
            
            # Enviar notificación de nuevo pago
            try:
                from notificaciones.services import WhatsAppService
                servicio = WhatsAppService()
                servicio.enviar_notificacion('pago_nuevo', pago=pago)
            except Exception as e:
                print(f"Error enviando notificación de nuevo pago: {e}")
            
            # Mensaje informativo sobre el estado pendiente
            messages.success(request, f'Pago creado exitosamente. ID: {pago.pago_id}. Estado: Pendiente. El balance se descontará cuando se confirme el pago.')
            
            return redirect('remesas:registro_transacciones')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = PagoForm()
    
    # Obtener datos de monedas para JavaScript con valores específicos del usuario
    monedas_data = {}
    for moneda in form.fields['tipo_moneda'].queryset:
        valor_usuario = moneda.get_valor_para_usuario(request.user)
        monedas_data[moneda.id] = {
            'codigo': moneda.codigo,
            'valor_usuario': float(valor_usuario)
        }
    
    context = {
        'form': form,
        'title': 'Crear Nuevo Pago',
        'action': 'Crear',
        'monedas_data_json': json.dumps(monedas_data)
    }
    return render(request, 'remesas/pagos/pago_form.html', context)

@login_required
def editar_pago(request, pago_id):
    """Vista para editar un pago existente"""
    pago = get_object_or_404(Pago, id=pago_id)
    
    # Guardar valores originales para revertir cambios en el balance si es necesario
    cantidad_original = pago.cantidad
    moneda_original = pago.tipo_moneda
    
    if request.method == 'POST':
        # Verificar si es una petición AJAX
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        try:
            # Procesar datos del formulario
            destinatario = request.POST.get('destinatario')
            cantidad = request.POST.get('cantidad')
            tipo_moneda_id = request.POST.get('tipo_moneda')
            tipo_pago = request.POST.get('tipo_pago')
            telefono = request.POST.get('telefono', '')
            carnet_identidad = request.POST.get('carnet_identidad', '')
            tarjeta = request.POST.get('tarjeta', '')
            direccion = request.POST.get('direccion', '')
            observaciones = request.POST.get('observaciones', '')
            comprobante_pago = request.FILES.get('comprobante_pago')
            
            # Validaciones básicas
            if not destinatario or not cantidad or not tipo_moneda_id or not tipo_pago:
                error_msg = 'Todos los campos obligatorios deben ser completados'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect(request.path)
            
            # Obtener la moneda
            try:
                tipo_moneda = models.Moneda.objects.get(id=tipo_moneda_id)
            except models.Moneda.DoesNotExist:
                error_msg = 'Moneda seleccionada no válida'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect(request.path)
            
            # Validar cantidad
            try:
                cantidad = Decimal(str(cantidad))
                if cantidad <= 0:
                    raise ValueError("La cantidad debe ser positiva")
            except (ValueError, TypeError):
                error_msg = 'La cantidad debe ser un número válido mayor que 0'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect(request.path)
            
            # Validar tarjeta si es transferencia
            if tipo_pago == 'transferencia' and not tarjeta:
                error_msg = 'El número de tarjeta es requerido para transferencias'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect(request.path)
            
            # Calcular diferencia de monto en USD para mensaje informativo
            monto_original_usd = Decimal('0')
            if cantidad_original and moneda_original:
                if moneda_original.codigo == 'USD':
                    monto_original_usd = cantidad_original
                else:
                    monto_original_usd = cantidad_original / moneda_original.valor_actual
            
            # Calcular nuevo monto en USD
            if tipo_moneda.codigo == 'USD':
                monto_nuevo_usd = cantidad
            else:
                monto_nuevo_usd = cantidad / tipo_moneda.valor_actual
            
            # Calcular diferencia para mensaje informativo
            diferencia_usd = monto_nuevo_usd - monto_original_usd
            
            # Actualizar el pago
            pago.destinatario = destinatario
            pago.cantidad = cantidad
            pago.tipo_moneda = tipo_moneda
            pago.tipo_pago = tipo_pago
            pago.telefono = telefono
            pago.carnet_identidad = carnet_identidad
            pago.tarjeta = tarjeta if tipo_pago == 'transferencia' else ''
            pago.direccion = direccion
            pago.observaciones = observaciones
            
            # Actualizar comprobante si se proporciona uno nuevo
            if comprobante_pago:
                pago.comprobante_pago = comprobante_pago
            
            # Guardar primero los cambios básicos
            pago.save()
            
            # Establecer el usuario editor antes del recálculo
            pago.usuario_editor = request.user
            
            # Recalcular valores USD con las tasas actuales después de la edición
            pago.recalcular_valores_por_edicion()
            
            # Calcular balance final real después de la actualización
            perfil = request.user.perfil
            balance_calculado = perfil.calcular_balance_real()
            perfil.actualizar_balance()  # Sincronizar el balance almacenado
            balance_final = balance_calculado
            if diferencia_usd > 0:
                if balance_final < 0:
                    success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se descontaron ${diferencia_usd:.2f} USD adicionales. Tu balance ahora es ${balance_final:.2f} USD (negativo).'
                else:
                    success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se descontaron ${diferencia_usd:.2f} USD adicionales de tu balance.'
            elif diferencia_usd < 0:
                success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se reembolsaron ${abs(diferencia_usd):.2f} USD a tu balance.'
            else:
                success_msg = 'Pago actualizado exitosamente con nuevos valores USD.'
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': success_msg})
            else:
                messages.success(request, success_msg)
                return redirect('remesas:registro_transacciones')
                
        except Exception as e:
            error_msg = f'Error al actualizar el pago: {str(e)}'
            if is_ajax:
                return JsonResponse({'success': False, 'message': error_msg})
            else:
                messages.error(request, error_msg)
                return redirect('remesas:registro_transacciones')
    
    # GET request - mostrar formulario
    # Filtrar monedas según el tipo de pago del pago actual
    monedas = models.Moneda.objects.filter(
        activa=True, 
        tipo_moneda=pago.tipo_pago
    ).order_by('nombre')
    
    context = {
        'pago': pago,
        'monedas': monedas,
        'title': f'Editar Pago {pago.pago_id}'
    }
    return render(request, 'remesas/pagos/editar_pago.html', context)

@login_required
def detalle_pago(request, pago_id):
    """Vista para ver los detalles de un pago"""
    pago = get_object_or_404(Pago, id=pago_id)
    
    # Determinar el tipo de usuario
    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    
    context = {
        'pago': pago,
        'user_tipo': user_tipo,
        'title': f'Detalle del Pago #{pago.id}'
    }
    return render(request, 'remesas/pagos/detalle_pago.html', context)


@login_required
def confirmar_pago(request, pago_id):
    """
    Vista para confirmar un pago (cambia de pendiente a confirmado)
    """
    if request.method == 'POST':
        try:
            pago = get_object_or_404(models.Pago, id=pago_id)
            
            # Verificar que el usuario tenga permisos
            if not (request.user == pago.usuario or 
                    request.user.is_superuser or 
                    (hasattr(request.user, 'perfil') and request.user.perfil.tipo_usuario in ['admin', 'contable'])):
                return JsonResponse({
                    'success': False,
                    'message': 'No tienes permisos para confirmar este pago.'
                })
            
            if not pago.puede_confirmar():
                return JsonResponse({
                    'success': False,
                    'message': f'El pago no puede ser confirmado desde el estado actual: {pago.get_estado_display()}'
                })
            
            # Confirmar el pago (esto descuenta del balance)
            if pago.confirmar():
                # Enviar notificación de cambio de estado
                try:
                    from notificaciones.services import WhatsAppService
                    servicio = WhatsAppService()
                    servicio.enviar_notificacion('pago_estado', pago=pago, estado_anterior='pendiente')
                except Exception as e:
                    print(f"Error enviando notificación de cambio de estado: {e}")
                
                # Obtener balance actualizado dinámicamente
                if hasattr(pago.usuario, 'perfil'):
                    balance_calculado = pago.usuario.perfil.calcular_balance_real()
                    pago.usuario.perfil.actualizar_balance()  # Sincronizar balance almacenado
                    balance_final = balance_calculado
                else:
                    balance_final = 0
                monto_usd = pago.calcular_monto_en_usd()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Pago #{pago.pago_id} confirmado exitosamente. Se descontaron ${monto_usd:.2f} USD. Balance actual: ${balance_final:.2f} USD'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Error al confirmar el pago. Por favor intenta de nuevo.'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al confirmar el pago: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)


@login_required
def cancelar_pago(request, pago_id):
    """
    Vista para cancelar un pago (cambia de pendiente a cancelado)
    """
    if request.method == 'POST':
        try:
            pago = get_object_or_404(models.Pago, id=pago_id)
            
            # Verificar que el usuario tenga permisos
            if not (request.user == pago.usuario or 
                    request.user.is_superuser or 
                    (hasattr(request.user, 'perfil') and request.user.perfil.tipo_usuario in ['admin', 'contable'])):
                return JsonResponse({
                    'success': False,
                    'message': 'No tienes permisos para cancelar este pago.'
                })
            
            if not pago.puede_cancelar():
                return JsonResponse({
                    'success': False,
                    'message': f'El pago no puede ser cancelado desde el estado actual: {pago.get_estado_display()}'
                })
            
            # Cancelar el pago
            if pago.cancelar():
                # Enviar notificación de cambio de estado
                try:
                    from notificaciones.services import WhatsAppService
                    servicio = WhatsAppService()
                    servicio.enviar_notificacion('pago_estado', pago=pago, estado_anterior='pendiente')
                except Exception as e:
                    print(f"Error enviando notificación de cambio de estado: {e}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Pago #{pago.pago_id} cancelado exitosamente.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Error al cancelar el pago. Por favor intenta de nuevo.'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al cancelar el pago: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)


# FUNCIÓN ELIMINADA - Reemplazada por la nueva función eliminar_pago con restricciones de admin

@csrf_exempt
@require_http_methods(["GET"])
def api_balance_usuario(request):
    """
    API endpoint para obtener el balance actualizado del usuario
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Usuario no autenticado'
        }, status=401)
    
    try:
        # Invalidar cache del balance
        from .context_processors import invalidate_user_balance_cache
        invalidate_user_balance_cache(request.user.id)
        
        if request.user.is_superuser:
            balance = Decimal('0.00')
            tipo_usuario = 'admin'
        else:
            perfil = request.user.perfil
            balance = perfil.calcular_balance_real()
            tipo_usuario = perfil.tipo_usuario
            
            # Actualizar balance almacenado
            perfil.actualizar_balance()
        
        return JsonResponse({
            'success': True,
            'balance': float(balance),
            'balance_formatted': f"{balance:,.2f}",
            'moneda': 'USD',
            'tipo_usuario': tipo_usuario
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error calculando balance: {str(e)}'
        }, status=500)


# ===== VISTAS PARA TIPOS DE VALORES DE MONEDAS =====

@login_required
def lista_tipos_valores(request):
    """Vista para listar tipos de valores de monedas"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('remesas:lista_monedas')
    
    tipos_valores = models.TipoValorMoneda.objects.all().order_by('orden', 'nombre')
    
    context = {
        'tipos_valores': tipos_valores,
        'page_title': 'Tipos de Valores de Monedas'
    }
    return render(request, 'remesas/tipos_valores/lista.html', context)


@login_required
def crear_tipo_valor(request):
    """Vista para crear un nuevo tipo de valor de moneda"""
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            orden = request.POST.get('orden', 0)
            
            print(f"Datos recibidos - Nombre: {nombre}, Descripción: {descripcion}, Orden: {orden}")  # Debug
            
            if not nombre:
                return JsonResponse({'success': False, 'message': 'El nombre es requerido'})
            
            # Verificar que no exista un tipo con el mismo nombre (case insensitive)
            if models.TipoValorMoneda.objects.filter(nombre__iexact=nombre).exists():
                return JsonResponse({'success': False, 'message': 'Ya existe un tipo con ese nombre'})
            
            # Crear el tipo de valor
            tipo_valor = models.TipoValorMoneda.objects.create(
                nombre=nombre,
                descripcion=descripcion if descripcion else '',
                orden=int(orden) if orden else 0,
                creado_por=request.user
            )
            
            print(f"Tipo de valor creado exitosamente: {tipo_valor} (ID: {tipo_valor.id})")  # Debug
            
            return JsonResponse({
                'success': True, 
                'message': f'Tipo de valor "{nombre}" creado exitosamente'
            })
            
        except Exception as e:
            print(f"Error en crear_tipo_valor: {str(e)}")  # Debug
            import traceback
            traceback.print_exc()  # Debug completo
            
            return JsonResponse({'success': False, 'message': f'Error al crear tipo de valor: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
def editar_tipo_valor(request, tipo_id):
    """Vista para editar un tipo de valor de moneda"""
    # Temporalmente removemos la restricción de superuser para hacer pruebas
    # if not request.user.is_superuser:
    #     return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)
    
    tipo_valor = get_object_or_404(models.TipoValorMoneda, id=tipo_id)
    
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            orden = request.POST.get('orden', 0)
            
            if not nombre:
                return JsonResponse({'success': False, 'message': 'El nombre es requerido'})
            
            # Verificar que no exista otro tipo con el mismo nombre
            if models.TipoValorMoneda.objects.filter(nombre__iexact=nombre).exclude(id=tipo_id).exists():
                return JsonResponse({'success': False, 'message': 'Ya existe un tipo con ese nombre'})
            
            # Actualizar el tipo de valor
            tipo_valor.nombre = nombre
            tipo_valor.descripcion = descripcion if descripcion else ''
            tipo_valor.orden = int(orden) if orden else 0
            tipo_valor.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Tipo de valor "{nombre}" actualizado exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al actualizar: {str(e)}'})
    
    # Solo devolver error para métodos no permitidos
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def eliminar_tipo_valor(request, tipo_id):
    """Vista para eliminar un tipo de valor de moneda"""
    # Temporalmente removemos la restricción de superuser para hacer pruebas
    # if not request.user.is_superuser:
    #     return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)
    
    if request.method == 'POST':
        try:
            tipo_valor = get_object_or_404(models.TipoValorMoneda, id=tipo_id)
            
            # Verificar que no sea el único tipo activo
            tipos_activos = models.TipoValorMoneda.objects.filter(activo=True).count()
            if tipos_activos <= 1 and tipo_valor.activo:
                return JsonResponse({
                    'success': False, 
                    'message': 'No se puede eliminar el único tipo de valor activo'
                })
            
            # Verificar que no haya usuarios usando este tipo
            from login.models import PerfilUsuario
            usuarios_usando = PerfilUsuario.objects.filter(tipo_valor_moneda=tipo_valor).count()
            if usuarios_usando > 0:
                return JsonResponse({
                    'success': False, 
                    'message': f'No se puede eliminar. {usuarios_usando} usuarios están usando este tipo de valor'
                })
            
            nombre = tipo_valor.nombre
            tipo_valor.delete()
            
            return JsonResponse({
                'success': True, 
                'message': f'Tipo de valor "{nombre}" eliminado exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
def toggle_estado_tipo_valor(request, tipo_id):
    """Vista para activar/desactivar un tipo de valor de moneda"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)
    
    if request.method == 'POST':
        try:
            tipo_valor = get_object_or_404(models.TipoValorMoneda, id=tipo_id)
            
            # Si se intenta desactivar, verificar que no sea el único activo
            if tipo_valor.activo:
                tipos_activos = models.TipoValorMoneda.objects.filter(activo=True).count()
                if tipos_activos <= 1:
                    return JsonResponse({
                        'success': False, 
                        'message': 'No se puede desactivar el único tipo de valor activo'
                    })
            
            # Cambiar estado
            tipo_valor.activo = not tipo_valor.activo
            tipo_valor.save()
            
            estado_texto = 'activado' if tipo_valor.activo else 'desactivado'
            return JsonResponse({
                'success': True, 
                'message': f'Tipo de valor "{tipo_valor.nombre}" {estado_texto} exitosamente',
                'nuevo_estado': tipo_valor.activo
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
def actualizar_valores_monedas(request):
    """Vista para actualizar valores de monedas masivamente"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            valores_actualizados = 0
            
            for item in data.get('valores', []):
                moneda_id = item.get('moneda_id')
                tipo_valor_id = item.get('tipo_valor_id')
                nuevo_valor = item.get('valor')
                
                if moneda_id and tipo_valor_id and nuevo_valor is not None:
                    try:
                        moneda = models.Moneda.objects.get(id=moneda_id)
                        tipo_valor = models.TipoValorMoneda.objects.get(id=tipo_valor_id)
                        
                        valor_obj, created = models.ValorMoneda.objects.get_or_create(
                            moneda=moneda,
                            tipo_valor=tipo_valor,
                            defaults={'valor': Decimal(str(nuevo_valor)), 'actualizado_por': request.user}
                        )
                        
                        if not created:
                            valor_obj.valor = Decimal(str(nuevo_valor))
                            valor_obj.actualizado_por = request.user
                            valor_obj.save()
                        
                        valores_actualizados += 1
                        
                    except (models.Moneda.DoesNotExist, models.TipoValorMoneda.DoesNotExist, ValueError):
                        continue
            
            return JsonResponse({
                'success': True, 
                'message': f'{valores_actualizados} valores actualizados exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@require_POST
def actualizar_valor_individual(request):
    """
    Vista para actualizar un valor individual de moneda (AJAX)
    IMPORTANTE: No afecta operaciones históricas
    """
    try:
        import json
        data = json.loads(request.body)
        
        moneda_id = data.get('moneda_id')
        tipo_id = data.get('tipo_id')
        nuevo_valor = data.get('valor')
        
        if not all([moneda_id, tipo_id, nuevo_valor is not None]):
            return JsonResponse({'success': False, 'message': 'Datos incompletos'})
        
        # Validar que el valor sea positivo
        try:
            nuevo_valor = Decimal(str(nuevo_valor))
            if nuevo_valor < 0:
                return JsonResponse({'success': False, 'message': 'El valor no puede ser negativo'})
        except (ValueError, decimal.InvalidOperation):
            return JsonResponse({'success': False, 'message': 'Valor numérico inválido'})
        
        # Obtener la moneda y tipo de valor
        try:
            moneda = models.Moneda.objects.get(id=moneda_id)
            tipo_valor = models.TipoValorMoneda.objects.get(id=tipo_id)
        except (models.Moneda.DoesNotExist, models.TipoValorMoneda.DoesNotExist):
            return JsonResponse({'success': False, 'message': 'Moneda o tipo de valor no encontrado'})
        
        # Crear o actualizar el valor
        valor_obj, created = models.ValorMoneda.objects.update_or_create(
            moneda=moneda,
            tipo_valor=tipo_valor,
            defaults={
                'valor': nuevo_valor,
                'actualizado_por': request.user
            }
        )
        
        # Log de la operación para auditoria
        action = 'creado' if created else 'actualizado'
        print(f"Valor {action} - Usuario: {request.user.username}, Moneda: {moneda.codigo}, Tipo: {tipo_valor.nombre}, Valor: {nuevo_valor}")
        
        return JsonResponse({
            'success': True,
            'message': f'Valor actualizado exitosamente para {moneda.codigo} - {tipo_valor.nombre}',
            'nuevo_valor': float(nuevo_valor)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'})


@login_required  
@require_POST
def crear_tipo_valor(request):
    """
    Vista para crear un nuevo tipo de valor de moneda
    """
    try:
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        orden = request.POST.get('orden', '0')
        
        if not nombre:
            return JsonResponse({'success': False, 'message': 'El nombre es requerido'})
        
        # Validar que no exista un tipo con el mismo nombre
        if models.TipoValorMoneda.objects.filter(nombre__iexact=nombre).exists():
            return JsonResponse({'success': False, 'message': 'Ya existe un tipo de valor con este nombre'})
        
        # Validar orden
        try:
            orden = int(orden)
        except ValueError:
            orden = 0
        
        # Crear el nuevo tipo de valor
        nuevo_tipo = models.TipoValorMoneda.objects.create(
            nombre=nombre,
            descripcion=descripcion or None,
            orden=orden,
            creado_por=request.user
        )
        
        # Crear valores por defecto (0) para todas las monedas existentes
        monedas = models.Moneda.objects.all()
        valores_creados = 0
        
        for moneda in monedas:
            models.ValorMoneda.objects.create(
                moneda=moneda,
                tipo_valor=nuevo_tipo,
                valor=Decimal('0'),
                actualizado_por=request.user
            )
            valores_creados += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Tipo de valor "{nombre}" creado exitosamente. Se inicializaron {valores_creados} valores en 0.',
            'tipo_id': nuevo_tipo.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error al crear tipo de valor: {str(e)}'})
