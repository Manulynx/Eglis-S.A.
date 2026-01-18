#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
import json

def test_crear_usuario_ajax():
    """Test para verificar la creación de usuarios vía AJAX"""
    print("🧪 TESTING CREACIÓN DE USUARIO VIA AJAX")
    print("=" * 60)
    
    # Crear cliente de pruebas
    client = Client()
    
    # Crear un usuario administrador para hacer la prueba
    try:
        admin_user = User.objects.get(username='Lazaro')
        print(f"✅ Usuario admin encontrado: {admin_user.username}")
    except User.DoesNotExist:
        print("❌ No se encontró usuario admin para la prueba")
        return
    
    # Hacer login como admin
    client.force_login(admin_user)
    print(f"✅ Login realizado como {admin_user.username}")
    
    # Datos de prueba válidos
    datos_validos = {
        'username': 'test_ajax_user',
        'first_name': 'Test',
        'last_name': 'Ajax User',
        'password1': 'testpass123',
        'password2': 'testpass123',
        'telefono': '+1234567890',
        'tipo_usuario': 'gestor',
        'tipo_valor_moneda': ''
    }
    
    print(f"\n📤 Enviando datos válidos:")
    for key, value in datos_validos.items():
        if 'password' not in key:
            print(f"   {key}: {value}")
    
    # Hacer petición AJAX
    response = client.post('/login/admin/usuarios/crear/', 
                         data=datos_validos,
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    print(f"\n📨 Respuesta del servidor:")
    print(f"   Status Code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type')}")
    
    try:
        response_data = json.loads(response.content.decode())
        print(f"   JSON válido: ✅")
        print(f"   Status: {response_data.get('status')}")
        print(f"   Message: {response_data.get('message')}")
        
        if response_data.get('status') == 'success':
            print(f"✅ Usuario creado exitosamente vía AJAX")
            
            # Verificar que el usuario existe
            try:
                created_user = User.objects.get(username=datos_validos['username'])
                print(f"✅ Usuario verificado en BD: {created_user.username}")
                
                # Verificar teléfono
                if hasattr(created_user, 'perfil') and created_user.perfil.telefono:
                    print(f"✅ Teléfono guardado: {created_user.perfil.telefono}")
                else:
                    print(f"❌ Teléfono no guardado")
                
                # Limpiar - eliminar usuario de prueba
                created_user.delete()
                print(f"✅ Usuario de prueba eliminado")
                
            except User.DoesNotExist:
                print(f"❌ Usuario no encontrado en BD después de creación")
                
        else:
            print(f"❌ Error en creación: {response_data.get('message')}")
            
    except json.JSONDecodeError as e:
        print(f"❌ Respuesta no es JSON válido: {e}")
        print(f"   Contenido: {response.content.decode()[:500]}...")
    
    # Test con datos inválidos (contraseñas no coinciden)
    print(f"\n🧪 TESTING CON DATOS INVÁLIDOS:")
    
    datos_invalidos = datos_validos.copy()
    datos_invalidos['username'] = 'test_ajax_invalid'
    datos_invalidos['password2'] = 'diferentes'
    
    response_invalid = client.post('/login/admin/usuarios/crear/', 
                                 data=datos_invalidos,
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    try:
        response_data = json.loads(response_invalid.content.decode())
        print(f"   Status: {response_data.get('status')}")
        print(f"   Message: {response_data.get('message')}")
        
        if response_data.get('status') == 'error':
            print(f"✅ Manejo de errores funciona correctamente")
        else:
            print(f"❌ Error no fue detectado correctamente")
            
    except json.JSONDecodeError:
        print(f"❌ Respuesta de error no es JSON válido")

def main():
    try:
        test_crear_usuario_ajax()
        print(f"\n✅ Pruebas completadas")
    except Exception as e:
        print(f"❌ Error en las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()