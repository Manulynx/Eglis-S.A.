#!/usr/bin/env python
import os
import sys
import django
from decimal import Decimal

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.contrib.auth.models import User
from login.models import PerfilUsuario

def test_crear_usuario_con_telefono():
    """Test para verificar la creación de usuarios con teléfono"""
    print("🧪 TESTING CREACIÓN DE USUARIO CON TELÉFONO")
    print("=" * 60)
    
    # Datos de prueba
    test_data = {
        'username': 'test_user_telefono',
        'first_name': 'Usuario',
        'last_name': 'De Prueba',
        'password': 'testpass123',
        'telefono': '+1234567890',
        'tipo_usuario': 'gestor'
    }
    
    print(f"📝 Datos de prueba:")
    for key, value in test_data.items():
        if key != 'password':
            print(f"   {key}: {value}")
        else:
            print(f"   {key}: ****")
    
    try:
        # Verificar si el usuario ya existe y eliminarlo
        try:
            existing_user = User.objects.get(username=test_data['username'])
            print(f"⚠️  Usuario '{test_data['username']}' ya existe, eliminándolo...")
            existing_user.delete()
        except User.DoesNotExist:
            pass
        
        # Crear el usuario usando el mismo método que la vista
        print(f"\n🏗️  Creando usuario...")
        
        user = User.objects.create_user(
            username=test_data['username'],
            email='',
            password=test_data['password'],
            first_name=test_data['first_name'],
            last_name=test_data['last_name'],
            is_staff=False,
            is_superuser=False
        )
        
        print(f"✅ Usuario creado con ID: {user.id}")
        
        # Verificar que el perfil se haya creado
        try:
            perfil = user.perfil
            print(f"✅ Perfil encontrado con ID: {perfil.id}")
        except PerfilUsuario.DoesNotExist:
            print(f"❌ Perfil no encontrado, creándolo...")
            perfil = PerfilUsuario.objects.create(usuario=user)
        
        # Asignar datos al perfil
        perfil.tipo_usuario = test_data['tipo_usuario']
        perfil.telefono = test_data['telefono']
        perfil.save()
        
        print(f"✅ Perfil actualizado")
        
        # Verificar que se guardó correctamente
        user_verificado = User.objects.get(id=user.id)
        perfil_verificado = user_verificado.perfil
        
        print(f"\n🔍 VERIFICACIÓN:")
        print(f"   Username: {user_verificado.username}")
        print(f"   Nombre completo: {user_verificado.first_name} {user_verificado.last_name}")
        print(f"   Tipo usuario: {perfil_verificado.tipo_usuario}")
        print(f"   Teléfono: '{perfil_verificado.telefono}'")
        
        # Verificar si el teléfono se guardó
        if perfil_verificado.telefono == test_data['telefono']:
            print(f"✅ TELÉFONO GUARDADO CORRECTAMENTE: {perfil_verificado.telefono}")
            resultado_telefono = True
        else:
            print(f"❌ ERROR: Teléfono no coincide")
            print(f"   Esperado: '{test_data['telefono']}'")
            print(f"   Encontrado: '{perfil_verificado.telefono}'")
            resultado_telefono = False
        
        # Limpiar - eliminar usuario de prueba
        print(f"\n🧹 Limpiando usuario de prueba...")
        user_verificado.delete()
        print(f"✅ Usuario de prueba eliminado")
        
        return resultado_telefono
        
    except Exception as e:
        print(f"❌ ERROR durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_modelo_perfil():
    """Verificar el modelo PerfilUsuario"""
    print("\n🔍 VERIFICANDO MODELO PERFILUSUARIO")
    print("=" * 60)
    
    # Obtener información del modelo
    from login.models import PerfilUsuario
    
    print(f"📋 Campos del modelo PerfilUsuario:")
    for field in PerfilUsuario._meta.get_fields():
        field_type = type(field).__name__
        print(f"   - {field.name}: {field_type}")
        
        if field.name == 'telefono':
            print(f"     * Max length: {getattr(field, 'max_length', 'N/A')}")
            print(f"     * Null: {getattr(field, 'null', 'N/A')}")
            print(f"     * Blank: {getattr(field, 'blank', 'N/A')}")
    
    # Verificar algunos usuarios existentes
    print(f"\n📊 Usuarios con teléfonos actuales:")
    usuarios_con_telefono = User.objects.select_related('perfil').exclude(perfil__telefono__isnull=True).exclude(perfil__telefono__exact='')
    
    for user in usuarios_con_telefono[:5]:  # Mostrar solo los primeros 5
        try:
            telefono = user.perfil.telefono if hasattr(user, 'perfil') else 'Sin perfil'
            print(f"   - {user.username}: '{telefono}'")
        except:
            print(f"   - {user.username}: Error accediendo al perfil")

def main():
    try:
        # Verificar modelo
        verificar_modelo_perfil()
        
        # Probar creación
        resultado = test_crear_usuario_con_telefono()
        
        print(f"\n🎯 RESULTADO FINAL:")
        if resultado:
            print("✅ La funcionalidad de guardar teléfono funciona correctamente")
        else:
            print("❌ Hay problemas con el guardado del teléfono")
            
    except Exception as e:
        print(f"❌ Error en las pruebas: {e}")

if __name__ == "__main__":
    main()