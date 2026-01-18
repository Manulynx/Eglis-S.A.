from django.urls import path
from . import views
from .views_transacciones import registro_transacciones, exportar_excel

app_name = 'remesas'

urlpatterns = [
    path('registro/', registro_transacciones, name='registro_transacciones'),
    path('exportar/<str:tipo>/', exportar_excel, name='exportar_excel'),
    path('', views.remesas, name='nueva_remesa'),  # Changed name to match template
    path('admin/', views.remesas_admin, name='remesas_admin'),
    
    # APIs para formularios dinámicos
    path('api/monedas/', views.api_monedas, name='api_monedas'),
    path('api/gestores/', views.api_gestores, name='api_gestores'),
    path('api/metodos-pago/', views.api_metodos_pago, name='api_metodos_pago'),
    path('api/balance/', views.api_balance_usuario, name='api_balance_usuario'),

    # Otras URLs
    # path('lista/', views.lista_remesas, name='remesas_lista'),  # ELIMINADO - Reemplazado por registro_transacciones
    path('confirmar/<int:remesa_id>/', views.confirmar_remesa, name='confirmar_remesa'),
    # URL ELIMINADA - procesar_remesa ya no es necesario, la lógica se movió a confirmar_remesa
    path('cancelar/<int:remesa_id>/', views.cancelar_remesa, name='cancelar_remesa'),
    path('eliminar/<int:remesa_id>/', views.eliminar_remesa, name='eliminar_remesa'),
    path('detalle/<int:remesa_id>/', views.detalle_remesa, name='detalle_remesa'),
    path('editar/<int:remesa_id>/', views.editar_remesa, name='editar_remesa'),
    
    # URLs para Monedas
    path('monedas/', views.lista_monedas, name='lista_monedas'),
    path('monedas/crear/', views.crear_moneda, name='crear_moneda'),
    path('monedas/editar/<int:moneda_id>/', views.editar_moneda, name='editar_moneda'),
    path('monedas/eliminar/<int:moneda_id>/', views.eliminar_moneda, name='eliminar_moneda'),
    path('monedas/toggle-estado/<int:moneda_id>/', views.toggle_estado_moneda, name='toggle_estado_moneda'),
    path('monedas/actualizar-fondo/', views.actualizar_fondo_caja, name='actualizar_fondo_caja'),
    path('monedas/actualizar-alerta/', views.actualizar_alerta_minima, name='actualizar_alerta_minima'),
    
    # URLs para Tipos de Valores de Monedas
    path('tipos-valores/', views.lista_tipos_valores, name='lista_tipos_valores'),
    path('tipos-valores/crear/', views.crear_tipo_valor, name='crear_tipo_valor'),
    path('tipos-valores/editar/<int:tipo_id>/', views.editar_tipo_valor, name='editar_tipo_valor'),
    path('tipos-valores/eliminar/<int:tipo_id>/', views.eliminar_tipo_valor, name='eliminar_tipo_valor'),
    path('tipos-valores/toggle-estado/<int:tipo_id>/', views.toggle_estado_tipo_valor, name='toggle_estado_tipo_valor'),
    
    # URLs para Valores de Monedas
    path('valores-monedas/actualizar/', views.actualizar_valores_monedas, name='actualizar_valores_monedas'),
    path('valores-monedas/actualizar-individual/', views.actualizar_valor_individual, name='actualizar_valor_individual'),
    
    # URLs para Pagos
    # path('pagos/', views.lista_pagos, name='lista_pagos'),  # ELIMINADO - Reemplazado por registro_transacciones
    path('pagos/crear/', views.crear_pago, name='crear_pago'),
    path('pagos/detalle/<int:pago_id>/', views.detalle_pago, name='detalle_pago'),
    path('pagos/editar/<int:pago_id>/', views.editar_pago, name='editar_pago'),
    path('pagos/confirmar/<int:pago_id>/', views.confirmar_pago, name='confirmar_pago'),
    path('pagos/cancelar/<int:pago_id>/', views.cancelar_pago, name='cancelar_pago'),
    path('pagos/eliminar/<int:pago_id>/', views.eliminar_pago, name='eliminar_pago'),
    
    # URLs para Pagos de Remesas
    path('pagos-remesa/crear/<int:remesa_id>/', views.crear_pago_remesa, name='crear_pago_remesa'),
    path('pagos-remesa/listar/<int:remesa_id>/', views.listar_pagos_remesa, name='listar_pagos_remesa'),
    path('pagos-remesa/editar/<int:pago_id>/', views.editar_pago_remesa, name='editar_pago_remesa'),
    path('pagos-remesa/eliminar/<int:pago_id>/', views.eliminar_pago_remesa, name='eliminar_pago_remesa'),
    path('pagos-remesa/confirmar/<int:pago_id>/', views.confirmar_pago_remesa, name='confirmar_pago_remesa'),
    path('pagos-remesa/cancelar/<int:pago_id>/', views.cancelar_pago_remesa, name='cancelar_pago_remesa'),
]
