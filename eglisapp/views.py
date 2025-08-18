
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
    # Excluir USD y filtrar solo monedas activas
    monedas = Moneda.objects.filter(activa=True)
    return render(request, 'eglisapp/home.html', {'monedas': monedas})
