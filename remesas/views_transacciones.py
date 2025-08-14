from django.shortcuts import render
# from django.core.paginator import Paginator  # COMENTADO TEMPORALMENTE
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import datetime
from .models import Remesa, Pago, Moneda
from django.http import HttpResponse, JsonResponse
import csv
import io

@login_required
def registro_transacciones(request):
    # Obtener la pestaña activa desde el parámetro 'tab'
    tab_activa = request.GET.get('tab', 'remesas')  # Por defecto muestra remesas
    tipo = tab_activa  # Mantener compatibilidad con el resto del código
    
    # Consultas base - filtrar por usuario si no es admin
    if request.user.is_staff or request.user.is_superuser:
        # Si es admin, mostrar todos los registros
        remesas = Remesa.objects.select_related('moneda', 'gestor').all()
        pagos = Pago.objects.select_related('tipo_moneda').all()
    else:
        # Si no es admin, mostrar solo los registros del usuario actual
        remesas = Remesa.objects.select_related('moneda', 'gestor').filter(gestor=request.user)
        pagos = Pago.objects.select_related('tipo_moneda').filter(usuario=request.user)
    
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
            remesas = remesas.filter(fecha__gte=fecha_desde)
        except ValueError:
            pass
    
    if fecha_hasta_remesas:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_remesas, '%Y-%m-%d').date()
            remesas = remesas.filter(fecha__lte=fecha_hasta)
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
    
    # Crear lista combinada para pestaña "Total"
    total_operaciones_list = []
    
    # Agregar remesas a la lista combinada
    for remesa in remesas:
        total_operaciones_list.append({
            'id_operacion': remesa.remesa_id,  # ID completo de la remesa
            'tipo': remesa.tipo_pago.capitalize() if remesa.tipo_pago else 'Transferencia',
            'cantidad': remesa.importe,
            'moneda': remesa.moneda.codigo if remesa.moneda else 'USD',
            'equiv_usd': remesa.calcular_monto_en_usd(),
            'estado': remesa.estado,
            'fecha': remesa.fecha,  # Mantenemos fecha para filtros
            'id_original': remesa.id,
            'tipo_operacion': 'Remesa',
            'remitente': remesa.receptor_nombre or '',  # Usar el campo correcto del modelo
            'destinatario': ''  # Las remesas no tienen destinatario separado
        })
    
    # Agregar pagos a la lista combinada
    for pago in pagos:
        total_operaciones_list.append({
            'id_operacion': pago.pago_id,  # ID completo del pago
            'tipo': pago.tipo_pago.capitalize() if pago.tipo_pago else 'Efectivo',
            'cantidad': pago.cantidad,
            'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
            'equiv_usd': pago.calcular_monto_en_usd(),
            'estado': 'efectuado',  # Estado fijo para pagos
            'fecha': pago.fecha_creacion,  # Mantenemos fecha para filtros
            'id_original': pago.id,
            'tipo_operacion': 'Pago',
            'remitente': '',  # Agregado para búsqueda
            'destinatario': pago.destinatario  # Agregado para búsqueda
        })
    
    # Aplicar filtros específicos para TOTAL
    search_total = request.GET.get('search_total')
    tipo_operacion = request.GET.get('tipo_operacion')
    moneda_total = request.GET.get('moneda_total')
    rango_usd = request.GET.get('rango_usd')
    fecha_desde_total = request.GET.get('fecha_desde_total')
    fecha_hasta_total = request.GET.get('fecha_hasta_total')
    cantidad_min_total = request.GET.get('cantidad_min_total')
    cantidad_max_total = request.GET.get('cantidad_max_total')
    
    # Aplicar filtros a la lista combinada
    if search_total:
        search_lower = search_total.lower()
        total_operaciones_list = [op for op in total_operaciones_list 
                                 if (search_lower in (op.get('id_operacion', '') or '').lower() or
                                     search_lower in (op.get('remitente', '') or '').lower() or
                                     search_lower in (op.get('destinatario', '') or '').lower())]
    
    if tipo_operacion:
        if tipo_operacion == 'remesa':
            total_operaciones_list = [op for op in total_operaciones_list if op['tipo_operacion'] == 'Remesa']
        elif tipo_operacion == 'pago':
            total_operaciones_list = [op for op in total_operaciones_list if op['tipo_operacion'] == 'Pago']
    
    if moneda_total:
        try:
            moneda_obj = Moneda.objects.get(id=moneda_total)
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['moneda'] == moneda_obj.codigo]
        except Moneda.DoesNotExist:
            pass
    
    if rango_usd:
        if rango_usd == '0-100':
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['equiv_usd'] is not None and 0 <= op['equiv_usd'] <= 100]
        elif rango_usd == '100-500':
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['equiv_usd'] is not None and 100 < op['equiv_usd'] <= 500]
        elif rango_usd == '500-1000':
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['equiv_usd'] is not None and 500 < op['equiv_usd'] <= 1000]
        elif rango_usd == '1000-5000':
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['equiv_usd'] is not None and 1000 < op['equiv_usd'] <= 5000]
        elif rango_usd == '5000+':
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['equiv_usd'] is not None and op['equiv_usd'] > 5000]
    
    if fecha_desde_total:
        try:
            fecha_desde = datetime.strptime(fecha_desde_total, '%Y-%m-%d').date()
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if (op['fecha'].date() >= fecha_desde 
                                         if hasattr(op['fecha'], 'date') else op['fecha'] >= fecha_desde)]
        except ValueError:
            pass
    
    if fecha_hasta_total:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_total, '%Y-%m-%d').date()
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if (op['fecha'].date() <= fecha_hasta 
                                         if hasattr(op['fecha'], 'date') else op['fecha'] <= fecha_hasta)]
        except ValueError:
            pass
    
    if cantidad_min_total:
        try:
            cantidad_min = float(cantidad_min_total)
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['cantidad'] is not None and op['cantidad'] >= cantidad_min]
        except ValueError:
            pass
    
    if cantidad_max_total:
        try:
            cantidad_max = float(cantidad_max_total)
            total_operaciones_list = [op for op in total_operaciones_list 
                                     if op['cantidad'] is not None and op['cantidad'] <= cantidad_max]
        except ValueError:
            pass
    
    # Ordenar por fecha (más recientes primero) - manejo seguro de fechas
    try:
        total_operaciones_list.sort(key=lambda x: x['fecha'], reverse=True)
    except (TypeError, KeyError):
        # Si hay problemas con las fechas, usar orden por id como fallback
        total_operaciones_list.sort(key=lambda x: x.get('id_original', 0), reverse=True)
    
    # Ordenar resultados
    remesas = remesas.order_by('-fecha')
    pagos = pagos.order_by('-fecha_creacion')
    
    # Estadísticas de remesas (basadas en los datos filtrados)
    total_pendientes = remesas.filter(estado='pendiente').count()
    total_confirmadas = remesas.filter(estado='confirmada').count()
    total_completadas = remesas.filter(estado='completada').count()
    total_canceladas = remesas.filter(estado='cancelada').count()
    
    # Calcular totales en USD
    remesas_count = remesas.count()
    pagos_count = pagos.count()
    total_operaciones_count = len(total_operaciones_list)
    
    # Calcular totales filtrados (mismo que el count ya que sin paginación)
    remesas_filtradas_count = remesas_count
    pagos_filtrados_count = pagos_count
    total_filtradas_count = total_operaciones_count
    
    # TOTAL REMESAS: Solo sumar remesas confirmadas y completadas
    remesas_confirmadas_completadas = remesas.filter(estado__in=['confirmada', 'completada'])
    total_remesas = sum(remesa.calcular_monto_en_usd() for remesa in remesas_confirmadas_completadas)
    
    total_pagos = sum(pago.calcular_monto_en_usd() for pago in pagos)
    
    # Obtener monedas para filtros
    monedas = Moneda.objects.filter(activa=True)
    
    # PAGINACIÓN COMENTADA TEMPORALMENTE - Mostrando todos los resultados
    # remesas_paginator = Paginator(remesas, 10)
    # pagos_paginator = Paginator(pagos, 10)
    # total_paginator = Paginator(total_operaciones_list, 10)
    
    # remesas_page_num = request.GET.get('remesas_page', 1)
    # pagos_page_num = request.GET.get('pagos_page', 1)
    # total_page_num = request.GET.get('total_page', 1)
    
    # remesas_page = remesas_paginator.get_page(remesas_page_num)
    # pagos_page = pagos_paginator.get_page(pagos_page_num)
    # total_page = total_paginator.get_page(total_page_num)
    
    context = {
        'remesas': remesas,  # Mostrando todos los resultados sin paginación
        'pagos': pagos,  # Mostrando todos los resultados sin paginación
        'total_operaciones': total_operaciones_list,  # Mostrando todos los resultados sin paginación
        'total_pendientes': total_pendientes,
        'total_confirmadas': total_confirmadas,
        'total_completadas': total_completadas,
        'total_canceladas': total_canceladas,
        'tipo_actual': tipo,
        'tab_activa': tab_activa,  # Agregar para que el template sepa qué pestaña mostrar
        'remesas_count': remesas_count,
        'pagos_count': pagos_count,
        'total_operaciones_count': total_operaciones_count,
        'remesas_filtradas_count': remesas_filtradas_count,
        'pagos_filtrados_count': pagos_filtrados_count,
        'total_filtradas_count': total_filtradas_count,
        'total_remesas': total_remesas,
        'total_pagos': total_pagos,
        'monedas': monedas,
    }
    
    return render(request, 'remesas/registro_transacciones.html', context)


@login_required
def exportar_excel(request, tipo):
    """Vista para exportar datos a formato CSV (compatible con Excel)"""
    try:
        # Aplicar los mismos filtros que en la vista principal
        if request.user.is_staff or request.user.is_superuser:
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
                    remesas = remesas.filter(fecha__gte=fecha_desde)
                except ValueError:
                    pass
            if fecha_hasta_remesas:
                try:
                    fecha_hasta = datetime.strptime(fecha_hasta_remesas, '%Y-%m-%d').date()
                    remesas = remesas.filter(fecha__lte=fecha_hasta)
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
            response['Content-Disposition'] = f'attachment; filename="Remesas_{datetime.now().strftime("%Y-%m-%d")}.csv"'
            
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
            response['Content-Disposition'] = f'attachment; filename="Pagos_{datetime.now().strftime("%Y-%m-%d")}.csv"'
            
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
                    'detalle': remesa.receptor_nombre or ''
                })
            
            # Agregar pagos a la lista combinada
            for pago in pagos:
                total_operaciones_list.append({
                    'id_operacion': pago.pago_id,
                    'tipo_operacion': 'Pago',
                    'cantidad': pago.cantidad,
                    'moneda': pago.tipo_moneda.codigo if pago.tipo_moneda else 'USD',
                    'equiv_usd': pago.calcular_monto_en_usd(),
                    'estado': 'efectuado',
                    'fecha': pago.fecha_creacion,
                    'detalle': pago.destinatario or ''
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
            response['Content-Disposition'] = f'attachment; filename="Operaciones_Total_{datetime.now().strftime("%Y-%m-%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID Operación', 'Tipo', 'Cantidad', 'Moneda', 'Equiv. USD', 'Estado', 'Fecha', 'Detalle'])
            
            for operacion in total_operaciones_list:
                writer.writerow([
                    operacion['id_operacion'] or '',
                    operacion['tipo_operacion'],
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
