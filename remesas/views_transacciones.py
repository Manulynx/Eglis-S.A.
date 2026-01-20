from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo
from .models import Remesa, Pago, PagoRemesa, Moneda
from django.http import HttpResponse, JsonResponse
import csv
import io

@login_required
def registro_transacciones(request):
    # Obtener la pestaña activa desde el parámetro 'tab'
    tab_activa = request.GET.get('tab', 'remesas')  # Por defecto muestra remesas
    tipo = tab_activa  # Mantener compatibilidad con el resto del código
    
    # Consultas base - filtrar según el tipo de usuario
    user_tipo = 'admin' if request.user.is_superuser else (
        request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
    )
    
    if user_tipo == 'admin':
        # Si es admin, mostrar todos los registros
        remesas = Remesa.objects.select_related('moneda', 'gestor').all()
        pagos = Pago.objects.select_related('tipo_moneda').all()
        pagos_remesa = PagoRemesa.objects.select_related('tipo_moneda', 'usuario', 'remesa').all()
    elif user_tipo == 'contable':
        # Si es contable, mostrar todos los registros (incluyendo los de administradores)
        remesas = Remesa.objects.select_related('moneda', 'gestor').all()
        pagos = Pago.objects.select_related('tipo_moneda').all()
        pagos_remesa = PagoRemesa.objects.select_related('tipo_moneda', 'usuario', 'remesa').all()
    else:
        # Si es gestor u otro tipo, mostrar solo los registros del usuario actual
        remesas = Remesa.objects.select_related('moneda', 'gestor').filter(gestor=request.user)
        pagos = Pago.objects.select_related('tipo_moneda').filter(usuario=request.user)
        pagos_remesa = PagoRemesa.objects.select_related('tipo_moneda', 'usuario', 'remesa').filter(usuario=request.user)

    
    # Filtro de fecha rápido (Default: hoy)
    filtro_fecha = request.GET.get('filtro_fecha', 'hoy')
    
    if filtro_fecha != 'todas':
        # Obtener la fecha actual en la zona horaria de Cuba
        tz_cuba = ZoneInfo(settings.TIME_ZONE)
        ahora_utc = timezone.now()
        ahora_local = ahora_utc.astimezone(tz_cuba)
        today = ahora_local.date()
        
        if filtro_fecha == 'hoy':
            remesas = remesas.filter(
                Q(fecha__date=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=today)
            )
            pagos = pagos.filter(
                Q(fecha_creacion__date=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=today)
            )
            pagos_remesa = pagos_remesa.filter(
                Q(fecha_creacion__date=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=today)
            )
        elif filtro_fecha == 'ayer':
            yesterday = today - timedelta(days=1)
            remesas = remesas.filter(
                Q(fecha__date=yesterday)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=yesterday)
            )
            pagos = pagos.filter(
                Q(fecha_creacion__date=yesterday)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=yesterday)
            )
            pagos_remesa = pagos_remesa.filter(
                Q(fecha_creacion__date=yesterday)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date=yesterday)
            )
        elif filtro_fecha == 'semana':
            week_ago = today - timedelta(weeks=1)
            remesas = remesas.filter(
                Q(fecha__date__gte=week_ago, fecha__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=week_ago, cancelado_por_tiempo_en__date__lte=today)
            )
            pagos = pagos.filter(
                Q(fecha_creacion__date__gte=week_ago, fecha_creacion__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=week_ago, cancelado_por_tiempo_en__date__lte=today)
            )
            pagos_remesa = pagos_remesa.filter(
                Q(fecha_creacion__date__gte=week_ago, fecha_creacion__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=week_ago, cancelado_por_tiempo_en__date__lte=today)
            )
        elif filtro_fecha == 'mes':
            month_ago = today - timedelta(days=30)
            remesas = remesas.filter(
                Q(fecha__date__gte=month_ago, fecha__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=month_ago, cancelado_por_tiempo_en__date__lte=today)
            )
            pagos = pagos.filter(
                Q(fecha_creacion__date__gte=month_ago, fecha_creacion__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=month_ago, cancelado_por_tiempo_en__date__lte=today)
            )
            pagos_remesa = pagos_remesa.filter(
                Q(fecha_creacion__date__gte=month_ago, fecha_creacion__date__lte=today)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=month_ago, cancelado_por_tiempo_en__date__lte=today)
            )

    # Aplicar filtros específicos para REMESAS
    search_remesas = request.GET.get('search_remesas')
    estado_remesas = request.GET.get('estado_remesas')
    moneda_remesas = request.GET.get('moneda_remesas')
    tipo_pago_remesas = request.GET.get('tipo_pago_remesas')
    usuario_remesas = request.GET.get('usuario_remesas')
    fecha_desde_remesas = request.GET.get('fecha_desde_remesas')
    fecha_hasta_remesas = request.GET.get('fecha_hasta_remesas')
    importe_min_remesas = request.GET.get('importe_min_remesas')
    importe_max_remesas = request.GET.get('importe_max_remesas')
    
    if search_remesas:
        remesas = remesas.filter(
            Q(id__icontains=search_remesas) |
            Q(receptor_nombre__icontains=search_remesas) |
            Q(remesa_id__icontains=search_remesas)
        )
    
    if estado_remesas:
        remesas = remesas.filter(estado=estado_remesas)
    
    if moneda_remesas:
        remesas = remesas.filter(moneda_id=moneda_remesas)
    
    if tipo_pago_remesas:
        remesas = remesas.filter(tipo_pago=tipo_pago_remesas)
    
    if usuario_remesas:
        remesas = remesas.filter(gestor_id=usuario_remesas)
    
    if fecha_desde_remesas:
        try:
            fecha_desde = datetime.strptime(fecha_desde_remesas, '%Y-%m-%d').date()
            remesas = remesas.filter(
                Q(fecha__date__gte=fecha_desde)
                | Q(
                    cancelado_por_tiempo=True,
                    cancelado_por_tiempo_en__date__gte=fecha_desde,
                )
            )
        except ValueError:
            pass
    
    if fecha_hasta_remesas:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_remesas, '%Y-%m-%d').date()
            remesas = remesas.filter(
                Q(fecha__date__lte=fecha_hasta)
                | Q(
                    cancelado_por_tiempo=True,
                    cancelado_por_tiempo_en__date__lte=fecha_hasta,
                )
            )
        except ValueError:
            pass
    
    if importe_min_remesas:
        try:
            importe_min = float(importe_min_remesas)
            remesas = remesas.filter(importe__gte=importe_min)
        except ValueError:
            pass
    
    if importe_max_remesas:
        try:
            importe_max = float(importe_max_remesas)
            remesas = remesas.filter(importe__lte=importe_max)
        except ValueError:
            pass
    
    # Aplicar filtros específicos para PAGOS
    search_pagos = request.GET.get('search_pagos')
    estado_pagos = request.GET.get('estado_pagos')  # NUEVO: Filtro de estado
    tipo_pago_pagos = request.GET.get('tipo_pago_pagos')
    moneda_pagos = request.GET.get('moneda_pagos')
    usuario_pagos = request.GET.get('usuario_pagos')
    destinatario_pagos = request.GET.get('destinatario_pagos')
    fecha_desde_pagos = request.GET.get('fecha_desde_pagos')
    fecha_hasta_pagos = request.GET.get('fecha_hasta_pagos')
    cantidad_min_pagos = request.GET.get('cantidad_min_pagos')
    cantidad_max_pagos = request.GET.get('cantidad_max_pagos')
    
    if search_pagos:
        pagos = pagos.filter(
            Q(id__icontains=search_pagos) |
            Q(destinatario__icontains=search_pagos) |
            Q(pago_id__icontains=search_pagos)
        )
    
    # NUEVO: Filtro por estado
    if estado_pagos:
        pagos = pagos.filter(estado=estado_pagos)
    
    if tipo_pago_pagos:
        pagos = pagos.filter(tipo_pago=tipo_pago_pagos)
    
    if moneda_pagos:
        pagos = pagos.filter(tipo_moneda_id=moneda_pagos)
    
    if usuario_pagos:
        pagos = pagos.filter(usuario_id=usuario_pagos)
    
    if destinatario_pagos:
        pagos = pagos.filter(destinatario__icontains=destinatario_pagos)
    
    if fecha_desde_pagos:
        try:
            fecha_desde = datetime.strptime(fecha_desde_pagos, '%Y-%m-%d').date()
            pagos = pagos.filter(
                Q(fecha_creacion__date__gte=fecha_desde)
                | Q(
                    cancelado_por_tiempo=True,
                    cancelado_por_tiempo_en__date__gte=fecha_desde,
                )
            )
        except ValueError:
            pass
    
    if fecha_hasta_pagos:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_pagos, '%Y-%m-%d').date()
            pagos = pagos.filter(
                Q(fecha_creacion__date__lte=fecha_hasta)
                | Q(
                    cancelado_por_tiempo=True,
                    cancelado_por_tiempo_en__date__lte=fecha_hasta,
                )
            )
        except ValueError:
            pass
    
    if cantidad_min_pagos:
        try:
            cantidad_min = float(cantidad_min_pagos)
            pagos = pagos.filter(cantidad__gte=cantidad_min)
        except ValueError:
            pass
    
    if cantidad_max_pagos:
        try:
            cantidad_max = float(cantidad_max_pagos)
            pagos = pagos.filter(cantidad__lte=cantidad_max)
        except ValueError:
            pass
    
    # --- OPTIMIZACIÓN: Paginación en base de datos ---
    # En lugar de traer todos los objetos y filtrarlos en Python,
    # aplicamos filtros a los QuerySets y usamos UNION para paginar IDs.
    
    # 1. Preparar QuerySets base (copias para no afectar las pestañas individuales)
    total_remesas_qs = remesas.all()
    total_pagos_qs = pagos.all()
    total_pagos_remesa_qs = pagos_remesa.all()
    
    # 2. Obtener filtros de la pestaña TOTAL
    search_total = request.GET.get('search_total')
    tipo_operacion = request.GET.get('tipo_operacion')
    moneda_total = request.GET.get('moneda_total')
    usuario_total = request.GET.get('usuario_total')
    rango_usd = request.GET.get('rango_usd')
    fecha_desde_total = request.GET.get('fecha_desde_total')
    fecha_hasta_total = request.GET.get('fecha_hasta_total')
    cantidad_min_total = request.GET.get('cantidad_min_total')
    cantidad_max_total = request.GET.get('cantidad_max_total')
    
    # 3. Aplicar filtros a los QuerySets
    if search_total:
        total_remesas_qs = total_remesas_qs.filter(
            Q(remesa_id__icontains=search_total) | 
            Q(receptor_nombre__icontains=search_total)
        )
        total_pagos_qs = total_pagos_qs.filter(
            Q(pago_id__icontains=search_total) | 
            Q(destinatario__icontains=search_total)
        )
        total_pagos_remesa_qs = total_pagos_remesa_qs.filter(
            Q(pago_id__icontains=search_total) | 
            Q(destinatario__icontains=search_total)
        )
    
    if tipo_operacion:
        if tipo_operacion == 'remesa':
            total_pagos_qs = total_pagos_qs.none()
            total_pagos_remesa_qs = total_pagos_remesa_qs.none()
        elif tipo_operacion == 'pago':
            total_remesas_qs = total_remesas_qs.none()
            
    if moneda_total:
        try:
            moneda_obj = Moneda.objects.get(id=moneda_total)
            total_remesas_qs = total_remesas_qs.filter(moneda__codigo=moneda_obj.codigo)
            total_pagos_qs = total_pagos_qs.filter(tipo_moneda__codigo=moneda_obj.codigo)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(tipo_moneda__codigo=moneda_obj.codigo)
        except Moneda.DoesNotExist:
            pass
            
    if usuario_total:
        total_remesas_qs = total_remesas_qs.filter(gestor_id=usuario_total)
        total_pagos_qs = total_pagos_qs.filter(usuario_id=usuario_total)
        total_pagos_remesa_qs = total_pagos_remesa_qs.filter(usuario_id=usuario_total)
        
    if fecha_desde_total:
        try:
            fd = datetime.strptime(fecha_desde_total, '%Y-%m-%d').date()
            total_remesas_qs = total_remesas_qs.filter(
                Q(fecha__date__gte=fd) | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=fd)
            )
            total_pagos_qs = total_pagos_qs.filter(
                Q(fecha_creacion__date__gte=fd)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=fd)
            )
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(
                Q(fecha_creacion__date__gte=fd)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__gte=fd)
            )
        except ValueError: pass

    if fecha_hasta_total:
        try:
            fh = datetime.strptime(fecha_hasta_total, '%Y-%m-%d').date()
            total_remesas_qs = total_remesas_qs.filter(
                Q(fecha__date__lte=fh) | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__lte=fh)
            )
            total_pagos_qs = total_pagos_qs.filter(
                Q(fecha_creacion__date__lte=fh)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__lte=fh)
            )
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(
                Q(fecha_creacion__date__lte=fh)
                | Q(cancelado_por_tiempo=True, cancelado_por_tiempo_en__date__lte=fh)
            )
        except ValueError: pass

    if cantidad_min_total:
        try:
            cmin = float(cantidad_min_total)
            total_remesas_qs = total_remesas_qs.filter(importe__gte=cmin)
            total_pagos_qs = total_pagos_qs.filter(cantidad__gte=cmin)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(cantidad__gte=cmin)
        except ValueError: pass

    if cantidad_max_total:
        try:
            cmax = float(cantidad_max_total)
            total_remesas_qs = total_remesas_qs.filter(importe__lte=cmax)
            total_pagos_qs = total_pagos_qs.filter(cantidad__lte=cmax)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(cantidad__lte=cmax)
        except ValueError: pass
        
    if rango_usd:
        # Usamos valores históricos para filtrar en DB
        if rango_usd == '0-100':
            total_remesas_qs = total_remesas_qs.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
            total_pagos_qs = total_pagos_qs.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(monto_usd_historico__gte=0, monto_usd_historico__lte=100)
        elif rango_usd == '100-500':
            total_remesas_qs = total_remesas_qs.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
            total_pagos_qs = total_pagos_qs.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(monto_usd_historico__gt=100, monto_usd_historico__lte=500)
        elif rango_usd == '500-1000':
            total_remesas_qs = total_remesas_qs.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
            total_pagos_qs = total_pagos_qs.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(monto_usd_historico__gt=500, monto_usd_historico__lte=1000)
        elif rango_usd == '1000-5000':
            total_remesas_qs = total_remesas_qs.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
            total_pagos_qs = total_pagos_qs.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(monto_usd_historico__gt=1000, monto_usd_historico__lte=5000)
        elif rango_usd == '5000+':
            total_remesas_qs = total_remesas_qs.filter(monto_usd_historico__gt=5000)
            total_pagos_qs = total_pagos_qs.filter(monto_usd_historico__gt=5000)
            total_pagos_remesa_qs = total_pagos_remesa_qs.filter(monto_usd_historico__gt=5000)

    # 4. Crear UNION de valores ligeros
    from django.db.models import Value, CharField, F
    from django.db.models.functions import Coalesce
    
    # IMPORTANTE: Limpiar ordenamiento previo para evitar errores en UNION
    # "ORDER BY not allowed in subqueries of compound statements"
    
    remesas_values = total_remesas_qs.order_by().annotate(
        fecha_sort=Coalesce('cancelado_por_tiempo_en', 'fecha'),
        type_op=Value('remesa', output_field=CharField())
    ).values('id', 'fecha_sort', 'type_op')
    
    pagos_values = total_pagos_qs.order_by().annotate(
        fecha_sort=Coalesce('cancelado_por_tiempo_en', 'fecha_creacion'),
        type_op=Value('pago', output_field=CharField())
    ).values('id', 'fecha_sort', 'type_op')
    
    pagos_remesa_values = total_pagos_remesa_qs.order_by().annotate(
        fecha_sort=Coalesce('cancelado_por_tiempo_en', 'fecha_creacion'),
        type_op=Value('pago_remesa', output_field=CharField())
    ).values('id', 'fecha_sort', 'type_op')
    
    # Esta es la lista que se paginará (QuerySet)
    total_operaciones_list = remesas_values.union(pagos_values, pagos_remesa_values).order_by('-fecha_sort')
    
    # Ordenar resultados individuales (si fue cancelado por tiempo, usar la fecha de cancelación)
    remesas = remesas.annotate(_sort_dt=Coalesce('cancelado_por_tiempo_en', 'fecha')).order_by('-_sort_dt')
    pagos = pagos.annotate(_sort_dt=Coalesce('cancelado_por_tiempo_en', 'fecha_creacion')).order_by('-_sort_dt')
    pagos_remesa = pagos_remesa.annotate(_sort_dt=Coalesce('cancelado_por_tiempo_en', 'fecha_creacion')).order_by('-_sort_dt')
    
    # Estadísticas de remesas (basadas en los datos filtrados)
    total_pendientes = remesas.filter(estado='pendiente').count()
    total_confirmadas = 0  # Ya no tenemos estado confirmada como intermedio
    total_completadas = remesas.filter(estado='completada').count()
    total_canceladas = remesas.filter(estado='cancelada').count()
    
    # Calcular totales en USD
    remesas_count = remesas.count()
    pagos_count = pagos.count()
    pagos_remesa_count = pagos_remesa.count()
    total_pagos_count = pagos_count + pagos_remesa_count  # Sumar ambos tipos de pagos

    # Total de pagos COMPLETADOS/CONFIRMADOS (incluye PagoRemesa) dentro de los filtros actuales
    total_pagos_completados_count = (
        pagos.filter(estado='confirmado').count() + pagos_remesa.filter(estado='confirmado').count()
    )
    # total_operaciones_list es ahora un QuerySet, usar count()
    total_operaciones_count = total_operaciones_list.count()
    
    # Detectar si hay filtros aplicados para REMESAS
    filtros_remesas_aplicados = bool(
        search_remesas or estado_remesas or moneda_remesas or tipo_pago_remesas or usuario_remesas or
        fecha_desde_remesas or fecha_hasta_remesas or importe_min_remesas or importe_max_remesas
    )
    
    # Detectar si hay filtros aplicados para PAGOS
    filtros_pagos_aplicados = bool(
        search_pagos or tipo_pago_pagos or moneda_pagos or usuario_pagos or destinatario_pagos or 
        fecha_desde_pagos or fecha_hasta_pagos or cantidad_min_pagos or cantidad_max_pagos
    )
    
    # Detectar si hay filtros aplicados para TOTAL
    filtros_total_aplicados = bool(
        search_total or tipo_operacion or moneda_total or usuario_total or rango_usd or
        fecha_desde_total or fecha_hasta_total or cantidad_min_total or cantidad_max_total
    )
    
    # Calcular totales filtrados (mismo que el count ya que sin paginación)
    remesas_filtradas_count = remesas.count()
    pagos_filtrados_count = pagos.count()
    pagos_remesa_filtrados_count = pagos_remesa.count()
    total_pagos_filtrados_count = pagos_filtrados_count + pagos_remesa_filtrados_count
    total_filtradas_count = total_operaciones_count
    
    # TOTAL REMESAS: Sumar remesas filtradas (excluyendo canceladas a menos que se filtre explícitamente por ellas)
    # Optimización: Usar agregación de base de datos en lugar de iterar en Python
    from django.db.models import Sum, F, Case, When, DecimalField
    
    # Para calcular el total en USD, necesitamos considerar la conversión
    # Esto es complejo de hacer puramente en DB si la lógica de conversión es dinámica
    # Pero si usamos los campos históricos (monto_usd_historico), podemos optimizarlo
    
    # Intentar usar agregación si es posible, sino fallback a iteración pero solo sobre los IDs necesarios
    # Para mantener la consistencia con la lógica actual que usa calcular_monto_en_usd(),
    # seguiremos iterando pero solo si el dataset es pequeño, o aceptamos el costo para el total.
    # Una mejora real sería guardar el monto_usd siempre en la DB.
    
    # Si hay muchos registros, esto puede ser lento. 
    # Limitamos el cálculo de totales si hay demasiados registros y no es una petición de exportación
    MAX_ITEMS_FOR_TOTAL = 1000
    
    # TOTAL REMESAS: Solo contar remesas completadas
    if remesas_filtradas_count > MAX_ITEMS_FOR_TOTAL:
        # Si hay muchos, usar una aproximación o solo sumar los visibles si se prefiere
        # O mejor, usar los campos históricos que ya están en la DB
        total_remesas_agg = remesas.filter(estado='completada').aggregate(total=Sum('monto_usd_historico'))
        total_remesas = total_remesas_agg['total'] or 0
    else:
        # Comportamiento original para pocos registros - solo completadas
        total_remesas = sum(remesa.calcular_monto_en_usd() for remesa in remesas if remesa.estado == 'completada')
    
    # TOTAL PAGOS: Solo contar pagos completados/confirmados (incluyendo PagoRemesa)
    if pagos_filtrados_count > MAX_ITEMS_FOR_TOTAL:
        total_pagos_agg = pagos.filter(estado='confirmado').aggregate(total=Sum('monto_usd_historico'))
        total_pagos_remesa_agg = pagos_remesa.filter(estado='confirmado').aggregate(total=Sum('monto_usd_historico'))
        total_pagos = (total_pagos_agg['total'] or 0) + (total_pagos_remesa_agg['total'] or 0)
    else:
        # Solo completados/confirmados
        total_pagos = sum(pago.calcular_monto_en_usd() for pago in pagos if pago.estado == 'confirmado')
        total_pagos += sum(pago.calcular_monto_en_usd() for pago in pagos_remesa if pago.estado == 'confirmado')
    
    # Obtener monedas para filtros
    monedas = Moneda.objects.filter(activa=True)
    
    # Obtener usuarios para filtros (admin y contable ven todos, gestor no ve filtros de usuario)
    usuarios = []
    if request.user.is_authenticated:
        user_tipo_actual = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        if user_tipo_actual == 'admin' or user_tipo_actual == 'contable':
            from django.contrib.auth.models import User
            usuarios = User.objects.all().select_related('perfil').order_by('first_name', 'username')
    
    # Paginación
    items_per_page = 10
    remesas_paginator = Paginator(remesas, items_per_page)
    pagos_paginator = Paginator(pagos, items_per_page)
    total_paginator = Paginator(total_operaciones_list, items_per_page)
    
    remesas_page_num = request.GET.get('remesas_page', 1)
    pagos_page_num = request.GET.get('pagos_page', 1)
    total_page_num = request.GET.get('total_page', 1)
    
    try:
        remesas_page = remesas_paginator.page(remesas_page_num)
        # Agregar conteo de pagos enlazados a cada remesa en la página
        for remesa in remesas_page:
            remesa.pagos_count = remesa.pagos_enlazados.count()
    except PageNotAnInteger:
        remesas_page = remesas_paginator.page(1)
        # Agregar conteo de pagos enlazados
        for remesa in remesas_page:
            remesa.pagos_count = remesa.pagos_enlazados.count()
    except EmptyPage:
        remesas_page = remesas_paginator.page(remesas_paginator.num_pages)
        # Agregar conteo de pagos enlazados
        for remesa in remesas_page:
            remesa.pagos_count = remesa.pagos_enlazados.count()

    try:
        pagos_page = pagos_paginator.page(pagos_page_num)
    except PageNotAnInteger:
        pagos_page = pagos_paginator.page(1)
    except EmptyPage:
        pagos_page = pagos_paginator.page(pagos_paginator.num_pages)

    try:
        total_page = total_paginator.page(total_page_num)
    except PageNotAnInteger:
        total_page = total_paginator.page(1)
    except EmptyPage:
        total_page = total_paginator.page(total_paginator.num_pages)
    
    # --- OPTIMIZACIÓN: Transformar resultados paginados ---
    # total_page contiene dicts con IDs. Necesitamos los objetos completos.
    
    # 1. Obtener IDs de la página actual
    page_items = list(total_page.object_list)
    remesa_ids = [item['id'] for item in page_items if item['type_op'] == 'remesa']
    pago_ids = [item['id'] for item in page_items if item['type_op'] == 'pago']
    pago_remesa_ids = [item['id'] for item in page_items if item['type_op'] == 'pago_remesa']
    
    # 2. Fetch eficiente de objetos
    remesas_dict = {r.id: r for r in Remesa.objects.filter(id__in=remesa_ids).select_related('moneda', 'gestor').prefetch_related('pagos_enlazados')}
    pagos_dict = {p.id: p for p in Pago.objects.filter(id__in=pago_ids).select_related('tipo_moneda', 'usuario')}
    pagos_remesa_dict = {p.id: p for p in PagoRemesa.objects.filter(id__in=pago_remesa_ids).select_related('tipo_moneda', 'usuario', 'remesa')}
    
    # 3. Reconstruir lista de diccionarios para el template
    transformed_list = []
    for item in page_items:
        if item['type_op'] == 'remesa':
            remesa = remesas_dict.get(item['id'])
            if remesa:
                # Agregar conteo de pagos enlazados
                pagos_count = remesa.pagos_enlazados.count()
                
                transformed_list.append({
                    'id_operacion': remesa.remesa_id,
                    'tipo': remesa.tipo_pago.capitalize() if remesa.tipo_pago else 'Transferencia',
                    'cantidad': remesa.importe,
                    'moneda': remesa.moneda.codigo if remesa.moneda else 'USD',
                    'equiv_usd': remesa.calcular_monto_en_usd(),
                    'estado': remesa.estado,
                    'cancelado_por_tiempo': bool(getattr(remesa, 'cancelado_por_tiempo', False)),
                    'fecha': remesa.fecha,
                    'id_original': remesa.id,
                    'tipo_operacion': 'Remesa',
                    'remitente': remesa.receptor_nombre or '',
                    'destinatario': '',
                    'gestor': remesa.gestor,
                    'usuario': remesa.gestor,
                    'pagos_count': pagos_count  # Agregar conteo de pagos enlazados
                })
        elif item['type_op'] == 'pago':
            pago = pagos_dict.get(item['id'])
            if pago:
                transformed_list.append({
                    'id_operacion': pago.pago_id,
                    'tipo': pago.tipo_pago.capitalize() if pago.tipo_pago else 'Efectivo',
                    'cantidad': pago.cantidad,
                    'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
                    'equiv_usd': pago.calcular_monto_en_usd(),
                    'estado': pago.estado,
                    'cancelado_por_tiempo': bool(getattr(pago, 'cancelado_por_tiempo', False)),
                    'fecha': pago.fecha_creacion,
                    'id_original': pago.id,
                    'tipo_operacion': 'Pago',
                    'remitente': '',
                    'destinatario': pago.destinatario,
                    'gestor': pago.usuario,
                    'usuario': pago.usuario,
                    'tarjeta': pago.tarjeta if pago.tarjeta else None,
                    'telefono': pago.telefono if pago.telefono else None,
                    'carnet_identidad': pago.carnet_identidad if pago.carnet_identidad else None
                })
        else:  # pago_remesa
            pago = pagos_remesa_dict.get(item['id'])
            if pago:
                transformed_list.append({
                    'id_operacion': pago.pago_id,
                    'tipo': pago.tipo_pago.capitalize() if pago.tipo_pago else 'Efectivo',
                    'cantidad': pago.cantidad,
                    'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
                    'equiv_usd': pago.calcular_monto_en_usd(),
                    'estado': pago.estado,
                    'cancelado_por_tiempo': bool(getattr(pago, 'cancelado_por_tiempo', False)),
                    'fecha': pago.fecha_creacion,
                    'id_original': pago.id,
                    'tipo_operacion': 'PagoRemesa',
                    'remitente': '',
                    'destinatario': pago.destinatario,
                    'gestor': pago.usuario,
                    'usuario': pago.usuario,
                    'tarjeta': pago.tarjeta if pago.tarjeta else None,
                    'telefono': pago.telefono if pago.telefono else None,
                    'carnet_identidad': pago.carnet_identidad if pago.carnet_identidad else None,
                    'remesa': pago.remesa  # Agregar referencia a la remesa asociada
                })
    
    # 4. Reemplazar la lista de objetos en la página
    total_page.object_list = transformed_list
    
    # Obtener el tipo de usuario si está autenticado
    user_tipo = None
    if request.user.is_authenticated:
        if request.user.is_superuser:
            user_tipo = 'admin'
        elif hasattr(request.user, 'perfil'):
            user_tipo = request.user.perfil.tipo_usuario
        else:
            user_tipo = 'gestor'  # Default

    context = {
        'remesas': remesas_page,
        'pagos': pagos_page,
        'pagos_remesa': pagos_remesa.order_by('-fecha_creacion'),  # Agregar pagos de remesa
        'total_operaciones': total_page,
        'filtro_fecha': filtro_fecha,
        'total_pendientes': total_pendientes,
        'total_confirmadas': total_confirmadas,
        'total_completadas': total_completadas,
        'total_canceladas': total_canceladas,
        'tipo_actual': tipo,
        'tab_activa': tab_activa,  # Agregar para que el template sepa qué pestaña mostrar
        'remesas_count': remesas_count,
        'pagos_count': total_pagos_count,  # Usar contador total que incluye Pago y PagoRemesa
        'pagos_completados_count': total_pagos_completados_count,
        'total_operaciones_count': total_operaciones_count,
        'remesas_filtradas_count': remesas_filtradas_count,
        'pagos_filtrados_count': total_pagos_filtrados_count,  # Usar contador total filtrado
        'total_filtradas_count': total_filtradas_count,
        'total_remesas': total_remesas,
        'total_pagos': total_pagos,
        'monedas': monedas,
        'usuarios': usuarios,
        'filtros_remesas_aplicados': filtros_remesas_aplicados,
        'filtros_pagos_aplicados': filtros_pagos_aplicados,
        'filtros_total_aplicados': filtros_total_aplicados,
        'user_tipo': user_tipo,
        # NUEVO: Agregar opciones de estado para pagos
        'estados_pagos': Pago.ESTADO_CHOICES,
    }
    
    return render(request, 'remesas/registro_transacciones.html', context)


@login_required
def exportar_excel(request, tipo):
    """Vista para exportar datos a formato CSV (compatible con Excel)"""
    try:
        # Aplicar los mismos filtros que en la vista principal
        user_tipo = 'admin' if request.user.is_superuser else (
            request.user.perfil.tipo_usuario if hasattr(request.user, 'perfil') else 'gestor'
        )
        
        if user_tipo == 'admin':
            remesas = Remesa.objects.select_related('moneda', 'gestor').all()
            pagos = Pago.objects.select_related('tipo_moneda').all()
        elif user_tipo == 'contable':
            # Los contables ahora pueden ver todas las operaciones (incluyendo las de administradores)
            remesas = Remesa.objects.select_related('moneda', 'gestor').all()
            pagos = Pago.objects.select_related('tipo_moneda').all()
        else:
            remesas = Remesa.objects.select_related('moneda', 'gestor').filter(gestor=request.user)
            pagos = Pago.objects.select_related('tipo_moneda').filter(usuario=request.user)

        # Aplicar filtros de la URL
        if tipo == 'remesas':
            # Aplicar filtros específicos para REMESAS
            search_remesas = request.GET.get('search_remesas')
            estado_remesas = request.GET.get('estado_remesas')
            moneda_remesas = request.GET.get('moneda_remesas')
            tipo_pago_remesas = request.GET.get('tipo_pago_remesas')
            fecha_desde_remesas = request.GET.get('fecha_desde_remesas')
            fecha_hasta_remesas = request.GET.get('fecha_hasta_remesas')
            importe_min_remesas = request.GET.get('importe_min_remesas')
            importe_max_remesas = request.GET.get('importe_max_remesas')

            if search_remesas:
                remesas = remesas.filter(
                    Q(id__icontains=search_remesas) |
                    Q(receptor_nombre__icontains=search_remesas) |
                    Q(remesa_id__icontains=search_remesas)
                )
            if estado_remesas:
                remesas = remesas.filter(estado=estado_remesas)
            if moneda_remesas:
                remesas = remesas.filter(moneda_id=moneda_remesas)
            if tipo_pago_remesas:
                remesas = remesas.filter(tipo_pago=tipo_pago_remesas)
            if fecha_desde_remesas:
                try:
                    fecha_desde = datetime.strptime(fecha_desde_remesas, '%Y-%m-%d').date()
                    remesas = remesas.filter(fecha__date__gte=fecha_desde)
                except ValueError:
                    pass
            if fecha_hasta_remesas:
                try:
                    fecha_hasta = datetime.strptime(fecha_hasta_remesas, '%Y-%m-%d').date()
                    remesas = remesas.filter(fecha__date__lte=fecha_hasta)
                except ValueError:
                    pass
            if importe_min_remesas:
                try:
                    importe_min = float(importe_min_remesas)
                    remesas = remesas.filter(importe__gte=importe_min)
                except ValueError:
                    pass
            if importe_max_remesas:
                try:
                    importe_max = float(importe_max_remesas)
                    remesas = remesas.filter(importe__lte=importe_max)
                except ValueError:
                    pass

            # Crear respuesta CSV para remesas
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="Remesas_{timezone.now().strftime("%Y-%m-%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID Remesa', 'Receptor', 'Estado', 'Importe', 'Moneda', 'Equiv. USD', 'Fecha', 'Tipo Pago', 'Observaciones'])
            
            for remesa in remesas.order_by('-fecha'):
                writer.writerow([
                    remesa.remesa_id or '',
                    remesa.receptor_nombre or '',
                    remesa.get_estado_display(),
                    str(remesa.importe or 0),
                    remesa.moneda.codigo if remesa.moneda else 'USD',
                    f"{remesa.calcular_monto_en_usd():.2f}",
                    remesa.fecha.strftime('%Y-%m-%d') if remesa.fecha else '',
                    remesa.get_tipo_pago_display() if remesa.tipo_pago else '',
                    remesa.observaciones or ''
                ])

        elif tipo == 'pagos':
            # Aplicar filtros específicos para PAGOS
            search_pagos = request.GET.get('search_pagos')
            estado_pagos = request.GET.get('estado_pagos')  # NUEVO: Filtro de estado
            tipo_pago_pagos = request.GET.get('tipo_pago_pagos')
            moneda_pagos = request.GET.get('moneda_pagos')
            destinatario_pagos = request.GET.get('destinatario_pagos')
            fecha_desde_pagos = request.GET.get('fecha_desde_pagos')
            fecha_hasta_pagos = request.GET.get('fecha_hasta_pagos')
            cantidad_min_pagos = request.GET.get('cantidad_min_pagos')
            cantidad_max_pagos = request.GET.get('cantidad_max_pagos')

            if search_pagos:
                pagos = pagos.filter(
                    Q(id__icontains=search_pagos) |
                    Q(destinatario__icontains=search_pagos) |
                    Q(pago_id__icontains=search_pagos)
                )
            
            # NUEVO: Filtro por estado
            if estado_pagos:
                pagos = pagos.filter(estado=estado_pagos)
                
            if tipo_pago_pagos:
                pagos = pagos.filter(tipo_pago=tipo_pago_pagos)
            if moneda_pagos:
                pagos = pagos.filter(tipo_moneda_id=moneda_pagos)
            if destinatario_pagos:
                pagos = pagos.filter(destinatario__icontains=destinatario_pagos)
            if fecha_desde_pagos:
                try:
                    fecha_desde = datetime.strptime(fecha_desde_pagos, '%Y-%m-%d').date()
                    pagos = pagos.filter(fecha_creacion__date__gte=fecha_desde)
                except ValueError:
                    pass
            if fecha_hasta_pagos:
                try:
                    fecha_hasta = datetime.strptime(fecha_hasta_pagos, '%Y-%m-%d').date()
                    pagos = pagos.filter(fecha_creacion__date__lte=fecha_hasta)
                except ValueError:
                    pass
            if cantidad_min_pagos:
                try:
                    cantidad_min = float(cantidad_min_pagos)
                    pagos = pagos.filter(cantidad__gte=cantidad_min)
                except ValueError:
                    pass
            if cantidad_max_pagos:
                try:
                    cantidad_max = float(cantidad_max_pagos)
                    pagos = pagos.filter(cantidad__lte=cantidad_max)
                except ValueError:
                    pass

            # Crear respuesta CSV para pagos
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="Pagos_{timezone.now().strftime("%Y-%m-%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID Pago', 'Destinatario', 'Tipo Pago', 'Cantidad', 'Moneda', 'Equiv. USD', 'Fecha', 'Teléfono', 'Dirección'])
            
            for pago in pagos.order_by('-fecha_creacion'):
                writer.writerow([
                    pago.pago_id or '',
                    pago.destinatario or '',
                    pago.get_tipo_pago_display() if pago.tipo_pago else '',
                    str(pago.cantidad or 0),
                    pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
                    f"{pago.calcular_monto_en_usd():.2f}",
                    pago.fecha_creacion.strftime('%Y-%m-%d') if pago.fecha_creacion else '',
                    pago.telefono or '',
                    pago.direccion or ''
                ])

        elif tipo == 'total':
            # Crear lista combinada para pestaña "Total" con filtros
            total_operaciones_list = []
            
            # Aplicar filtros básicos a remesas y pagos
            remesas = remesas.order_by('-fecha')
            pagos = pagos.order_by('-fecha_creacion')
            
            # Agregar remesas a la lista combinada
            for remesa in remesas:
                total_operaciones_list.append({
                    'id_operacion': remesa.remesa_id,
                    'tipo_operacion': 'Remesa',
                    'cantidad': remesa.importe,
                    'moneda': remesa.moneda.codigo if remesa.moneda else 'USD',
                    'equiv_usd': remesa.calcular_monto_en_usd(),
                    'estado': remesa.estado,
                    'fecha': remesa.fecha,
                    'detalle': remesa.receptor_nombre or '',
                    'usuario': remesa.gestor.first_name or remesa.gestor.username if remesa.gestor else 'N/A'
                })
            
            # Agregar pagos a la lista combinada
            for pago in pagos:
                total_operaciones_list.append({
                    'id_operacion': pago.pago_id,
                    'tipo_operacion': 'Pago',
                    'cantidad': pago.cantidad,
                    'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
                    'equiv_usd': pago.calcular_monto_en_usd(),
                    'estado': pago.estado,  # Usar el estado real del pago
                    'fecha': pago.fecha_creacion,
                    'detalle': pago.destinatario or '',
                    'usuario': pago.usuario.first_name or pago.usuario.username if pago.usuario else 'N/A'
                })

            # Aplicar filtros específicos para TOTAL
            search_total = request.GET.get('search_total')
            tipo_operacion = request.GET.get('tipo_operacion')
            moneda_total = request.GET.get('moneda_total')
            rango_usd = request.GET.get('rango_usd')

            if search_total:
                search_lower = search_total.lower()
                total_operaciones_list = [op for op in total_operaciones_list 
                                         if (search_lower in (op.get('id_operacion', '') or '').lower() or
                                             search_lower in (op.get('detalle', '') or '').lower())]
            
            if tipo_operacion:
                if tipo_operacion == 'remesa':
                    total_operaciones_list = [op for op in total_operaciones_list if op['tipo_operacion'] == 'Remesa']
                elif tipo_operacion == 'pago':
                    total_operaciones_list = [op for op in total_operaciones_list if op['tipo_operacion'] == 'Pago']

            # Ordenar por fecha
            total_operaciones_list.sort(key=lambda x: x['fecha'], reverse=True)

            # Crear respuesta CSV para total
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="Operaciones_Total_{timezone.now().strftime("%Y-%m-%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID Operación', 'Tipo', 'Usuario', 'Cantidad', 'Moneda', 'Equiv. USD', 'Estado', 'Fecha', 'Detalle'])
            
            for operacion in total_operaciones_list:
                writer.writerow([
                    operacion['id_operacion'] or '',
                    operacion['tipo_operacion'],
                    operacion['usuario'],
                    str(operacion['cantidad'] or 0),
                    operacion['moneda'],
                    f"{operacion['equiv_usd']:.2f}",
                    operacion['estado'],
                    operacion['fecha'].strftime('%Y-%m-%d') if operacion['fecha'] else '',
                    operacion['detalle']
                ])

        else:
            return JsonResponse({'error': 'Tipo de exportación no válido'}, status=400)

        return response

    except Exception as e:
        return JsonResponse({'error': f'Error al exportar: {str(e)}'}, status=500)
