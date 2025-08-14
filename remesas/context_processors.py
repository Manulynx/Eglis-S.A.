from decimal import Decimal

def user_balance(request):
    """Context processor para mostrar el balance del usuario en todas las plantillas"""
    context = {
        'user_balance': None,
        'user_balance_moneda': 'USD'
    }
    
    if request.user.is_authenticated:
        try:
            # Usar el balance del PerfilUsuario en lugar del modelo Balance
            perfil = request.user.perfil
            context['user_balance'] = perfil.balance
            context['user_balance_moneda'] = 'USD'  # El balance siempre está en USD
        except Exception:
            context['user_balance'] = Decimal('0.00')
            context['user_balance_moneda'] = 'USD'
    
    return context
