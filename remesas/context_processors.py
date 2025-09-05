from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
import hashlib

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
                # Verificar si el superuser tiene perfil
                if hasattr(request.user, 'perfil'):
                    # Usar el balance real del perfil
                    perfil = request.user.perfil
                    cache_key = f'user_balance_{request.user.id}'
                    
                    cached_balance = cache.get(cache_key)
                    
                    if cached_balance is not None:
                        context['user_balance'] = cached_balance['balance']
                        context['user_tipo'] = 'admin'
                    else:
                        balance_calculado = perfil.calcular_balance_real()
                        
                        if abs(perfil.balance - balance_calculado) > Decimal('0.01'):
                            perfil.actualizar_balance()
                        
                        cache.set(cache_key, {
                            'balance': balance_calculado,
                            'user_tipo': 'admin',
                            'timestamp': timezone.now()
                        }, 30)
                        
                        context['user_balance'] = balance_calculado
                    
                    context['user_tipo'] = 'admin'
                else:
                    # Superuser sin perfil
                    context['user_balance'] = Decimal('0.00')
                    context['user_tipo'] = 'admin'
            else:
                # Verificar si el usuario tiene perfil
                if not hasattr(request.user, 'perfil'):
                    context['user_balance'] = Decimal('0.00')
                    context['user_tipo'] = 'gestor'
                else:
                    # Generar clave de cache única para el usuario
                    cache_key = f'user_balance_{request.user.id}'
                    
                    # Intentar obtener el balance del cache (válido por 30 segundos)
                    cached_balance = cache.get(cache_key)
                    
                    if cached_balance is not None:
                        # Usar balance desde cache
                        context['user_balance'] = cached_balance['balance']
                        context['user_tipo'] = cached_balance['user_tipo']
                    else:
                        # Calcular balance y guardarlo en cache
                        perfil = request.user.perfil
                        balance_calculado = perfil.calcular_balance_real()
                        user_tipo = perfil.tipo_usuario
                        
                        # Actualizar balance almacenado si difiere significativamente del calculado
                        if abs(perfil.balance - balance_calculado) > Decimal('0.01'):
                            perfil.actualizar_balance()
                        
                        # Guardar en cache por 30 segundos
                        cache.set(cache_key, {
                            'balance': balance_calculado,
                            'user_tipo': user_tipo,
                            'timestamp': timezone.now()
                        }, 30)
                        
                        context['user_balance'] = balance_calculado
                        context['user_tipo'] = user_tipo
            
            context['user_balance_moneda'] = 'USD'  # El balance siempre está en USD
            
        except Exception as e:
            # Log del error para debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculando balance para usuario {request.user.username}: {e}")
            
            context['user_balance'] = Decimal('0.00')
            context['user_balance_moneda'] = 'USD'
            context['user_tipo'] = 'gestor'  # Default a gestor si hay error
    
    return context

def invalidate_user_balance_cache(user_id):
    """Función helper para invalidar el cache del balance de un usuario específico"""
    cache_key = f'user_balance_{user_id}'
    cache.delete(cache_key)
