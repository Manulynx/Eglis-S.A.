#!/usr/bin/env python
import os
import sys
import django
import json
import requests
from django.test import Client
from django.contrib.auth.models import User

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

def test_crear_usuario_real():
    """Test real de creación de usuario con petición AJAX"""
    print("🧪 TEST REAL: CREAR USUARIO CON AJAX")
    print("=" * 60)
    
    # Crear cliente
    client = Client()
    
    # Login como admin
    try:
        admin = User.objects.get(username='Lazaro')
        client.force_login(admin)
        print(f"✅ Login como {admin.username}")
    except User.DoesNotExist:
        print("❌ No se encontró admin")
        return
    
    # Datos de prueba
    test_username = 'test_ajax_debug'
    datos = {
        'username': test_username,
        'first_name': 'Test',
        'last_name': 'Debug',
        'password1': 'testpass123',
        'password2': 'testpass123',
        'telefono': '+1234567890',
        'tipo_usuario': 'gestor',
        'tipo_valor_moneda': ''
    }
    
    # Eliminar usuario si existe
    try:
        existing = User.objects.get(username=test_username)
        existing.delete()
        print(f"🗑️  Usuario existente eliminado")
    except User.DoesNotExist:
        pass
    
    print(f"\n📤 Enviando petición AJAX...")
    
    # Hacer petición AJAX
    response = client.post('/login/admin/usuarios/crear/', 
                         data=datos,
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    print(f"\n📨 RESPUESTA:")
    print(f"   Status Code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type', 'No Content-Type')}")
    print(f"   Content-Length: {len(response.content)} bytes")
    
    # Intentar ver el contenido
    try:
        content = response.content.decode('utf-8')
        print(f"   Contenido (primeros 500 chars): {content[:500]}")
        
        # Intentar parsear como JSON
        try:
            json_data = json.loads(content)
            print(f"✅ JSON válido:")
            for key, value in json_data.items():
                print(f"      {key}: {value}")
        except json.JSONDecodeError:
            print(f"❌ NO es JSON válido")
            
    except Exception as e:
        print(f"❌ Error leyendo contenido: {e}")
    
    # Verificar si el usuario se creó
    try:
        created_user = User.objects.get(username=test_username)
        print(f"\n✅ Usuario encontrado en BD:")
        print(f"   ID: {created_user.id}")
        print(f"   Username: {created_user.username}")
        print(f"   Nombre: {created_user.first_name} {created_user.last_name}")
        
        # Verificar teléfono
        if hasattr(created_user, 'perfil'):
            print(f"   Teléfono: {created_user.perfil.telefono}")
        
        # Limpiar
        created_user.delete()
        print(f"🗑️  Usuario de prueba eliminado")
        
    except User.DoesNotExist:
        print(f"❌ Usuario NO se creó en BD")

def main():
    try:
        test_crear_usuario_real()
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()