from django import template

register = template.Library()

@register.filter
def getitem(dictionary, key):
    """
    Filtro para obtener un item de un diccionario usando una key.
    Uso: {{ diccionario|getitem:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """
    Multiplica un valor por otro.
    Uso: {{ valor|multiply:2 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def format_currency(value, currency_code=""):
    """
    Formatea un valor como moneda.
    Uso: {{ valor|format_currency:"USD" }}
    """
    try:
        value = float(value)
        if currency_code:
            return f"{value:,.6f} {currency_code}"
        return f"{value:,.6f}"
    except (ValueError, TypeError):
        return "0.000000"

@register.filter
def add_class(field, css_class):
    """
    Añade una clase CSS a un campo de formulario.
    Uso: {{ field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={"class": css_class})
