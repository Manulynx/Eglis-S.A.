from django.contrib import admin
from .models import Remesa, ClienteR, ClienteD, Moneda, TipodePago, RegistroRemesas, Balance

@admin.register(ClienteR)
class ClienteRAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'apellidos', 'correo', 'numero_cuenta']
    search_fields = ['nombre', 'apellidos', 'correo']

@admin.register(ClienteD)
class ClienteDAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'apellidos', 'correo', 'numero_cuenta']
    search_fields = ['nombre', 'apellidos', 'correo']

@admin.register(Remesa)
class RemesaAdmin(admin.ModelAdmin):
    list_display = ['remesa_id', 'fecha', 'tipo_pago', 'receptor_nombre', 'importe', 'moneda', 'estado']
    search_fields = ['remesa_id', 'receptor_nombre']
    list_filter = ['estado', 'tipo_pago', 'fecha', 'moneda']

@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'valor_actual']

@admin.register(TipodePago)
class TipodePagoAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre']

@admin.register(RegistroRemesas)
class RegistroRemesasAdmin(admin.ModelAdmin):
    list_display = ['remesa', 'tipo', 'fecha_registro', 'usuario_registro', 'monto']
    list_filter = ['tipo', 'fecha_registro']
    search_fields = ['remesa__remesa_id', 'usuario_registro__username']

@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'saldo', 'moneda', 'fecha_actualizacion']
    list_filter = ['moneda', 'fecha_creacion']
    search_fields = ['usuario__username', 'usuario__email']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
