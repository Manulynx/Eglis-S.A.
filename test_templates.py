#!/usr/bin/env python3
"""
Script para probar que los templates se cargan correctamente
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.template.loader import get_template
from django.test import RequestFactory

def test_templates():
    """Probar que los templates se cargan sin errores"""
    templates_to_test = [
        'login/base_login.html',
        'login/login.html',
        'eglisapp/base.html',
    ]
    
    factory = RequestFactory()
    request = factory.get('/')
    
    for template_name in templates_to_test:
        try:
            template = get_template(template_name)
            print(f"✅ Template '{template_name}' cargado correctamente")
        except Exception as e:
            print(f"❌ Error en template '{template_name}': {e}")
    
    print("\n✅ Prueba de templates completada")

if __name__ == '__main__':
    test_templates()
