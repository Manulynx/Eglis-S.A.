from decimal import Decimal

def user_balance(request):
    """Context processor para mostrar el balance del usuario en todas las plantillas"""
    context = {
        'user_balance': None,
        'user_balance_moneda': 'USD',
        'user_tipo': None
    }
    
    if request.user.is_authenticated:
        try:
            # Determinar el tipo de usuario
            if request.user.is_superuser:
                context['user_tipo'] = 'admin'
                # Los administradores pueden no tener perfil, usar balance 0
                context['user_balance'] = Decimal('0.00')
            else:
                # Usar el balance calculado dinámicamente
                perfil = request.user.perfil
                balance_calculado = perfil.calcular_balance_real()
                
                # Actualizar balance almacenado si difiere del calculado
                if perfil.balance != balance_calculado:
                    perfil.actualizar_balance()
                
                context['user_balance'] = balance_calculado
                context['user_tipo'] = perfil.tipo_usuario
            
            context['user_balance_moneda'] = 'USD'  # El balance siempre está en USD
            
        except Exception:
            context['user_balance'] = Decimal('0.00')
            context['user_balance_moneda'] = 'USD'
            context['user_tipo'] = 'gestor'  # Default a gestor si hay error
    
    return context
