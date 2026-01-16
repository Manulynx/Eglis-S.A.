
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

# Vistas de redirección para integrar con el sistema de login
def login_redirect(request):
    return redirect('login:login')

@login_required
def admin_usuarios_redirect(request):
    return redirect('login:administrar_usuarios')

@login_required
def home(request):
    from remesas.models import Moneda
    
    # Obtener monedas activas
    monedas = Moneda.objects.filter(activa=True)
    
    # Preparar monedas con sus valores específicos para el usuario logueado
    monedas_con_valores = []
    for moneda in monedas:
        # Obtener el valor específico para este usuario
        valor_para_usuario = moneda.get_valor_para_usuario(request.user)
        
        # Agregar la moneda con su valor específico
        monedas_con_valores.append({
            'moneda': moneda,
            'valor_usuario': valor_para_usuario
        })
    
    return render(request, 'eglisapp/home.html', {'monedas_con_valores': monedas_con_valores})
