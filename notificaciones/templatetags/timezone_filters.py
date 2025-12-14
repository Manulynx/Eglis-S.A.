from django import template
from django.utils import timezone
from django.utils.dateformat import format

register = template.Library()

@register.filter
def fecha_local(fecha, formato='d/m/Y H:i'):
    """
    Convierte una fecha UTC a la zona horaria local configurada en Django
    """
    if not fecha:
        return ''
    
    # Si la fecha no tiene zona horaria, asumimos que es UTC
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.utc)
    
    # Convertir a la zona horaria local configurada en settings
    zona_local = timezone.get_current_timezone()
    fecha_local = fecha.astimezone(zona_local)
    
    return format(fecha_local, formato)

@register.filter
def fecha_local_corta(fecha):
    """
    Formato corto para fechas (dd/mm/yyyy)
    """
    return fecha_local(fecha, 'd/m/Y')

@register.filter
def fecha_local_completa(fecha):
    """
    Formato completo para fechas (dd/mm/yyyy HH:MM)
    """
    return fecha_local(fecha, 'd/m/Y H:i')
