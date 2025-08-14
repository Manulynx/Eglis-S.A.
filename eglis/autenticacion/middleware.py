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