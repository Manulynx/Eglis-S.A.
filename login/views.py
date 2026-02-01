from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import PerfilUsuario, SesionUsuario, HistorialAcciones
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Obtener la IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def registrar_accion(usuario, accion, descripcion, request):
    """Registrar una acción en el historial"""
    HistorialAcciones.objects.create(
        usuario=usuario,
        accion=accion,
        descripcion=descripcion,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

def login_view(request):
    """Vista para el login de usuarios"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Crear o actualizar sesión
                    sesion, created = SesionUsuario.objects.get_or_create(
                        usuario=user,
                        defaults={
                            'session_key': request.session.session_key,
                            'ip_address': get_client_ip(request),
                            'user_agent': request.META.get('HTTP_USER_AGENT', '')
                        }
                    )
                    if not created:
                        sesion.session_key = request.session.session_key
                        sesion.ip_address = get_client_ip(request)
                        sesion.user_agent = request.META.get('HTTP_USER_AGENT', '')
                        sesion.save()
                    
                    # Registrar acción
                    registrar_accion(user, 'login', f'Inicio de sesión exitoso', request)
                    
                    # Mensaje de bienvenida personalizado
                    nombre_completo = f"{user.first_name} {user.last_name}".strip()
                    nombre_mostrar = nombre_completo if nombre_completo else user.username
                    messages.success(request, f'Sesión iniciada correctamente. ¡Bienvenido {nombre_mostrar}!')
                    return redirect('home')
                else:
                    messages.error(request, 'Su cuenta ha sido desactivada. Contacte al administrador.')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos. Verifique sus credenciales.')
        else:
            messages.error(request, 'Debe completar todos los campos para iniciar sesión.')
    
    return render(request, 'login/login.html')

@login_required
def logout_view(request):
    """Vista para cerrar sesión"""
    # Obtener nombre del usuario antes de cerrar sesión
    nombre_completo = f"{request.user.first_name} {request.user.last_name}".strip()
    nombre_mostrar = nombre_completo if nombre_completo else request.user.username
    
    # Registrar acción antes de cerrar sesión
    registrar_accion(request.user, 'logout', 'Cierre de sesión', request)
    
    # Eliminar sesión
    try:
        sesion = SesionUsuario.objects.get(usuario=request.user)
        sesion.delete()
    except SesionUsuario.DoesNotExist:
        pass
    
    logout(request)
    messages.success(request, f'Sesión cerrada correctamente. ¡Hasta pronto {nombre_mostrar}!')
    return redirect('login:login')

def is_staff(user):
    """Verificar si el usuario es staff"""
    return user.is_authenticated and user.is_staff

def administrar_usuarios(request):
    """Vista para administrar usuarios"""
    # Obtener parámetros de filtro
    search_query = request.GET.get('search', '')
    estado_filter = request.GET.get('estado', '')
    tipo_usuario_filter = request.GET.get('tipo_usuario', '')
    balance_filter = request.GET.get('balance', '')
    filtro_fecha = request.GET.get('filtro_fecha', 'hoy')

    # Rango de fechas basado en actividad (remesas/pagos), igual que Registro
    from datetime import timedelta
    from django.conf import settings
    from zoneinfo import ZoneInfo

    tz_local = ZoneInfo(settings.TIME_ZONE)
    today = timezone.now().astimezone(tz_local).date()

    fecha_desde_obj = None
    fecha_hasta_obj = None
    if filtro_fecha != 'todas':
        if filtro_fecha == 'hoy':
            fecha_desde_obj = today
            fecha_hasta_obj = today
        elif filtro_fecha == 'ayer':
            fecha_desde_obj = today - timedelta(days=1)
            fecha_hasta_obj = fecha_desde_obj
        elif filtro_fecha == 'semana':
            fecha_desde_obj = today - timedelta(weeks=1)
            fecha_hasta_obj = today
        elif filtro_fecha == 'mes':
            fecha_desde_obj = today - timedelta(days=30)
            fecha_hasta_obj = today
        else:
            # Si llega un valor inválido, por seguridad tratamos como 'hoy'
            filtro_fecha = 'hoy'
            fecha_desde_obj = today
            fecha_hasta_obj = today
    
    # Obtener usuarios (excluir usuario programador)
    usuarios = User.objects.select_related('perfil').exclude(username='cdtwilight')
    
    # Aplicar filtro de búsqueda
    if search_query:
        usuarios = usuarios.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Aplicar filtro de estado
    if estado_filter:
        if estado_filter == 'activo':
            usuarios = usuarios.filter(is_active=True)
        elif estado_filter == 'inactivo':
            usuarios = usuarios.filter(is_active=False)
    
    # Aplicar filtro de tipo de usuario
    if tipo_usuario_filter:
        if tipo_usuario_filter == 'admin':
            usuarios = usuarios.filter(is_superuser=True)
        elif tipo_usuario_filter == 'gestor':
            usuarios = usuarios.filter(is_superuser=False, perfil__tipo_usuario='gestor')
        elif tipo_usuario_filter == 'contable':
            usuarios = usuarios.filter(perfil__tipo_usuario='contable')
    
    # Importar modelos necesarios
    from remesas.models import Remesa, Pago, PagoRemesa
    from decimal import Decimal
    
    # Agregar estadísticas de remesas y pagos a cada usuario
    usuarios_con_datos = []
    suma_todos_balances = Decimal('0.00')
    total_remesas_count = 0
    total_pagos_count = 0
    
    for usuario in usuarios:
        # Querysets base (all-time) de actividad del usuario
        remesas_usuario_all = Remesa.objects.filter(
            gestor=usuario,
            estado__in=['confirmada', 'completada']
        ).select_related('moneda')

        pagos_usuario_all = Pago.objects.filter(
            usuario=usuario,
            estado='confirmado'
        ).select_related('tipo_moneda')

        pagos_remesa_usuario_all = PagoRemesa.objects.filter(
            usuario=usuario,
            estado='confirmado'
        ).select_related('tipo_moneda')

        # Querysets para mostrar (filtrados por periodo si aplica)
        remesas_usuario = remesas_usuario_all
        pagos_usuario = pagos_usuario_all
        pagos_remesa_usuario = pagos_remesa_usuario_all

        if fecha_desde_obj and fecha_hasta_obj:
            remesas_usuario = remesas_usuario.filter(
                fecha__date__gte=fecha_desde_obj,
                fecha__date__lte=fecha_hasta_obj
            )
            pagos_usuario = pagos_usuario.filter(
                fecha_creacion__date__gte=fecha_desde_obj,
                fecha_creacion__date__lte=fecha_hasta_obj
            )
            pagos_remesa_usuario = pagos_remesa_usuario.filter(
                fecha_creacion__date__gte=fecha_desde_obj,
                fecha_creacion__date__lte=fecha_hasta_obj
            )

        # Contadores
        remesas_count = remesas_usuario.count()
        pagos_count = pagos_usuario.count() + pagos_remesa_usuario.count()
        total_remesas_count += remesas_count
        total_pagos_count += pagos_count

        # Totales USD (periodo o all-time según filtro)
        total_remesas_usd = Decimal('0.00')
        
        for remesa in remesas_usuario:
            try:
                # Usar el método que prioriza valores históricos guardados
                monto_usd = remesa.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_remesas_usd += Decimal(str(monto_usd))
            except Exception as e:
                logger.exception("Error calculando monto USD para remesa %s", getattr(remesa, 'remesa_id', 'N/A'))
                continue
        
        total_pagos_usd = Decimal('0.00')
        for pago in pagos_usuario:
            try:
                # Usar el método que prioriza valores históricos guardados
                monto_usd = pago.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_pagos_usd += Decimal(str(monto_usd))
            except Exception as e:
                logger.exception("Error calculando monto USD para pago %s", getattr(pago, 'pago_id', 'N/A'))
                continue

        for pago in pagos_remesa_usuario:
            try:
                monto_usd = pago.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_pagos_usd += Decimal(str(monto_usd))
            except Exception as e:
                logger.exception("Error calculando monto USD para pago remesa %s", getattr(pago, 'pago_id', 'N/A'))
                continue

        # Balance unificado: siempre RemesasUSD - PagosUSD (para el periodo seleccionado)
        balance = total_remesas_usd - total_pagos_usd

        # Mantener perfil.balance sincronizado solo cuando se está viendo 'todas'
        if filtro_fecha == 'todas':
            try:
                balance_all_time = balance
                if usuario.perfil.balance != balance_all_time:
                    usuario.perfil.balance = balance_all_time
                    usuario.perfil.save()
            except Exception:
                pass

        suma_todos_balances += balance
        
        # Agregar datos calculados al usuario
        usuario.balance_display = balance  # Para mostrar en la template
        usuario.remesas_count = remesas_count
        usuario.pagos_count = pagos_count
        usuario.total_remesas_usd = total_remesas_usd
        usuario.total_pagos_usd = total_pagos_usd
        
        # Mostrar siempre todos los usuarios (los que no tengan actividad en el periodo quedan en 0)
        usuarios_con_datos.append(usuario)
    
    # Aplicar filtro de balance (después de calcular los balances)
    if balance_filter:
        usuarios_filtrados = []
        for usuario in usuarios_con_datos:
            if balance_filter == 'positivo' and usuario.balance_display > 0:
                usuarios_filtrados.append(usuario)
            elif balance_filter == 'negativo' and usuario.balance_display < 0:
                usuarios_filtrados.append(usuario)
            elif balance_filter == 'cero' and usuario.balance_display == 0:
                usuarios_filtrados.append(usuario)
        usuarios_con_datos = usuarios_filtrados
    
    # Ordenar usuarios: primero los que tienen actividad (remesas o pagos), luego los sin actividad
    # Dentro de cada grupo, ordenar por balance de mayor a menor
    usuarios_con_datos.sort(key=lambda usuario: (
        # Primer criterio: usuarios con actividad primero (True viene antes que False cuando se invierte)
        -(usuario.remesas_count + usuario.pagos_count > 0),
        # Segundo criterio: balance de mayor a menor (invertido)
        -usuario.balance_display
    ))
    
    # Paginación
    paginator = Paginator(usuarios_con_datos, 10)
    page_number = request.GET.get('page')
    usuarios_page = paginator.get_page(page_number)

    # Querystring para paginación (preservar filtros)
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    querystring = query_params.urlencode()
    
    # Estadísticas generales
    total_usuarios = User.objects.count()
    usuarios_activos = User.objects.filter(is_active=True).count()
    usuarios_staff = User.objects.filter(is_staff=True).count()
    
    # Usuarios conectados en las últimas 24 horas
    hace_24h = timezone.now() - timezone.timedelta(hours=24)
    usuarios_activos_hoy = SesionUsuario.objects.filter(
        ultima_actividad__gte=hace_24h
    ).count()

    # Obtener tipos de valores de moneda para los formularios
    from remesas.models import TipoValorMoneda, Moneda
    tipos_valor_moneda = TipoValorMoneda.objects.filter(activo=True).order_by('orden', 'nombre')
    
    # Obtener todas las monedas activas para asignación
    monedas_disponibles = Moneda.objects.filter(activa=True).order_by('nombre')
    
    context = {
        'usuarios': usuarios_page,
        'search_query': search_query,
        'estado_filter': estado_filter,
        'tipo_usuario_filter': tipo_usuario_filter,
        'balance_filter': balance_filter,
        'filtro_fecha': filtro_fecha,
        'querystring': querystring,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'usuarios_staff': usuarios_staff,
        'usuarios_activos_hoy': usuarios_activos_hoy,
        'total_remesas': total_remesas_count,  # Total de remesas gestionadas
        'total_pagos': total_pagos_count,      # Total de pagos realizados
        'suma_todos_balances': suma_todos_balances,  # Suma de todos los balances
        'tipos_valor_moneda': tipos_valor_moneda,  # Para los formularios
        'monedas_disponibles': monedas_disponibles,  # Para asignación de monedas
    }
    
    return render(request, 'autenticacion/administrar_usuarios.html', context)

def crear_usuario(request):
    """Vista para crear un nuevo usuario"""
    if request.method == 'POST':
        # Verificar si es AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            # Obtener datos del formulario
            username = request.POST.get('username')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            tipo_usuario = request.POST.get('tipo_usuario', 'gestor')
            telefono = request.POST.get('telefono', '').strip()
            tipo_valor_moneda_id = request.POST.get('tipo_valor_moneda', '')
            monedas_asignadas = request.POST.getlist('monedas_asignadas')  # Lista de IDs de monedas
            
            # Validar campos requeridos
            if not username or not password1:
                raise ValueError('Username y contraseña son requeridos')
            
            if password1 != password2:
                raise ValueError('Las contraseñas no coinciden')
            
            # Determinar permisos basándose en el tipo de usuario
            is_staff = tipo_usuario in ['admin']
            is_superuser = tipo_usuario in ['admin']
            
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email='',  # Email vacío por defecto
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_staff,
                is_superuser=is_superuser
            )
            
            # Asignar tipo de usuario, teléfono y tipo de valor de moneda al perfil
            perfil = user.perfil
            perfil.tipo_usuario = tipo_usuario
            
            # Asignar teléfono si se proporcionó
            if telefono:
                perfil.telefono = telefono
            
            # Asignar tipo de valor de moneda
            if tipo_valor_moneda_id:
                from remesas.models import TipoValorMoneda
                try:
                    tipo_valor = TipoValorMoneda.objects.get(id=tipo_valor_moneda_id, activo=True)
                    perfil.tipo_valor_moneda = tipo_valor
                except TipoValorMoneda.DoesNotExist:
                    pass  # Mantener el valor por defecto
            
            perfil.save()
            
            # Asignar monedas si se proporcionaron (solo para gestor y domicilio)
            if monedas_asignadas and tipo_usuario in ['gestor', 'domicilio']:
                from remesas.models import Moneda
                try:
                    monedas_objetos = Moneda.objects.filter(id__in=monedas_asignadas, activa=True)
                    perfil.monedas_asignadas.set(monedas_objetos)
                except Exception as e:
                    logger.exception("Error asignando monedas al usuario %s", username)
            
            # Registrar acción si hay usuario autenticado
            if request.user.is_authenticated:
                registrar_accion(
                    request.user, 'create', 
                    f'Usuario creado: {username} (tipo: {tipo_usuario})', 
                    request
                )
            
            # SIEMPRE devolver JSON para AJAX
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Usuario {username} creado exitosamente.'
                })

            messages.success(request, f'Usuario {username} creado exitosamente.')
            return redirect('login:administrar_usuarios')
            
        except Exception as e:
            # Manejo de errores
            logger.exception("Error creando usuario")
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error al crear usuario: {str(e)}'
                })
            messages.error(request, f'Error al crear usuario: {str(e)}')
            return redirect('login:administrar_usuarios')
    
    # Para peticiones no POST o errores
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'message': 'Solicitud no válida.'
        })

    return redirect('login:administrar_usuarios')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def obtener_usuario(request, user_id):
    """Vista para obtener datos de un usuario (AJAX)"""
    try:
        usuario = get_object_or_404(User, id=user_id)
        
        # Obtener el tipo de usuario y teléfono
        if usuario.is_superuser:
            tipo_usuario = 'admin'
            tipo_usuario_display = 'Administrador'
            # Los admins también pueden tener perfil ahora
            try:
                perfil = usuario.perfil
                telefono = perfil.telefono if perfil.telefono else ''
                tipo_valor_moneda_id = perfil.tipo_valor_moneda.id if perfil.tipo_valor_moneda else None
                tipo_valor_moneda_nombre = perfil.tipo_valor_moneda.nombre if perfil.tipo_valor_moneda else ''
                # Obtener monedas asignadas
                monedas_asignadas = list(perfil.monedas_asignadas.values_list('id', flat=True))
                monedas_asignadas_display = ', '.join(
                    perfil.monedas_asignadas.values_list('codigo', flat=True)
                ) if perfil.monedas_asignadas.exists() else 'Todas las monedas'
            except:
                telefono = ''
                tipo_valor_moneda_id = None
                tipo_valor_moneda_nombre = ''
                monedas_asignadas = []
                monedas_asignadas_display = 'Todas las monedas'
        else:
            try:
                perfil = usuario.perfil
                tipo_usuario = perfil.tipo_usuario
                telefono = perfil.telefono if perfil.telefono else ''
                tipo_valor_moneda_id = perfil.tipo_valor_moneda.id if perfil.tipo_valor_moneda else None
                tipo_valor_moneda_nombre = perfil.tipo_valor_moneda.nombre if perfil.tipo_valor_moneda else ''
                # Usar el display definido en las opciones del modelo
                tipo_usuario_display = dict(perfil.TIPO_USUARIO_CHOICES).get(tipo_usuario, 'Gestor')
                
                # Obtener monedas asignadas
                monedas_asignadas = list(perfil.monedas_asignadas.values_list('id', flat=True))
                monedas_asignadas_display = ', '.join(
                    perfil.monedas_asignadas.values_list('codigo', flat=True)
                ) if perfil.monedas_asignadas.exists() else 'Todas las monedas'
            except:
                tipo_usuario = 'gestor'
                tipo_usuario_display = 'Gestor'
                telefono = ''
                tipo_valor_moneda_id = None
                tipo_valor_moneda_nombre = ''
                monedas_asignadas = []
                monedas_asignadas_display = 'Todas las monedas'
        
        return JsonResponse({
            'status': 'success',
            'usuario': {
                'id': usuario.id,
                'username': usuario.username,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'email': usuario.email,
                'telefono': telefono,
                'is_superuser': usuario.is_superuser,
                'tipo_usuario': tipo_usuario,
                'tipo_usuario_display': tipo_usuario_display,
                'tipo_valor_moneda_id': tipo_valor_moneda_id,
                'tipo_valor_moneda_nombre': tipo_valor_moneda_nombre,
                'monedas_asignadas': monedas_asignadas,
                'monedas_asignadas_display': monedas_asignadas_display,
                'is_active': usuario.is_active,
                'date_joined': usuario.date_joined.strftime('%Y-%m-%d'),
                'last_login': usuario.last_login.strftime('%Y-%m-%d %H:%M') if usuario.last_login else 'Nunca'
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al obtener datos del usuario: {str(e)}'
        })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def editar_usuario(request, user_id):
    """Vista para editar un usuario"""
    usuario = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Verificar si es una petición AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            # Obtener datos del formulario - solo actualizar si no están vacíos
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            password = request.POST.get('password', '').strip()
            tipo_usuario = request.POST.get('tipo_usuario', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            tipo_valor_moneda_id = request.POST.get('tipo_valor_moneda', '').strip()
            monedas_asignadas = request.POST.getlist('monedas_asignadas')  # Lista de IDs de monedas
            
            # Actualizar campos del usuario solo si se proporcionaron valores
            if username:
                # Verificar que el username no esté en uso por otro usuario
                if User.objects.filter(username=username).exclude(id=usuario.id).exists():
                    raise ValueError(f'El nombre de usuario "{username}" ya está en uso')
                usuario.username = username
            
            if email:
                usuario.email = email
            
            if first_name:
                usuario.first_name = first_name
            
            if last_name:
                usuario.last_name = last_name
            
            # Solo actualizar la contraseña si se proporcionó una nueva
            if password:
                usuario.set_password(password)
            
            # Manejar tipo de usuario
            if tipo_usuario:
                if tipo_usuario == 'admin':
                    usuario.is_superuser = True
                    usuario.is_staff = True
                    # Crear o actualizar perfil para admin también
                    try:
                        perfil = usuario.perfil
                        perfil.tipo_usuario = 'admin'
                        if telefono:
                            perfil.telefono = telefono
                        
                        # Actualizar tipo de valor de moneda si se proporcionó
                        if tipo_valor_moneda_id:
                            from remesas.models import TipoValorMoneda
                            try:
                                tipo_valor = TipoValorMoneda.objects.get(id=tipo_valor_moneda_id, activo=True)
                                perfil.tipo_valor_moneda = tipo_valor
                            except TipoValorMoneda.DoesNotExist:
                                pass  # Mantener el valor actual
                        
                        perfil.save()
                        
                        # Actualizar monedas asignadas (admin puede tenerlas o no)
                        if monedas_asignadas is not None:
                            from remesas.models import Moneda
                            monedas_objetos = Moneda.objects.filter(id__in=monedas_asignadas, activa=True)
                            perfil.monedas_asignadas.set(monedas_objetos)
                    except:
                        # Si no tiene perfil, crear uno nuevo para admin
                        tipo_valor_obj = None
                        if tipo_valor_moneda_id:
                            from remesas.models import TipoValorMoneda
                            try:
                                tipo_valor_obj = TipoValorMoneda.objects.get(id=tipo_valor_moneda_id, activo=True)
                            except TipoValorMoneda.DoesNotExist:
                                pass
                        
                        perfil = PerfilUsuario.objects.create(
                            user=usuario, 
                            tipo_usuario='admin',
                            telefono=telefono if telefono else '',
                            tipo_valor_moneda=tipo_valor_obj
                        )
                        
                        # Asignar monedas si se proporcionaron
                        if monedas_asignadas:
                            from remesas.models import Moneda
                            monedas_objetos = Moneda.objects.filter(id__in=monedas_asignadas, activa=True)
                            perfil.monedas_asignadas.set(monedas_objetos)
                else:
                    usuario.is_superuser = False
                    usuario.is_staff = False
                    
                    # Crear o actualizar perfil
                    try:
                        perfil = usuario.perfil
                        perfil.tipo_usuario = tipo_usuario
                        if telefono:
                            perfil.telefono = telefono
                        
                        # Actualizar tipo de valor de moneda si se proporcionó
                        if tipo_valor_moneda_id:
                            from remesas.models import TipoValorMoneda
                            try:
                                tipo_valor = TipoValorMoneda.objects.get(id=tipo_valor_moneda_id, activo=True)
                                perfil.tipo_valor_moneda = tipo_valor
                            except TipoValorMoneda.DoesNotExist:
                                pass  # Mantener el valor actual
                        
                        perfil.save()
                        
                        # Actualizar monedas asignadas (solo para gestor y domicilio)
                        if tipo_usuario in ['gestor', 'domicilio'] and monedas_asignadas is not None:
                            from remesas.models import Moneda
                            monedas_objetos = Moneda.objects.filter(id__in=monedas_asignadas, activa=True)
                            perfil.monedas_asignadas.set(monedas_objetos)
                    except:
                        # Si no tiene perfil, crear uno nuevo
                        tipo_valor_obj = None
                        if tipo_valor_moneda_id:
                            from remesas.models import TipoValorMoneda
                            try:
                                tipo_valor_obj = TipoValorMoneda.objects.get(id=tipo_valor_moneda_id, activo=True)
                            except TipoValorMoneda.DoesNotExist:
                                pass
                        
                        perfil = PerfilUsuario.objects.create(
                            user=usuario, 
                            tipo_usuario=tipo_usuario,
                            telefono=telefono if telefono else '',
                            tipo_valor_moneda=tipo_valor_obj
                        )
                        
                        # Asignar monedas si se proporcionaron (solo para gestor y domicilio)
                        if tipo_usuario in ['gestor', 'domicilio'] and monedas_asignadas:
                            from remesas.models import Moneda
                            monedas_objetos = Moneda.objects.filter(id__in=monedas_asignadas, activa=True)
                            perfil.monedas_asignadas.set(monedas_objetos)
            
            # Validar y guardar usuario
            usuario.full_clean()
            usuario.save()
            
            # Registrar acción si hay usuario autenticado
            if request.user.is_authenticated:
                registrar_accion(
                    request.user, 'update', 
                    f'Usuario editado: {usuario.username}', 
                    request
                )
            
            success_msg = f'Usuario {usuario.username} actualizado exitosamente.'
            
            # Respuesta según el tipo de petición
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': success_msg
                })
            
            messages.success(request, success_msg)
            return redirect('login:administrar_usuarios')
            
        except Exception as e:
            error_msg = f'Error al actualizar usuario: {str(e)}'
            
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                })
            
            messages.error(request, error_msg)
            return redirect('login:administrar_usuarios')
    
    # Para peticiones GET AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'message': 'Método no permitido. Use POST para editar usuarios.'
        })
    
    return redirect('login:administrar_usuarios')

def eliminar_usuario(request, user_id):
    """Vista para eliminar un usuario"""
    usuario = get_object_or_404(User, id=user_id)
    
    # Solo permitir eliminar al propio usuario si no es el único administrador
    if request.user.is_authenticated and usuario == request.user:
        error_msg = 'No puedes eliminarte a ti mismo.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': error_msg})
        messages.error(request, error_msg)
        return redirect('login:administrar_usuarios')
    
    if request.method == 'POST':
        username = usuario.username
        
        try:
            # Registrar acción antes de eliminar si hay usuario autenticado
            if request.user.is_authenticated:
                registrar_accion(
                    request.user, 'delete', 
                    f'Usuario eliminado: {username}', 
                    request
                )
            
            usuario.delete()
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': f'Usuario {username} eliminado exitosamente.'
                })
            
            messages.success(request, f'Usuario {username} eliminado exitosamente.')
            
        except Exception as e:
            # Si es una petición AJAX, devolver JSON con error
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error al eliminar usuario: {str(e)}'
                })
            messages.error(request, f'Error al eliminar usuario: {str(e)}')
    
    return redirect('login:administrar_usuarios')

def toggle_usuario(request, user_id):
    """Vista para activar/desactivar un usuario"""
    usuario = get_object_or_404(User, id=user_id)

    if request.user.is_authenticated and usuario == request.user:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'No puedes desactivarte a ti mismo.'})
        messages.error(request, 'No puedes desactivarte a ti mismo.')
        return redirect('login:administrar_usuarios')

    usuario.is_active = not usuario.is_active
    usuario.save()

    estado = "activado" if usuario.is_active else "desactivado"

    # Registrar acción si hay usuario autenticado
    if request.user.is_authenticated:
        registrar_accion(
            request.user, 'update',
            f'Usuario {estado}: {usuario.username}',
            request
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'is_active': usuario.is_active,
            'message': f'Usuario {usuario.username} {estado} exitosamente.'
        })

    messages.success(request, f'Usuario {usuario.username} {estado} exitosamente.')
    return redirect('login:administrar_usuarios')

@login_required
def historial_usuario(request, user_id):
    """Vista para ver el historial de un usuario"""
    from remesas.models import Remesa, Pago, Moneda, PagoRemesa
    from decimal import Decimal
    from datetime import datetime, timedelta
    from django.db.models import Q
    
    usuario = get_object_or_404(User, id=user_id)
    
    # Solo el propio usuario o staff pueden ver el historial
    if usuario != request.user and not request.user.is_staff:
        messages.error(request, 'No tienes permisos para ver este historial.')
        return redirect('home')
    
    # Obtener parámetros de filtros generales
    search_query = request.GET.get('search', '')
    estado_filter = request.GET.get('estado', '')
    moneda_filter = request.GET.get('moneda', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    vista = request.GET.get('vista', 'remesas')
    
    # Filtros específicos para remesas
    search_remesas = request.GET.get('search_remesas', '')
    estado_remesas = request.GET.get('estado_remesas', '')
    moneda_remesas = request.GET.get('moneda_remesas', '')
    fecha_desde_remesas = request.GET.get('fecha_desde_remesas', '')
    fecha_hasta_remesas = request.GET.get('fecha_hasta_remesas', '')
    importe_min_remesas = request.GET.get('importe_min_remesas', '')
    importe_max_remesas = request.GET.get('importe_max_remesas', '')
    tipo_pago_remesas = request.GET.get('tipo_pago_remesas', '')
    
    # Filtros específicos para pagos  
    search_pagos = request.GET.get('search_pagos', '')
    tipo_pago_pagos = request.GET.get('tipo_pago_pagos', '')
    estado_pagos = request.GET.get('estado_pagos', '')
    moneda_pagos = request.GET.get('moneda_pagos', '')
    fecha_desde_pagos = request.GET.get('fecha_desde_pagos', '')
    fecha_hasta_pagos = request.GET.get('fecha_hasta_pagos', '')
    cantidad_min_pagos = request.GET.get('cantidad_min_pagos', '')
    cantidad_max_pagos = request.GET.get('cantidad_max_pagos', '')
    destinatario_pagos = request.GET.get('destinatario_pagos', '')
    
    # Filtros específicos para vista total
    search_total = request.GET.get('search_total', '')
    tipo_operacion = request.GET.get('tipo_operacion', '')
    moneda_total = request.GET.get('moneda_total', '')
    fecha_desde_total = request.GET.get('fecha_desde_total', '')
    fecha_hasta_total = request.GET.get('fecha_hasta_total', '')
    importe_min_total = request.GET.get('importe_min_total', '')
    importe_max_total = request.GET.get('importe_max_total', '')
    cantidad_min_total = request.GET.get('cantidad_min_total', '') or importe_min_total
    cantidad_max_total = request.GET.get('cantidad_max_total', '') or importe_max_total
    rango_usd = request.GET.get('rango_usd', '')
    
    # Obtener remesas del usuario
    remesas_queryset = Remesa.objects.filter(gestor=usuario).select_related('moneda')
    
    # Aplicar filtros a remesas según la vista
    if vista == 'remesas':
        # Filtros específicos para vista de remesas
        if search_remesas:
            remesas_queryset = remesas_queryset.filter(
                Q(remesa_id__icontains=search_remesas) |
                Q(receptor_nombre__icontains=search_remesas)
            )
        if estado_remesas:
            remesas_queryset = remesas_queryset.filter(estado=estado_remesas)
        if moneda_remesas:
            remesas_queryset = remesas_queryset.filter(moneda_id=moneda_remesas)
        if tipo_pago_remesas:
            remesas_queryset = remesas_queryset.filter(tipo_pago=tipo_pago_remesas)
        if importe_min_remesas:
            try:
                remesas_queryset = remesas_queryset.filter(importe__gte=float(importe_min_remesas))
            except ValueError:
                pass
        if importe_max_remesas:
            try:
                remesas_queryset = remesas_queryset.filter(importe__lte=float(importe_max_remesas))
            except ValueError:
                pass
        if fecha_desde_remesas:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde_remesas, '%Y-%m-%d')
                remesas_queryset = remesas_queryset.filter(fecha__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta_remesas:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta_remesas, '%Y-%m-%d') + timedelta(days=1)
                remesas_queryset = remesas_queryset.filter(fecha__lt=fecha_hasta_dt)
            except ValueError:
                pass
    elif vista == 'total':
        # Filtros específicos para vista total
        if search_total:
            remesas_queryset = remesas_queryset.filter(
                Q(remesa_id__icontains=search_total) |
                Q(receptor_nombre__icontains=search_total)
            )
        if moneda_total:
            remesas_queryset = remesas_queryset.filter(moneda_id=moneda_total)
        if fecha_desde_total:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde_total, '%Y-%m-%d')
                remesas_queryset = remesas_queryset.filter(fecha__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta_total:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta_total, '%Y-%m-%d') + timedelta(days=1)
                remesas_queryset = remesas_queryset.filter(fecha__lt=fecha_hasta_dt)
            except ValueError:
                pass
        if cantidad_min_total:
            try:
                remesas_queryset = remesas_queryset.filter(importe__gte=float(cantidad_min_total))
            except ValueError:
                pass
        if cantidad_max_total:
            try:
                remesas_queryset = remesas_queryset.filter(importe__lte=float(cantidad_max_total))
            except ValueError:
                pass
        if rango_usd:
            if rango_usd == '0-100':
                remesas_queryset = remesas_queryset.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
            elif rango_usd == '100-500':
                remesas_queryset = remesas_queryset.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
            elif rango_usd == '500-1000':
                remesas_queryset = remesas_queryset.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
            elif rango_usd == '1000-5000':
                remesas_queryset = remesas_queryset.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
            elif rango_usd == '5000+':
                remesas_queryset = remesas_queryset.filter(monto_usd_historico__gt=5000)
    # Si no es vista específica, usar filtros generales como fallback
    else:
        if search_query:
            remesas_queryset = remesas_queryset.filter(
                Q(remesa_id__icontains=search_query) |
                Q(receptor_nombre__icontains=search_query)
            )
        if estado_filter:
            remesas_queryset = remesas_queryset.filter(estado=estado_filter)
        if moneda_filter:
            remesas_queryset = remesas_queryset.filter(moneda_id=moneda_filter)
        if fecha_desde:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                remesas_queryset = remesas_queryset.filter(fecha__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1)
                remesas_queryset = remesas_queryset.filter(fecha__lt=fecha_hasta_dt)
            except ValueError:
                pass
    
    remesas_list = remesas_queryset.order_by('-fecha')
    
    # Obtener pagos del usuario
    pagos_queryset = Pago.objects.filter(usuario=usuario).select_related('tipo_moneda')
    pagos_remesa_queryset = PagoRemesa.objects.filter(usuario=usuario).select_related('tipo_moneda', 'remesa')
    
    # Aplicar filtros a pagos según la vista
    if vista == 'total' and tipo_operacion:
        if tipo_operacion == 'remesa':
            pagos_queryset = pagos_queryset.none()
            pagos_remesa_queryset = pagos_remesa_queryset.none()
        elif tipo_operacion == 'pago':
            remesas_queryset = remesas_queryset.none()

    if vista == 'pagos':
        # Filtros específicos para vista de pagos
        if search_pagos:
            pagos_queryset = pagos_queryset.filter(
                Q(pago_id__icontains=search_pagos) |
                Q(destinatario__icontains=search_pagos) |
                Q(telefono__icontains=search_pagos)
            )
            pagos_remesa_queryset = pagos_remesa_queryset.filter(
                Q(pago_id__icontains=search_pagos) |
                Q(destinatario__icontains=search_pagos) |
                Q(telefono__icontains=search_pagos)
            )
        if destinatario_pagos:
            pagos_queryset = pagos_queryset.filter(destinatario__icontains=destinatario_pagos)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(destinatario__icontains=destinatario_pagos)
        if tipo_pago_pagos:
            pagos_queryset = pagos_queryset.filter(tipo_pago=tipo_pago_pagos)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(tipo_pago=tipo_pago_pagos)
        if estado_pagos:
            pagos_queryset = pagos_queryset.filter(estado=estado_pagos)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(estado=estado_pagos)
        if moneda_pagos:
            pagos_queryset = pagos_queryset.filter(tipo_moneda_id=moneda_pagos)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(tipo_moneda_id=moneda_pagos)
        if cantidad_min_pagos:
            try:
                pagos_queryset = pagos_queryset.filter(cantidad__gte=float(cantidad_min_pagos))
                pagos_remesa_queryset = pagos_remesa_queryset.filter(cantidad__gte=float(cantidad_min_pagos))
            except ValueError:
                pass
        if cantidad_max_pagos:
            try:
                pagos_queryset = pagos_queryset.filter(cantidad__lte=float(cantidad_max_pagos))
                pagos_remesa_queryset = pagos_remesa_queryset.filter(cantidad__lte=float(cantidad_max_pagos))
            except ValueError:
                pass
        if fecha_desde_pagos:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde_pagos, '%Y-%m-%d')
                pagos_queryset = pagos_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta_pagos:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta_pagos, '%Y-%m-%d') + timedelta(days=1)
                pagos_queryset = pagos_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
            except ValueError:
                pass
    elif vista == 'total':
        # Filtros específicos para vista total en pagos
        if search_total:
            pagos_queryset = pagos_queryset.filter(
                Q(pago_id__icontains=search_total) |
                Q(destinatario__icontains=search_total) |
                Q(telefono__icontains=search_total)
            )
            pagos_remesa_queryset = pagos_remesa_queryset.filter(
                Q(pago_id__icontains=search_total) |
                Q(destinatario__icontains=search_total) |
                Q(telefono__icontains=search_total)
            )
        if moneda_total:
            pagos_queryset = pagos_queryset.filter(tipo_moneda_id=moneda_total)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(tipo_moneda_id=moneda_total)
        if fecha_desde_total:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde_total, '%Y-%m-%d')
                pagos_queryset = pagos_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta_total:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta_total, '%Y-%m-%d') + timedelta(days=1)
                pagos_queryset = pagos_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
            except ValueError:
                pass
        if cantidad_min_total:
            try:
                pagos_queryset = pagos_queryset.filter(cantidad__gte=float(cantidad_min_total))
                pagos_remesa_queryset = pagos_remesa_queryset.filter(cantidad__gte=float(cantidad_min_total))
            except ValueError:
                pass
        if cantidad_max_total:
            try:
                pagos_queryset = pagos_queryset.filter(cantidad__lte=float(cantidad_max_total))
                pagos_remesa_queryset = pagos_remesa_queryset.filter(cantidad__lte=float(cantidad_max_total))
            except ValueError:
                pass
        if rango_usd:
            if rango_usd == '0-100':
                pagos_queryset = pagos_queryset.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
            elif rango_usd == '100-500':
                pagos_queryset = pagos_queryset.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
            elif rango_usd == '500-1000':
                pagos_queryset = pagos_queryset.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
            elif rango_usd == '1000-5000':
                pagos_queryset = pagos_queryset.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
            elif rango_usd == '5000+':
                pagos_queryset = pagos_queryset.filter(monto_usd_historico__gt=5000)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(monto_usd_historico__gt=5000)
    # Si no es vista específica, usar filtros generales como fallback
    else:
        if search_query:
            pagos_queryset = pagos_queryset.filter(
                Q(pago_id__icontains=search_query) |
                Q(destinatario__icontains=search_query) |
                Q(telefono__icontains=search_query)
            )
            pagos_remesa_queryset = pagos_remesa_queryset.filter(
                Q(pago_id__icontains=search_query) |
                Q(destinatario__icontains=search_query) |
                Q(telefono__icontains=search_query)
            )
        if estado_filter:
            pagos_queryset = pagos_queryset.filter(estado=estado_filter)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(estado=estado_filter)
        if moneda_filter:
            pagos_queryset = pagos_queryset.filter(tipo_moneda_id=moneda_filter)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(tipo_moneda_id=moneda_filter)
        if fecha_desde:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                pagos_queryset = pagos_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1)
                pagos_queryset = pagos_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
                pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
            except ValueError:
                pass
    
    fecha_desde_term = fecha_desde_pagos or fecha_desde
    if fecha_desde_term:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde_term, '%Y-%m-%d')
            pagos_queryset = pagos_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__gte=fecha_desde_dt)
        except ValueError:
            pass
    
    fecha_hasta_term = fecha_hasta_pagos or fecha_hasta
    if fecha_hasta_term:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta_term, '%Y-%m-%d') + timedelta(days=1)
            pagos_queryset = pagos_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
            pagos_remesa_queryset = pagos_remesa_queryset.filter(fecha_creacion__lt=fecha_hasta_dt)
        except ValueError:
            pass
    
    pagos_list = pagos_queryset.order_by('-fecha_creacion')
    pagos_remesa_list = pagos_remesa_queryset.order_by('-fecha_creacion')
    
    # Agregar campos calculados a remesas usando valores históricos
    for remesa in remesas_list:
        # Usar el método que prioriza valores históricos guardados
        remesa.importe_usd = remesa.calcular_monto_en_usd()
    
    # Agregar campos calculados a pagos usando valores históricos
    for pago in pagos_list:
        # Campos que el template espera
        pago.numero_pago = pago.pago_id
        pago.destinatario_nombre = pago.destinatario
        pago.moneda = pago.tipo_moneda
        # El estado ya existe en el modelo, no necesitamos asignarlo
        
        # Usar el método que prioriza valores históricos guardados
        pago.cantidad_usd = pago.calcular_monto_en_usd()

    # Agregar campos calculados a pagos de remesa
    for pago_remesa in pagos_remesa_list:
        pago_remesa.numero_pago = pago_remesa.pago_id
        pago_remesa.destinatario_nombre = pago_remesa.destinatario
        pago_remesa.moneda = pago_remesa.tipo_moneda
        pago_remesa.cantidad_usd = pago_remesa.calcular_monto_en_usd()
    
    # Crear lista de transacciones combinadas
    total_transacciones = []
    
    # Agregar remesas
    for remesa in remesas_list:
        transaccion = type('Transaccion', (), {
            'tipo': 'remesa',
            'pk': remesa.pk,
            'remesa_id': remesa.remesa_id,
            'receptor_nombre': getattr(remesa, 'receptor_nombre', ''),
            'estado': remesa.estado,
            'importe': remesa.importe,
            'importe_usd': getattr(remesa, 'importe_usd', Decimal('0.00')),
            'moneda': remesa.moneda,
            'fecha_creacion': remesa.fecha,
        })()
        total_transacciones.append(transaccion)
    
    # Agregar pagos
    for pago in pagos_list:
        transaccion = type('Transaccion', (), {
            'tipo': 'pago',
            'pk': pago.pk,
            'numero_pago': pago.pago_id,
            'destinatario_nombre': pago.destinatario,
            'estado': pago.estado,  # Usar el estado real del pago
            'cantidad': pago.cantidad,
            'cantidad_usd': getattr(pago, 'cantidad_usd', Decimal('0.00')),
            'moneda': pago.tipo_moneda,
            'fecha_creacion': pago.fecha_creacion,
        })()
        total_transacciones.append(transaccion)

    # Agregar pagos de remesa
    for pago_remesa in pagos_remesa_list:
        transaccion = type('Transaccion', (), {
            'tipo': 'pago_remesa',
            'pk': pago_remesa.pk,
            'numero_pago': pago_remesa.pago_id,
            'destinatario_nombre': pago_remesa.destinatario,
            'estado': pago_remesa.estado,
            'cantidad': pago_remesa.cantidad,
            'cantidad_usd': getattr(pago_remesa, 'cantidad_usd', Decimal('0.00')),
            'moneda': pago_remesa.tipo_moneda,
            'fecha_creacion': pago_remesa.fecha_creacion,
            'remesa': pago_remesa.remesa,
        })()
        total_transacciones.append(transaccion)
    
    # Ordenar por fecha
    total_transacciones.sort(key=lambda x: x.fecha_creacion, reverse=True)

    # Paginación (igual que registro_transacciones)
    items_per_page = 20
    remesas_paginator = Paginator(remesas_list, items_per_page)
    pagos_paginator = Paginator(pagos_list, items_per_page)
    total_paginator = Paginator(total_transacciones, items_per_page)

    remesas_page_num = request.GET.get('remesas_page', 1)
    pagos_page_num = request.GET.get('pagos_page', 1)
    total_page_num = request.GET.get('total_page', 1)

    remesas = remesas_paginator.get_page(remesas_page_num)
    pagos = pagos_paginator.get_page(pagos_page_num)
    total_transacciones_page = total_paginator.get_page(total_page_num)
    
    # Estadísticas de elementos totales vs filtrados
    total_remesas_count = Remesa.objects.filter(gestor=usuario).count()
    total_pagos_count = Pago.objects.filter(usuario=usuario).count() + PagoRemesa.objects.filter(usuario=usuario).count()
    
    # Obtener balance calculado dinámicamente de las transacciones reales
    balance_calculado = usuario.perfil.calcular_balance_real() if hasattr(usuario, 'perfil') else Decimal('0.00')
    
    # Actualizar balance almacenado si difiere del calculado
    if hasattr(usuario, 'perfil') and usuario.perfil.balance != balance_calculado:
        usuario.perfil.actualizar_balance()
    
    balance = balance_calculado
    
    # Estadísticas - Solo remesas confirmadas y completadas para el total
    remesas_confirmadas_completadas = [r for r in remesas_list if r.estado in ['confirmada', 'completada']]
    
    # Calcular totales con manejo de errores
    total_remesas_usd = Decimal('0.00')
    for remesa in remesas_confirmadas_completadas:
        try:
            monto_usd = remesa.calcular_monto_en_usd()
            if monto_usd is not None:
                total_remesas_usd += Decimal(str(monto_usd))
        except Exception as e:
            logger.exception("Error calculando monto USD para remesa %s", getattr(remesa, 'remesa_id', 'N/A'))
            continue
    
    # Estadísticas - Solo pagos confirmados para el total
    pagos_confirmados = [p for p in pagos_list if p.estado == 'confirmado']
    pagos_remesa_confirmados = [p for p in pagos_remesa_list if p.estado == 'confirmado']
    
    total_pagos_usd = Decimal('0.00')
    for pago in pagos_confirmados:
        try:
            monto_usd = pago.calcular_monto_en_usd()
            if monto_usd is not None:
                total_pagos_usd += Decimal(str(monto_usd))
        except Exception as e:
            logger.exception("Error calculando monto USD para pago %s", getattr(pago, 'pago_id', 'N/A'))
            continue

    for pago in pagos_remesa_confirmados:
        try:
            monto_usd = pago.calcular_monto_en_usd()
            if monto_usd is not None:
                total_pagos_usd += Decimal(str(monto_usd))
        except Exception as e:
            logger.exception("Error calculando monto USD para pago remesa %s", getattr(pago, 'pago_id', 'N/A'))
            continue
    
    # Obtener opciones para filtros
    estados_disponibles = list(Remesa.objects.filter(gestor=usuario).values_list('estado', flat=True).distinct())
    monedas_disponibles = Moneda.objects.filter(activa=True)
    
    # Historial de acciones
    try:
        historial = HistorialAcciones.objects.filter(usuario=usuario)[:50]
    except:
        historial = []
    
    try:
        sesion = SesionUsuario.objects.get(usuario=usuario)
    except SesionUsuario.DoesNotExist:
        sesion = None
    
    context = {
        'usuario': usuario,
        'historial': historial,
        'sesion': sesion,
        'remesas': remesas,
        'pagos': pagos,
        'pagos_remesa': pagos_remesa_list,
        'total_transacciones': total_transacciones_page,
        'total_transacciones_count': len(total_transacciones),
        'remesas_count': remesas_list.count(),
        'total_remesas': total_remesas_usd,
        'pagos_count': pagos_list.count() + pagos_remesa_list.count(),
        'total_pagos': total_pagos_usd,
        'balance': balance,
        'total_remesas_count': total_remesas_count,
        'total_pagos_count': total_pagos_count,
        'search_query': search_query,
        'estado_filter': estado_filter,
        'moneda_filter': moneda_filter,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'vista': vista,
        'estados_disponibles': estados_disponibles,
        'monedas_disponibles': monedas_disponibles,
        'monedas': monedas_disponibles,  # Alias para el template
        # Filtros específicos de remesas
        'search_remesas': search_remesas,
        'estado_remesas': estado_remesas,
        'moneda_remesas': moneda_remesas,
        'fecha_desde_remesas': fecha_desde_remesas,
        'fecha_hasta_remesas': fecha_hasta_remesas,
        'importe_min_remesas': importe_min_remesas,
        'importe_max_remesas': importe_max_remesas,
        'tipo_pago_remesas': tipo_pago_remesas,
        # Filtros específicos de pagos
        'search_pagos': search_pagos,
        'tipo_pago_pagos': tipo_pago_pagos,
        'estado_pagos': estado_pagos,
        'moneda_pagos': moneda_pagos,
        'fecha_desde_pagos': fecha_desde_pagos,
        'fecha_hasta_pagos': fecha_hasta_pagos,
        'cantidad_min_pagos': cantidad_min_pagos,
        'cantidad_max_pagos': cantidad_max_pagos,
        'destinatario_pagos': destinatario_pagos,
        # Filtros específicos de total
        'search_total': search_total,
        'tipo_operacion': tipo_operacion,
        'moneda_total': moneda_total,
        'fecha_desde_total': fecha_desde_total,
        'fecha_hasta_total': fecha_hasta_total,
        'importe_min_total': importe_min_total,
        'importe_max_total': importe_max_total,
        'cantidad_min_total': cantidad_min_total,
        'cantidad_max_total': cantidad_max_total,
        'rango_usd': rango_usd,
    }

    # Querystrings para paginación
    def _build_qs(extra_params):
        params = request.GET.copy()
        for key in ['remesas_page', 'pagos_page', 'total_page']:
            params.pop(key, None)
        for key, value in extra_params.items():
            params[key] = value
        return params.urlencode()

    context.update({
        'querystring_remesas': _build_qs({'vista': 'remesas'}),
        'querystring_pagos': _build_qs({'vista': 'pagos'}),
        'querystring_total': _build_qs({'vista': 'total'}),
    })
    
    # Verificar si es una petición de exportación a Excel
    if request.GET.get('export') == 'excel':
        from django.http import HttpResponse
        import csv
        from io import StringIO
        from django.utils import timezone
        
        # Crear respuesta CSV (compatible con Excel)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{vista}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        output = StringIO()
        writer = csv.writer(output)
        
        if vista == 'remesas':
            # Headers
            writer.writerow(['ID', 'Receptor', 'Estado', 'Importe', 'Moneda', 'USD', 'Fecha'])
            
            # Datos
            for remesa in remesas_list:
                writer.writerow([
                    remesa.remesa_id,
                    getattr(remesa, 'receptor_nombre', ''),
                    remesa.estado,
                    float(remesa.importe) if remesa.importe else 0,
                    remesa.moneda.nombre if remesa.moneda else '',
                    float(getattr(remesa, 'importe_usd', 0)),
                    remesa.fecha.strftime('%Y-%m-%d') if remesa.fecha else ''
                ])
        elif vista == 'pagos':
            writer.writerow(['ID', 'Destinatario', 'Cantidad', 'Moneda', 'USD', 'Fecha'])
            
            for pago in pagos_list:
                writer.writerow([
                    pago.pago_id,
                    pago.destinatario,
                    float(pago.cantidad) if pago.cantidad else 0,
                    pago.tipo_moneda.nombre if pago.tipo_moneda else '',
                    float(getattr(pago, 'cantidad_usd', 0)),
                    pago.fecha_creacion.strftime('%Y-%m-%d') if pago.fecha_creacion else ''
                ])
        else:  # total
            writer.writerow(['Tipo', 'ID', 'Destinatario/Receptor', 'Estado', 'Importe/Cantidad', 'Moneda', 'USD', 'Fecha'])
            
            for trans in total_transacciones:
                writer.writerow([
                    trans.tipo.title(),
                    getattr(trans, 'remesa_id', '') or getattr(trans, 'numero_pago', ''),
                    getattr(trans, 'receptor_nombre', '') or getattr(trans, 'destinatario_nombre', ''),
                    trans.estado,
                    float(getattr(trans, 'importe', 0) or getattr(trans, 'cantidad', 0)),
                    trans.moneda.nombre if trans.moneda else '',
                    float(getattr(trans, 'importe_usd', 0) or getattr(trans, 'cantidad_usd', 0)),
                    trans.fecha_creacion.strftime('%Y-%m-%d') if trans.fecha_creacion else ''
                ])
        
        response.write(output.getvalue())
        return response
    
    return render(request, 'autenticacion/historial_usuario.html', context)

def obtener_usuario_ajax(request, user_id):
    """Vista AJAX para obtener datos de un usuario"""
    usuario = get_object_or_404(User, id=user_id)
    
    data = {
        'id': usuario.id,
        'username': usuario.username,
        'email': usuario.email,
        'first_name': usuario.first_name,
        'last_name': usuario.last_name,
        'is_active': usuario.is_active,
        'is_staff': usuario.is_staff,
        'is_superuser': usuario.is_superuser,
        'date_joined': usuario.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
        'last_login': usuario.last_login.strftime('%Y-%m-%d %H:%M:%S') if usuario.last_login else 'Nunca'
    }
    
    return JsonResponse(data)
