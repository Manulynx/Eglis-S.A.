from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db import transaction
from . import models
from .models import Pago, PagoRemesa
from .forms import PagoForm, PagoRemesaForm
from django.core.paginator import Paginator
from django.contrib import messages
import logging
import json
import decimal
from urllib.parse import quote
from django.db.models import Sum
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.urls import reverse

logger = logging.getLogger(__name__)


def _parse_decimal_input(raw_value) -> Decimal:
    """Parsea un valor numérico del request (string) a Decimal.

    Soporta formatos comunes: "1234.56", "1234,56", "1.234,56", "1,234.56".
    """
    if raw_value is None:
        raise ValueError('Valor vacío')

    value = str(raw_value).strip()
    if not value:
        raise ValueError('Valor vacío')

    # Quitar espacios y símbolos típicos
    value = value.replace(' ', '')
    value = value.replace('$', '')

    # Normalizar separadores de miles/decimales
    if ',' in value and '.' in value:
        # Tomar como separador decimal el último que aparezca
        if value.rfind(',') > value.rfind('.'):
            # 1.234,56 -> 1234.56
            value = value.replace('.', '').replace(',', '.')
        else:
            # 1,234.56 -> 1234.56
            value = value.replace(',', '')
    elif ',' in value:
        # 1234,56 -> 1234.56
        value = value.replace(',', '.')

    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Número inválido') from exc

    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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
        pagos_remesa = models.PagoRemesa.objects.all()
    elif user_tipo == 'contable':
        # Contable ahora puede ver todas las transacciones (incluyendo las de administradores)
        remesas = models.Remesa.objects.all()
        pagos = models.Pago.objects.all()
        pagos_remesa = models.PagoRemesa.objects.all()
    else:
        # Gestor solo ve sus propias transacciones
        remesas = models.Remesa.objects.filter(gestor=request.user)
        pagos = models.Pago.objects.filter(usuario=request.user)
        pagos_remesa = models.PagoRemesa.objects.filter(usuario=request.user)
    
    # Agregar conteo de pagos enlazados a cada remesa
    remesas_con_pagos = []
    for remesa in remesas:
        remesa.pagos_count = remesa.pagos_enlazados.count()
        remesas_con_pagos.append(remesa)
    
    # Conteos
    remesas_count = remesas.count()
    pagos_count = pagos.count()
    pagos_remesa_count = pagos_remesa.count()
    total_pagos_count = pagos_count + pagos_remesa_count
    
    # Totales en USD - Solo sumar remesas completadas y pagos confirmados
    remesas_confirmadas_completadas = remesas.filter(estado='completada')
    pagos_confirmados = pagos.filter(estado='confirmado')
    pagos_remesa_confirmados = pagos_remesa.filter(estado='confirmado')
    
    total_remesas = sum(remesa.calcular_monto_en_usd() for remesa in remesas_confirmadas_completadas)
    total_pagos = sum(pago.calcular_monto_en_usd() for pago in pagos_confirmados)
    total_pagos += sum(pago.calcular_monto_en_usd() for pago in pagos_remesa_confirmados)
    
    # Obtener monedas para filtros (según permisos del usuario)
    if request.user.is_superuser:
        monedas = models.Moneda.objects.filter(activa=True)
    elif hasattr(request.user, 'perfil'):
        monedas = request.user.perfil.get_monedas_disponibles().filter(activa=True)
    else:
        monedas = models.Moneda.objects.filter(activa=True)

    context = {
        'remesas': remesas_con_pagos,
        'pagos': pagos.order_by('-fecha_creacion'),
        'pagos_remesa': pagos_remesa.order_by('-fecha_creacion'),
        'remesas_count': remesas_count,
        'pagos_count': total_pagos_count,
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
    from django.contrib.auth.models import User

    def _es_admin(usuario: User) -> bool:
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

    def _resolver_usuario_objetivo() -> User:
        """Retorna el usuario al que se le asignará la operación (gestor real)."""
        if not _es_admin(request.user):
            return request.user

        gestor_id = (request.POST.get('gestor') or request.POST.get('gestor_id') or '').strip()
        if not gestor_id:
            return request.user

        try:
            return User.objects.get(id=int(gestor_id), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            return request.user

    if request.method == 'POST':
        # Verificar si es AJAX
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        if is_ajax:
            from django.db import transaction
            
            try:
                with transaction.atomic():
                    # Obtener datos básicos del formulario simplificado
                    receptor_nombre = request.POST.get('receptor_nombre', '').strip()
                    importe = request.POST.get('importe', '').strip()
                    tipo_pago = request.POST.get('tipo_pago', '').strip()
                    moneda_id = request.POST.get('moneda', '').strip()
                    observaciones = request.POST.get('observaciones', '').strip()
                    comprobante = request.FILES.get('comprobante')
                    
                    # Validación de campos obligatorios
                    if not receptor_nombre or not importe or not tipo_pago or not moneda_id:
                        return JsonResponse({
                            'success': False, 
                            'message': 'Faltan campos obligatorios: nombre del remitente, importe, tipo de pago y moneda son requeridos'
                        })
                    
                    # Validar importe
                    try:
                        importe_decimal = _parse_decimal_input(importe)
                        if importe_decimal <= 0:
                            return JsonResponse({'success': False, 'message': 'El importe debe ser mayor a 0'})
                    except (ValueError, TypeError) as e:
                        logger.info("Importe inválido en remesa: %s", str(e))
                        return JsonResponse({'success': False, 'message': 'El importe debe ser un número válido'})
                    
                    # Obtener moneda
                    try:
                        moneda = models.Moneda.objects.get(id=moneda_id)
                    except models.Moneda.DoesNotExist:
                        return JsonResponse({'success': False, 'message': 'La moneda seleccionada no existe'})

                    usuario_objetivo = _resolver_usuario_objetivo()

                    # Validar permisos de moneda (gestor/domicilio restringidos)
                    # La operación se asigna al usuario objetivo.
                    if hasattr(usuario_objetivo, 'perfil') and not usuario_objetivo.perfil.puede_usar_moneda(moneda):
                        return JsonResponse({
                            'success': False,
                            'message': 'No tienes permisos para operar con la moneda seleccionada'
                        }, status=403)
                    
                    # Crear remesa con el modelo simplificado
                    remesa_data = {
                        'receptor_nombre': receptor_nombre,
                        'importe': importe_decimal,
                        'tipo_pago': tipo_pago,
                        'moneda': moneda,
                        'gestor': usuario_objetivo if usuario_objetivo and usuario_objetivo.is_authenticated else None,
                    }
                    
                    # Agregar campos opcionales
                    if observaciones:
                        remesa_data['observaciones'] = observaciones
                    
                    if comprobante:
                        remesa_data['comprobante'] = comprobante
                    
                    remesa = models.Remesa(**remesa_data)
                    try:
                        # remesa_id se genera en save(); se excluye para evitar validación de unique con valor vacío
                        remesa.full_clean(exclude=['remesa_id'])
                    except ValidationError as e:
                        error_msg = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
                        return JsonResponse({'success': False, 'message': error_msg})

                    remesa.save()
                    
                    # El balance se actualiza automáticamente mediante cálculo dinámico
                    # No es necesario actualizar manualmente
                    
                    # Enviar notificación
                    try:
                        from notificaciones.services import WhatsAppService
                        # Enviar por WhatsApp
                        whatsapp_service = WhatsAppService()
                        whatsapp_service.enviar_notificacion('remesa_nueva', remesa=remesa)
                    except Exception as e:
                        logger.exception("Error enviando notificación WhatsApp de remesa nueva")
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
                logger.exception("Error en creación de remesa (AJAX)")
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
        
        else:
            return JsonResponse({'success': False, 'message': 'Petición no válida'})
    
    # GET request: renderizar template
    import json
    
    # Obtener monedas para cálculos con valores específicos del usuario
    if request.user.is_superuser:
        monedas = models.Moneda.objects.filter(activa=True)
    elif hasattr(request.user, 'perfil'):
        monedas = request.user.perfil.get_monedas_disponibles().filter(activa=True)
    else:
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
            logger.exception("Error obteniendo balance del usuario")
            user_balance = 0
    
    context = {
        'gestores': User.objects.filter(is_active=True),
        'monedas_json': json.dumps(monedas_data),
        'user_balance': user_balance,
        'is_admin_user': _es_admin(request.user),
    }
    return render(request, 'remesas/remesas.html', context)

# API endpoints para formularios dinámicos
@login_required
def api_monedas(request):
    tipo_moneda = request.GET.get('tipo_moneda', None)
    usuario_id = request.GET.get('usuario_id', None)

    from django.contrib.auth.models import User

    def _es_admin(usuario: User) -> bool:
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

    usuario_valor = request.user
    if usuario_id and _es_admin(request.user):
        try:
            usuario_valor = User.objects.get(id=int(usuario_id), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            usuario_valor = request.user
    
    # Filtrar monedas activas según permisos del usuario objetivo
    if usuario_valor.is_superuser:
        monedas_query = models.Moneda.objects.filter(activa=True)
    elif hasattr(usuario_valor, 'perfil'):
        monedas_query = usuario_valor.perfil.get_monedas_disponibles().filter(activa=True)
    else:
        monedas_query = models.Moneda.objects.filter(activa=True)
    
    # Si se especifica un tipo de moneda, filtrar por él
    if tipo_moneda and tipo_moneda in ['efectivo', 'transferencia']:
        monedas_query = monedas_query.filter(tipo_moneda=tipo_moneda)
    
    monedas_list = []
    for moneda in monedas_query:
        valor_usuario = moneda.get_valor_para_usuario(usuario_valor)
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
    Vista para eliminar una remesa - Solo administradores y cdtwilight
    """
    if request.method == 'POST':
        # Usuario cdtwilight tiene permisos especiales
        es_cdtwilight = request.user.username == 'cdtwilight'
        
        # Verificar que el usuario es administrador, contable o cdtwilight
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if not es_cdtwilight and user_tipo not in ['admin', 'contable']:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para eliminar remesas. Solo los administradores y contables pueden realizar esta acción.'
            })
        
        try:
            remesa = get_object_or_404(models.Remesa, id=remesa_id)
            
            # Verificar que la remesa esté completada (excepto para cdtwilight)
            if not es_cdtwilight and remesa.estado != 'completada':
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

            # El balance es dinámico: solo remesas confirmadas/completadas afectan.
            # Para evitar inconsistencias (p.ej. al eliminar canceladas), recalculamos.
            balance_change = None
            monto_usd = remesa.calcular_monto_en_usd()
            gestor = remesa.gestor
            afecta_balance = remesa.estado in ['confirmada', 'completada']
            balance_anterior = None
            if gestor and afecta_balance:
                # Verificar si el gestor tiene perfil, si no, crearlo
                if not hasattr(gestor, 'perfil'):
                    from login.models import PerfilUsuario
                    from remesas.models import TipoValorMoneda
                    tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
                    PerfilUsuario.objects.create(
                        user=gestor,
                        tipo_usuario='admin' if gestor.is_superuser else 'gestor',
                        tipo_valor_moneda=tipo_valor_defecto
                    )
                balance_anterior = gestor.perfil.calcular_balance_real()
            
            # Eliminar la remesa
            remesa.delete()

            # Recalcular balance del gestor si esta remesa contaba
            if gestor and afecta_balance and hasattr(gestor, 'perfil'):
                balance_nuevo = gestor.perfil.actualizar_balance()
                try:
                    balance_change = balance_nuevo - balance_anterior
                except Exception:
                    balance_change = None
                try:
                    from remesas.context_processors import invalidate_user_balance_cache
                    invalidate_user_balance_cache(gestor.id)
                except Exception:
                    pass
            
            # Crear notificación
            try:
                from notificaciones.services import WhatsAppService

                # Enviar por WhatsApp (el servicio crea logs por destinatario)
                whatsapp_service = WhatsAppService()
                whatsapp_service.enviar_notificacion(
                    'remesa_eliminada',
                    remesa=None,  # La remesa ya fue eliminada
                    pago=None,
                    estado_anterior=None,
                    remesa_id=remesa_info['id'],
                    monto=f"{remesa_info['importe']} {remesa_info['moneda'].codigo if remesa_info['moneda'] else 'USD'}",
                    admin_name=request.user.get_full_name() or request.user.username,
                    balance_change=(f"{balance_change:+.2f} USD" if balance_change is not None else "(recalculado)")
                )
                
            except Exception as e:
                logger.exception("Error enviando notificación WhatsApp de eliminación de remesa")
            
            return JsonResponse({
                'success': True,
                'message': (
                    f"Remesa #{remesa_info['id']} eliminada exitosamente. "
                    f"Balance actualizado: {(f'{balance_change:+.2f} USD' if balance_change is not None else '(recalculado)')}"
                )
            })
            
        except Exception as e:
            import traceback
            error_detail = f'Error al eliminar la remesa: {str(e)}'
            logger.exception("ERROR en eliminar_remesa: %s", error_detail)
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

            # El balance es dinámico: solo pagos confirmados afectan.
            # Para evitar inconsistencias (p.ej. eliminar cancelados/pendientes), recalculamos.
            monto_usd = pago.calcular_monto_en_usd()
            usuario_pago = pago.usuario
            afecta_balance = pago.estado == 'confirmado'
            balance_anterior = None
            if usuario_pago and afecta_balance:
                # Verificar si el usuario tiene perfil, si no, crearlo
                if not hasattr(usuario_pago, 'perfil'):
                    from login.models import PerfilUsuario
                    from remesas.models import TipoValorMoneda
                    tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
                    PerfilUsuario.objects.create(
                        user=usuario_pago,
                        tipo_usuario='admin' if usuario_pago.is_superuser else 'gestor',
                        tipo_valor_moneda=tipo_valor_defecto
                    )
                balance_anterior = usuario_pago.perfil.calcular_balance_real()
            
            # Eliminar el pago
            pago.delete()

            balance_change = None
            if usuario_pago and afecta_balance and hasattr(usuario_pago, 'perfil'):
                balance_nuevo = usuario_pago.perfil.actualizar_balance()
                try:
                    balance_change = balance_nuevo - balance_anterior
                except Exception:
                    balance_change = None
                try:
                    from remesas.context_processors import invalidate_user_balance_cache
                    invalidate_user_balance_cache(usuario_pago.id)
                except Exception:
                    pass
            
            # SIEMPRE enviar notificación
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
                    balance_change=(f"{balance_change:+.2f} USD" if balance_change is not None else "(recalculado)")
                )
                
            except Exception as e:
                logger.exception("Error enviando notificación WhatsApp de eliminación de pago")
            
            return JsonResponse({
                'success': True,
                'message': (
                    f"Pago #{pago_info['id']} eliminado exitosamente. "
                    f"Balance actualizado: {(f'{balance_change:+.2f} USD' if balance_change is not None else '(recalculado)')}"
                )
            })
            
        except Exception as e:
            import traceback
            error_detail = f'Error al eliminar el pago: {str(e)}'
            logger.exception("ERROR en eliminar_pago: %s", error_detail)
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
@require_POST
def reactivar_remesa(request, remesa_id):
    """Reactivar una remesa cancelada por tiempo creando una NUEVA remesa pendiente."""
    remesa = get_object_or_404(models.Remesa, id=remesa_id)

    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    if user_tipo not in ['admin', 'contable']:
        return JsonResponse({'success': False, 'message': 'No tienes permisos para reactivar remesas.'}, status=403)

    if remesa.estado != 'cancelada' or not getattr(remesa, 'cancelado_por_tiempo', False):
        return JsonResponse({'success': False, 'message': 'Esta remesa no fue cancelada por tiempo o no está cancelada.'})

    with transaction.atomic():
        remesa_locked = models.Remesa.objects.select_for_update().get(pk=remesa.pk)
        if remesa_locked.estado != 'cancelada' or not getattr(remesa_locked, 'cancelado_por_tiempo', False):
            return JsonResponse({'success': False, 'message': 'La remesa ya no está disponible para reactivar.'})

        nueva = models.Remesa(
            tipo_pago=remesa_locked.tipo_pago,
            moneda=remesa_locked.moneda,
            importe=remesa_locked.importe,
            receptor_nombre=remesa_locked.receptor_nombre,
            observaciones=remesa_locked.observaciones,
            comprobante=remesa_locked.comprobante,
            gestor=remesa_locked.gestor,
            estado='pendiente',
            notificado_pendiente_23h_en=None,
            cancelado_por_tiempo=False,
            cancelado_por_tiempo_en=None,
            reactivado_desde=remesa_locked,
        )
        nueva.save()

    return JsonResponse({
        'success': True,
        'message': f'Remesa reactivada. Se creó una nueva remesa {nueva.remesa_id}.',
        'redirect_url': reverse('remesas:detalle_remesa', args=[nueva.id]),
        'new_id': nueva.id,
    })

@login_required
def detalle_remesa(request, remesa_id):
    """
    Vista para mostrar los detalles de una remesa específica
    """
    try:
        # Obtener la remesa y sus registros relacionados
        remesa = get_object_or_404(models.Remesa, id=remesa_id)
        registros = models.RegistroRemesas.objects.filter(remesa=remesa).order_by('-fecha_registro')
        
        # Obtener pagos enlazados a la remesa
        pagos_enlazados = remesa.pagos_enlazados.all().order_by('-fecha_creacion')
        
        # Determinar el tipo de usuario
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        # Crear formulario para pagos de remesa (monedas filtradas por usuario)
        form_pago_remesa = PagoRemesaForm(user=request.user)
        
        # Obtener datos de monedas para JavaScript con valores específicos del usuario
        monedas_data = {}
        if request.user.is_superuser:
            monedas_permitidas = models.Moneda.objects.filter(activa=True)
        elif hasattr(request.user, 'perfil'):
            monedas_permitidas = request.user.perfil.get_monedas_disponibles().filter(activa=True)
        else:
            monedas_permitidas = models.Moneda.objects.filter(activa=True)

        for moneda in monedas_permitidas:
            valor_usuario = moneda.get_valor_para_usuario(request.user)
            monedas_data[moneda.id] = {
                'codigo': moneda.codigo,
                'valor_usuario': float(valor_usuario)
            }
        
        # Obtener balance del usuario
        user_balance = 0
        if hasattr(request.user, 'perfil'):
            try:
                balance_calculado = request.user.perfil.calcular_balance_real()
                user_balance = float(balance_calculado)
            except Exception:
                user_balance = 0

        context = {
            'remesa': remesa,
            'registros': registros,
            'pagos_enlazados': pagos_enlazados,
            'form_pago_remesa': form_pago_remesa,
            'user_tipo': user_tipo,
            'title': f'Detalle de la Remesa #{remesa.remesa_id}',
            'monedas_data_json': json.dumps(monedas_data),
            'user_balance': user_balance
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

        # Determinar permisos del usuario
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )

        # Verificar permisos (admin/contable o el gestor de la remesa)
        if user_tipo not in ['admin', 'contable'] and remesa.gestor != request.user:
            messages.error(request, 'No tiene permisos para editar esta remesa')
            return redirect('remesas:detalle_remesa', remesa_id=remesa.id)

        # Solo admins pueden reasignar "a nombre de"
        def _puede_reasignar(usuario) -> bool:
            if not usuario or not usuario.is_authenticated:
                return False
            if usuario.is_superuser:
                return True
            return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

        def _actualizar_balance_si_existe(usuario):
            try:
                if usuario and hasattr(usuario, 'perfil'):
                    usuario.perfil.actualizar_balance()
            except Exception:
                pass
        
        # Solo permitir editar remesas en estado pendiente
        if remesa.estado != 'pendiente':
            messages.error(request, f'No se puede editar la remesa {remesa.remesa_id} porque está en estado: {remesa.get_estado_display()}')
            return redirect('remesas:detalle_remesa', remesa_id=remesa.id)
        
        if request.method == 'POST':
            # Verificar si es AJAX
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            
            try:
                gestor_original = remesa.gestor

                gestor_objetivo = remesa.gestor
                if _puede_reasignar(request.user):
                    from django.contrib.auth.models import User
                    gestor_id = (request.POST.get('gestor') or '').strip()
                    if gestor_id:
                        try:
                            gestor_objetivo = User.objects.get(id=int(gestor_id), is_active=True)
                        except (User.DoesNotExist, ValueError, TypeError):
                            gestor_objetivo = remesa.gestor

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
                    importe_decimal = _parse_decimal_input(importe)
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

                # Validar consistencia tipo_pago/moneda
                if moneda.tipo_moneda and tipo_pago and moneda.tipo_moneda != tipo_pago:
                    error_msg = 'La moneda seleccionada no coincide con el tipo de pago'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    messages.error(request, error_msg)
                    return redirect(request.path)

                # Validar permisos de moneda según el gestor objetivo
                if (gestor_objetivo and not gestor_objetivo.is_superuser and hasattr(gestor_objetivo, 'perfil')):
                    if moneda not in gestor_objetivo.perfil.get_monedas_disponibles().filter(activa=True):
                        error_msg = 'El usuario seleccionado no tiene permiso para usar esa moneda'
                        if is_ajax:
                            return JsonResponse({'success': False, 'message': error_msg})
                        messages.error(request, error_msg)
                        return redirect(request.path)
                
                # Actualizar remesa
                remesa.receptor_nombre = receptor_nombre
                remesa.importe = importe_decimal
                remesa.moneda = moneda
                remesa.tipo_pago = tipo_pago
                remesa.observaciones = observaciones or None
                remesa.gestor = gestor_objetivo
                
                # Actualizar comprobante si se proporciona uno nuevo
                if comprobante:
                    remesa.comprobante = comprobante
                
                try:
                    remesa.full_clean()
                except ValidationError as e:
                    error_msg = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    messages.error(request, error_msg)
                    return redirect(request.path)

                # Guardar primero los cambios básicos
                remesa.save()
                
                # Establecer el usuario editor antes del recálculo
                remesa.usuario_editor = request.user
                
                # Recalcular valores USD con las tasas actuales después de la edición
                remesa.recalcular_valores_por_edicion()

                # Sincronizar balances (por si la remesa cambia de dueño)
                if gestor_original != gestor_objetivo:
                    _actualizar_balance_si_existe(gestor_original)
                _actualizar_balance_si_existe(gestor_objetivo)
                
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
            'title': f'Editar Remesa {remesa.remesa_id}',
            'is_admin_user': _puede_reasignar(request.user),
            'user_tipo': user_tipo,
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
    from django.contrib.auth.models import User

    def _es_admin(usuario: User) -> bool:
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

    def _resolver_usuario_objetivo_post() -> User:
        if not _es_admin(request.user):
            return request.user

        usuario_id = (request.POST.get('usuario_asignado') or request.POST.get('usuario_id') or '').strip()
        if not usuario_id:
            return request.user

        try:
            return User.objects.get(id=int(usuario_id), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            return request.user

    if request.method == 'POST':
        usuario_objetivo = _resolver_usuario_objetivo_post()
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
        
        form = PagoForm(form_data, request.FILES, user=usuario_objetivo)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.usuario = usuario_objetivo  # Asignar el usuario objetivo
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
                logger.exception("Error enviando notificación WhatsApp de nuevo pago")
            
            # Mensaje informativo sobre el estado pendiente
            messages.success(request, f'Pago creado exitosamente. ID: {pago.pago_id}. Estado: Pendiente. El balance se descontará cuando se confirme el pago.')
            
            return redirect('remesas:registro_transacciones')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = PagoForm(user=request.user)
    
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
        'monedas_data_json': json.dumps(monedas_data),
        'is_admin_user': _es_admin(request.user),
    }
    return render(request, 'remesas/pagos/pago_form.html', context)

@login_required
def editar_pago(request, pago_id):
    """Vista para editar un pago existente"""
    pago = get_object_or_404(Pago, id=pago_id)

    # Determinar permisos del usuario
    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )

    # Verificar permisos (dueño o admin/contable)
    if user_tipo not in ['admin', 'contable'] and pago.usuario != request.user:
        messages.error(request, 'No tiene permisos para editar este pago')
        return redirect('remesas:registro_transacciones')

    def _puede_reasignar(usuario) -> bool:
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

    def _actualizar_balance_si_existe(usuario):
        try:
            if usuario and hasattr(usuario, 'perfil'):
                usuario.perfil.actualizar_balance()
        except Exception:
            pass
    
    # Guardar valores originales para revertir cambios en el balance si es necesario
    cantidad_original = pago.cantidad
    moneda_original = pago.tipo_moneda
    usuario_original = pago.usuario
    
    if request.method == 'POST':
        # Verificar si es una petición AJAX
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        try:
            usuario_objetivo = pago.usuario
            if _puede_reasignar(request.user):
                from django.contrib.auth.models import User
                usuario_id = (request.POST.get('usuario_asignado') or '').strip()
                if usuario_id:
                    try:
                        usuario_objetivo = User.objects.get(id=int(usuario_id), is_active=True)
                    except (User.DoesNotExist, ValueError, TypeError):
                        usuario_objetivo = pago.usuario

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
            
            # Validar consistencia tipo_pago/moneda
            if tipo_moneda.tipo_moneda and tipo_moneda.tipo_moneda != tipo_pago:
                error_msg = 'La moneda seleccionada no coincide con el tipo de pago'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_msg})
                messages.error(request, error_msg)
                return redirect(request.path)

            # Validar permisos de moneda según el usuario objetivo
            if (usuario_objetivo and not usuario_objetivo.is_superuser and hasattr(usuario_objetivo, 'perfil')):
                if tipo_moneda not in usuario_objetivo.perfil.get_monedas_disponibles().filter(activa=True):
                    error_msg = 'El usuario seleccionado no tiene permiso para usar esa moneda'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': error_msg})
                    messages.error(request, error_msg)
                    return redirect(request.path)

            # Calcular diferencia de monto en USD para mensaje informativo
            monto_original_usd = Decimal('0')
            try:
                monto_original_usd = Decimal(str(pago.calcular_monto_en_usd(usuario=usuario_original)))
            except Exception:
                monto_original_usd = Decimal('0')

            # Calcular nuevo monto en USD con valores del usuario objetivo
            if tipo_moneda.codigo == 'USD':
                monto_nuevo_usd = cantidad
            else:
                valor_para_usuario = tipo_moneda.get_valor_para_usuario(usuario_objetivo)
                monto_nuevo_usd = cantidad / Decimal(str(valor_para_usuario)) if valor_para_usuario else Decimal('0')
            
            # Calcular diferencia para mensaje informativo
            diferencia_usd = monto_nuevo_usd - monto_original_usd
            
            # Actualizar el pago
            pago.destinatario = destinatario
            pago.cantidad = cantidad
            pago.tipo_moneda = tipo_moneda
            pago.tipo_pago = tipo_pago
            pago.usuario = usuario_objetivo
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
            
            # Sincronizar balances para el usuario original y el usuario objetivo
            if usuario_original != usuario_objetivo:
                _actualizar_balance_si_existe(usuario_original)
            _actualizar_balance_si_existe(usuario_objetivo)

            # Calcular balance final real del usuario objetivo
            try:
                balance_final = usuario_objetivo.perfil.calcular_balance_real() if hasattr(usuario_objetivo, 'perfil') else Decimal('0')
            except Exception:
                balance_final = Decimal('0')
            if diferencia_usd > 0:
                if balance_final < 0:
                    success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se descontaron ${diferencia_usd:.2f} USD adicionales. Balance actual: ${balance_final:.2f} USD (negativo).'
                else:
                    success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se descontaron ${diferencia_usd:.2f} USD adicionales. Balance actual: ${balance_final:.2f} USD.'
            elif diferencia_usd < 0:
                success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Se reembolsaron ${abs(diferencia_usd):.2f} USD. Balance actual: ${balance_final:.2f} USD.'
            else:
                success_msg = f'Pago actualizado exitosamente con nuevos valores USD. Balance actual: ${balance_final:.2f} USD.'
            
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
        'title': f'Editar Pago {pago.pago_id}',
        'is_admin_user': _puede_reasignar(request.user),
        'user_tipo': user_tipo,
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
                    logger.exception("Error enviando notificación WhatsApp de cambio de estado (confirmar pago)")
                
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
                    logger.exception("Error enviando notificación WhatsApp de cambio de estado (cancelar pago)")
                
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


@login_required
@require_POST
def reactivar_pago(request, pago_id):
    """Reactivar un pago cancelado por tiempo creando un NUEVO pago pendiente."""
    pago = get_object_or_404(models.Pago, id=pago_id)

    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    if user_tipo not in ['admin', 'contable']:
        return JsonResponse({'success': False, 'message': 'No tienes permisos para reactivar pagos.'}, status=403)

    if pago.estado != 'cancelado' or not getattr(pago, 'cancelado_por_tiempo', False):
        return JsonResponse({'success': False, 'message': 'Este pago no fue cancelado por tiempo o no está cancelado.'})

    with transaction.atomic():
        pago_locked = models.Pago.objects.select_for_update().get(pk=pago.pk)
        if pago_locked.estado != 'cancelado' or not getattr(pago_locked, 'cancelado_por_tiempo', False):
            return JsonResponse({'success': False, 'message': 'El pago ya no está disponible para reactivar.'})

        nuevo = models.Pago(
            tipo_pago=pago_locked.tipo_pago,
            tipo_moneda=pago_locked.tipo_moneda,
            cantidad=pago_locked.cantidad,
            destinatario=pago_locked.destinatario,
            telefono=pago_locked.telefono,
            direccion=pago_locked.direccion,
            carnet_identidad=pago_locked.carnet_identidad,
            usuario=pago_locked.usuario,
            estado='pendiente',
            tarjeta=pago_locked.tarjeta,
            comprobante_pago=pago_locked.comprobante_pago,
            observaciones=pago_locked.observaciones,
            notificado_pendiente_23h_en=None,
            cancelado_por_tiempo=False,
            cancelado_por_tiempo_en=None,
            reactivado_desde=pago_locked,
        )
        nuevo.save()

    return JsonResponse({
        'success': True,
        'message': f'Pago reactivado. Se creó un nuevo pago {nuevo.pago_id}.',
        'redirect_url': reverse('remesas:detalle_pago', args=[nuevo.id]),
        'new_id': nuevo.id,
    })


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
            
            return JsonResponse({
                'success': True, 
                'message': f'Tipo de valor "{nombre}" creado exitosamente'
            })
            
        except Exception as e:
            logger.exception("Error en crear_tipo_valor")
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
        logger.info(
            "Valor %s - Usuario: %s, Moneda: %s, Tipo: %s, Valor: %s",
            action,
            request.user.username,
            moneda.codigo,
            tipo_valor.nombre,
            str(nuevo_valor),
        )
        
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


@login_required
@require_POST
def crear_pago_remesa(request, remesa_id):
    """
    Vista para crear un pago enlazado a una remesa
    """
    try:
        remesa = get_object_or_404(models.Remesa, id=remesa_id)

        from django.contrib.auth.models import User

        def _es_admin(usuario: User) -> bool:
            if not usuario or not usuario.is_authenticated:
                return False
            if usuario.is_superuser:
                return True
            return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

        def _resolver_usuario_objetivo_post() -> User:
            """Usuario al que se asigna el pago enlazado (solo admins pueden elegir)."""
            if not _es_admin(request.user):
                return request.user

            usuario_id = (request.POST.get('usuario_asignado') or request.POST.get('usuario_id') or '').strip()
            if not usuario_id:
                return request.user

            try:
                return User.objects.get(id=int(usuario_id), is_active=True)
            except (User.DoesNotExist, ValueError, TypeError):
                return request.user
        
        # Verificar que el usuario tenga permisos (admin, contable o el gestor de la remesa)
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if user_tipo not in ['admin', 'contable'] and remesa.gestor != request.user:
            return JsonResponse({
                'success': False, 
                'message': 'No tiene permisos para agregar pagos a esta remesa'
            })

        usuario_objetivo = _resolver_usuario_objetivo_post()
        
        # Crear el formulario con los datos POST y FILES (monedas filtradas por usuario)
        form = PagoRemesaForm(request.POST, request.FILES, user=usuario_objetivo)
        
        if form.is_valid():
            # Crear el pago pero no guardarlo todavía
            pago = form.save(commit=False)
            pago.remesa = remesa
            pago.usuario = usuario_objetivo
            pago.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Pago {pago.pago_id} creado y enlazado a la remesa exitosamente',
                'pago_id': pago.pago_id,
                'pago_pk': pago.pk
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            
            return JsonResponse({
                'success': False,
                'message': 'Error en los datos del formulario',
                'errors': errors
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al crear el pago: {str(e)}'
        })


@login_required
def editar_pago_remesa(request, pago_id):
    """
    Vista para editar un pago de remesa
    """
    pago = get_object_or_404(PagoRemesa, id=pago_id)
    remesa = pago.remesa
    
    # Verificar permisos
    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    
    if user_tipo not in ['admin', 'contable'] and remesa.gestor != request.user:
        messages.error(request, 'No tiene permisos para editar este pago')
        return redirect('remesas:detalle_remesa', remesa_id=remesa.id)
    
    # Solo permitir editar pagos pendientes
    if pago.estado != 'pendiente':
        messages.error(request, f'No se puede editar el pago porque está en estado: {pago.get_estado_display()}')
        return redirect('remesas:detalle_remesa', remesa_id=remesa.id)
    
    if request.method == 'POST':
        # Solo admins pueden reasignar "a nombre de"
        def _puede_reasignar(usuario) -> bool:
            if not usuario or not usuario.is_authenticated:
                return False
            if usuario.is_superuser:
                return True
            return bool(getattr(getattr(usuario, 'perfil', None), 'tipo_usuario', None) == 'admin')

        def _actualizar_balance_si_existe(usuario):
            try:
                if usuario and hasattr(usuario, 'perfil'):
                    usuario.perfil.actualizar_balance()
            except Exception:
                pass

        usuario_original = pago.usuario
        usuario_objetivo = pago.usuario
        if _puede_reasignar(request.user):
            from django.contrib.auth.models import User
            usuario_id = (request.POST.get('usuario_asignado') or '').strip()
            if usuario_id:
                try:
                    usuario_objetivo = User.objects.get(id=int(usuario_id), is_active=True)
                except (User.DoesNotExist, ValueError, TypeError):
                    usuario_objetivo = pago.usuario

        form = PagoRemesaForm(request.POST, request.FILES, instance=pago, user=usuario_objetivo)
        
        if form.is_valid():
            # Marcar como editado
            pago_editado = form.save(commit=False)
            pago_editado.editado = True
            pago_editado.fecha_edicion = timezone.now()
            pago_editado.usuario_editor = request.user
            pago_editado.usuario = usuario_objetivo
            pago_editado.save()

            # Recalcular valores USD con las tasas actuales después de la edición
            pago_editado.recalcular_valores_por_edicion()

            # Sincronizar balances por si cambia de usuario o estaba confirmado
            if usuario_original != usuario_objetivo:
                _actualizar_balance_si_existe(usuario_original)
            _actualizar_balance_si_existe(usuario_objetivo)
            
            messages.success(request, f'Pago {pago.pago_id} editado exitosamente')
            return redirect('remesas:detalle_remesa', remesa_id=remesa.id)
    else:
        # Mostrar monedas según el usuario dueño del pago (o el usuario actual si no hay dueño)
        form_usuario = pago.usuario or request.user
        form = PagoRemesaForm(instance=pago, user=form_usuario)
    
    context = {
        'form': form,
        'pago': pago,
        'remesa': remesa,
        'title': f'Editar Pago {pago.pago_id}',
        'user_tipo': user_tipo,
        'is_admin_user': (request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.tipo_usuario == 'admin')),
    }
    
    return render(request, 'remesas/editar_pago_remesa.html', context)


@login_required
def listar_pagos_remesa(request, remesa_id):
    """
    Vista para listar los pagos enlazados a una remesa
    """
    try:
        remesa = get_object_or_404(models.Remesa, id=remesa_id)
        pagos = remesa.pagos_enlazados.all().order_by('-fecha_creacion')
        
        pagos_data = []
        for pago in pagos:
            pagos_data.append({
                'id': pago.pk,
                'pago_id': pago.pago_id,
                'destinatario': pago.destinatario,
                'cantidad': str(pago.cantidad),
                'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'N/A',
                'tipo_pago': pago.get_tipo_pago_display(),
                'estado': pago.get_estado_display(),
                'estado_badge': pago.get_estado_badge(),
                'fecha_creacion': pago.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'comprobante_url': pago.comprobante_pago.url if pago.comprobante_pago else None
            })
        
        return JsonResponse({
            'success': True,
            'pagos': pagos_data,
            'total_pagos': len(pagos_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener los pagos: {str(e)}'
        })


@login_required
@require_POST
def eliminar_pago_remesa(request, pago_id):
    """
    Vista para eliminar un pago de remesa
    """
    try:
        pago = get_object_or_404(PagoRemesa, id=pago_id)
        
        # Verificar permisos
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if user_tipo not in ['admin', 'contable'] and pago.remesa.gestor != request.user:
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para eliminar este pago'
            })
        
        # Solo permitir eliminar pagos pendientes
        if pago.estado != 'pendiente':
            return JsonResponse({
                'success': False,
                'message': f'No se puede eliminar el pago porque está en estado: {pago.get_estado_display()}'
            })
        
        pago_id_str = pago.pago_id
        pago.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago {pago_id_str} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al eliminar el pago: {str(e)}'
        })


@login_required
@login_required
def confirmar_pago_remesa(request, pago_id):
    """
    Vista para confirmar un pago de remesa (cuando la remesa ya está completada)
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        })
    
    try:
        pago = get_object_or_404(PagoRemesa, id=pago_id)
        
        # Verificar permisos
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if user_tipo not in ['admin', 'contable']:
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para confirmar pagos'
            })
        
        # Verificar que la remesa esté completada
        if pago.remesa.estado != 'completada':
            return JsonResponse({
                'success': False,
                'message': 'La remesa debe estar completada para confirmar sus pagos manualmente'
            })
        
        # Verificar que el pago esté pendiente
        if pago.estado != 'pendiente':
            return JsonResponse({
                'success': False,
                'message': f'El pago ya está en estado: {pago.get_estado_display()}'
            })
        
        # Obtener el usuario del pago (el que lo creó)
        usuario_pago = pago.usuario
        if not usuario_pago:
            return JsonResponse({
                'success': False,
                'message': 'El pago no tiene un usuario asignado'
            })
        
        # Calcular el monto en USD
        if pago.monto_usd_historico:
            monto_usd = pago.monto_usd_historico
        else:
            # Calcular si no está guardado
            if pago.tipo_moneda and pago.tipo_moneda.codigo == 'USD':
                monto_usd = pago.cantidad
            elif pago.tipo_moneda:
                valor_moneda = pago.tipo_moneda.get_valor_para_usuario(usuario_pago)
                if valor_moneda > 0:
                    monto_usd = pago.cantidad / Decimal(str(valor_moneda))
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'No se pudo calcular el valor en USD'
                    })
            else:
                monto_usd = pago.cantidad
        
        # Verificar que el usuario tenga perfil
        if not hasattr(usuario_pago, 'perfil'):
            return JsonResponse({
                'success': False,
                'message': 'El usuario no tiene un perfil configurado'
            })
        
        # Balance dinámico: confirmar el pago y recalcular balance real.
        balance_anterior = usuario_pago.perfil.calcular_balance_real()

        # Cambiar estado del pago
        pago.estado = 'confirmado'
        pago.save()

        # Sincronizar balance almacenado con el balance real (incluye PagoRemesa confirmado)
        balance_final = usuario_pago.perfil.actualizar_balance()
        try:
            from remesas.context_processors import invalidate_user_balance_cache
            invalidate_user_balance_cache(usuario_pago.id)
        except Exception:
            pass
        
        mensaje = (
            f"Pago {pago.pago_id} confirmado exitosamente. "
            f"Se descontaron ${monto_usd:.2f} USD. Balance actual: ${balance_final:.2f} USD"
        )
        
        return JsonResponse({
            'success': True,
            'message': mensaje
        })
        
    except Exception as e:
        logger.exception("Error al confirmar pago remesa")
        return JsonResponse({
            'success': False,
            'message': f'Error al confirmar el pago: {str(e)}'
        })


@login_required
def cancelar_pago_remesa(request, pago_id):
    """
    Vista para cancelar un pago de remesa
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        })
    
    try:
        pago = get_object_or_404(PagoRemesa, id=pago_id)
        
        # Verificar permisos
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if user_tipo not in ['admin', 'contable']:
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para cancelar pagos'
            })
        
        # Verificar que la remesa esté completada
        if pago.remesa.estado != 'completada':
            return JsonResponse({
                'success': False,
                'message': 'La remesa debe estar completada para gestionar sus pagos manualmente'
            })
        
        # Verificar que el pago esté pendiente
        if pago.estado != 'pendiente':
            return JsonResponse({
                'success': False,
                'message': f'El pago ya está en estado: {pago.get_estado_display()}'
            })
        
        pago_id_str = pago.pago_id
        
        # Cambiar estado del pago
        pago.estado = 'cancelado'
        pago.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago {pago_id_str} cancelado exitosamente'
        })
        
    except Exception as e:
        logger.exception("Error al cancelar pago remesa")
        return JsonResponse({
            'success': False,
            'message': f'Error al cancelar el pago: {str(e)}'
        })


@login_required
@require_POST
def reactivar_pago_remesa(request, pago_id):
    """Reactivar un pago de remesa cancelado por tiempo creando un NUEVO pago de remesa pendiente."""
    pago = get_object_or_404(PagoRemesa, id=pago_id)

    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    if user_tipo not in ['admin', 'contable']:
        return JsonResponse({'success': False, 'message': 'No tienes permisos para reactivar pagos de remesa.'}, status=403)

    if pago.estado != 'cancelado' or not getattr(pago, 'cancelado_por_tiempo', False):
        return JsonResponse({'success': False, 'message': 'Este pago no fue cancelado por tiempo o no está cancelado.'})

    with transaction.atomic():
        pago_locked = PagoRemesa.objects.select_for_update().select_related('remesa').get(pk=pago.pk)
        if pago_locked.estado != 'cancelado' or not getattr(pago_locked, 'cancelado_por_tiempo', False):
            return JsonResponse({'success': False, 'message': 'El pago ya no está disponible para reactivar.'})

        nuevo = PagoRemesa(
            remesa=pago_locked.remesa,
            tipo_pago=pago_locked.tipo_pago,
            tipo_moneda=pago_locked.tipo_moneda,
            cantidad=pago_locked.cantidad,
            destinatario=pago_locked.destinatario,
            telefono=pago_locked.telefono,
            direccion=pago_locked.direccion,
            carnet_identidad=pago_locked.carnet_identidad,
            usuario=pago_locked.usuario,
            estado='pendiente',
            tarjeta=pago_locked.tarjeta,
            comprobante_pago=pago_locked.comprobante_pago,
            observaciones=pago_locked.observaciones,
            notificado_pendiente_23h_en=None,
            cancelado_por_tiempo=False,
            cancelado_por_tiempo_en=None,
            reactivado_desde=pago_locked,
        )
        nuevo.save()

        # Por defecto, volver al detalle de la remesa.
        redirect_url = (
            reverse('remesas:detalle_remesa', args=[pago_locked.remesa.id])
            if pago_locked.remesa
            else reverse('remesas:registro_transacciones')
        )

    return JsonResponse({
        'success': True,
        'message': f'Pago reactivado. Se creó un nuevo pago {nuevo.pago_id}.',
        'redirect_url': redirect_url,
        'new_id': nuevo.id,
    })


@login_required
@require_POST
def actualizar_fondo_caja(request):
    """
    Vista para actualizar el fondo de caja de una moneda (AJAX)
    Solo accesible para administradores
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Sin permisos para realizar esta acción'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        
        moneda_id = data.get('moneda_id')
        nuevo_fondo = data.get('fondo')
        
        if not all([moneda_id, nuevo_fondo is not None]):
            return JsonResponse({'success': False, 'message': 'Datos incompletos'})
        
        # Validar que el fondo sea un número válido
        try:
            nuevo_fondo = Decimal(str(nuevo_fondo))
            if nuevo_fondo < 0:
                return JsonResponse({'success': False, 'message': 'El fondo no puede ser negativo'})
        except (ValueError, decimal.InvalidOperation):
            return JsonResponse({'success': False, 'message': 'Valor numérico inválido'})
        
        # Obtener la moneda
        try:
            moneda = models.Moneda.objects.get(id=moneda_id)
        except models.Moneda.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Moneda no encontrada'})
        
        # Actualizar el fondo de caja
        moneda.fondo_caja = nuevo_fondo
        moneda.save()
        
        # Log de la operación para auditoria
        logger.info(
            "Fondo de caja actualizado - Usuario: %s, Moneda: %s, Nuevo Fondo: %s",
            request.user.username,
            moneda.codigo,
            str(nuevo_fondo),
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Fondo de caja actualizado exitosamente para {moneda.codigo}',
            'nuevo_fondo': float(nuevo_fondo)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'})


@login_required
@require_POST
def actualizar_alerta_minima(request):
    """
    Vista para actualizar la alerta de fondo mínimo de una moneda (AJAX)
    Solo accesible para administradores
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Sin permisos para realizar esta acción'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        
        moneda_id = data.get('moneda_id')
        alerta_minima = data.get('alerta_minima')
        
        if not all([moneda_id, alerta_minima is not None]):
            return JsonResponse({'success': False, 'message': 'Datos incompletos'})
        
        # Validar que la alerta sea un número válido
        try:
            alerta_minima = Decimal(str(alerta_minima))
            if alerta_minima < 0:
                return JsonResponse({'success': False, 'message': 'La alerta no puede ser negativa'})
        except (ValueError, decimal.InvalidOperation):
            return JsonResponse({'success': False, 'message': 'Valor numérico inválido'})
        
        # Obtener la moneda
        try:
            moneda = models.Moneda.objects.get(id=moneda_id)
        except models.Moneda.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Moneda no encontrada'})
        
        # Actualizar la alerta mínima
        moneda.alerta_fondo_minimo = alerta_minima
        moneda.save()
        
        # Log de la operación para auditoria
        logger.info(
            "Alerta mínima actualizada - Usuario: %s, Moneda: %s, Nueva Alerta: %s",
            request.user.username,
            moneda.codigo,
            str(alerta_minima),
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Alerta de fondo mínimo actualizada exitosamente para {moneda.codigo}',
            'nueva_alerta': float(alerta_minima)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'})
