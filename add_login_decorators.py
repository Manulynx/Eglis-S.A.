#!/usr/bin/env python3
"""
Script para agregar decoradores @login_required a todas las vistas del proyecto.
"""
import re
import os

def add_login_decorators(file_path):
    """Agrega decoradores @login_required a las funciones de vista."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patrones para identificar funciones de vista que necesitan decorador
    view_functions = [
        'api_gestores', 'api_metodos_pago', 'confirmar_remesa', 'procesar_remesa',
        # 'lista_remesas', 'cancelar_remesa', 'detalle_remesa', 'editar_remesa',  # lista_remesas eliminada
        'cancelar_remesa', 'detalle_remesa', 'editar_remesa',
        'lista_monedas', 'crear_moneda', 'editar_moneda', 'eliminar_moneda',
        # 'toggle_estado_moneda', 'lista_pagos', 'crear_pago', 'editar_pago',  # lista_pagos eliminada
        'toggle_estado_moneda', 'crear_pago', 'editar_pago',
        'detalle_pago', 'eliminar_pago'
    ]
    
    # Agregar decoradores
    for func_name in view_functions:
        # Buscar la función y agregar decorador si no lo tiene
        pattern = rf'^def {func_name}\('
        replacement = f'@login_required\ndef {func_name}('
        
        # Solo reemplazar si no tiene ya el decorador
        if not re.search(rf'@login_required\s*\ndef {func_name}\(', content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Decoradores agregados a {file_path}")

if __name__ == '__main__':
    # Agregar decoradores al archivo de vistas de remesas
    remesas_views = 'remesas/views.py'
    if os.path.exists(remesas_views):
        add_login_decorators(remesas_views)
    
    # También verificar views_transacciones.py si existe
    transacciones_views = 'remesas/views_transacciones.py'
    if os.path.exists(transacciones_views):
        add_login_decorators(transacciones_views)
    
    print("Proceso completado.")
