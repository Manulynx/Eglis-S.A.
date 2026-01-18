from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import logout


class AuthenticationRequiredMiddleware:
    """
    Middleware que requiere autenticación para todas las páginas,
    excepto para las URLs de login y páginas públicas especificadas.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs que no requieren autenticación
        self.public_urls = [
            '/login/',
            '/login/login/',
            '/admin/',  # Para el admin de Django
        ]
    
    def __call__(self, request):
        # Obtener la URL actual
        current_url = request.path
        
        # Verificar si la URL actual está en la lista de URLs públicas
        is_public_url = any(current_url.startswith(url) for url in self.public_urls)
        
        # Si no es una URL pública y el usuario no está autenticado
        if not is_public_url and not request.user.is_authenticated:
            # Redirigir al login
            return redirect('login:login')
        
        # Si el usuario está autenticado pero no está activo, cerrar sesión
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)
            return redirect('login:login')
        
        response = self.get_response(request)
        return response


class DomicilioAccessMiddleware:
    """
    Middleware que restringe el acceso de usuarios con rol 'domicilio'
    solo a la página principal y páginas de perfil.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs permitidas para usuarios domicilio (además de la home)
        self.allowed_urls = [
            '/login/',
            '/admin/',
            '/logout/',
            '/perfil/',
            '/cambiar-password/',
            '/',  # Home page
        ]
    
    def __call__(self, request):
        # Solo aplicar restricciones si el usuario está autenticado
        if request.user.is_authenticated and hasattr(request.user, 'perfil'):
            # Verificar si el usuario es tipo domicilio
            if request.user.perfil.tipo_usuario == 'domicilio':
                current_url = request.path
                
                # Verificar si la URL actual está permitida
                is_allowed = any(current_url.startswith(url) for url in self.allowed_urls)
                
                # Si no está permitida, redirigir a la home
                if not is_allowed:
                    return redirect('/')
        
        response = self.get_response(request)
        return response