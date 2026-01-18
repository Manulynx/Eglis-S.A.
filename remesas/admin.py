from django.contrib import admin
from .models import Remesa, ClienteR, ClienteD, Moneda, TipodePago, RegistroRemesas, Balance, PagoRemesa

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

@admin.register(PagoRemesa)
class PagoRemesaAdmin(admin.ModelAdmin):
    list_display = ['pago_id', 'remesa', 'tipo_pago', 'destinatario', 'cantidad', 'tipo_moneda', 'estado', 'fecha_creacion']
    search_fields = ['pago_id', 'destinatario', 'remesa__remesa_id']
    list_filter = ['estado', 'tipo_pago', 'tipo_moneda', 'fecha_creacion']
    readonly_fields = ['pago_id', 'fecha_creacion', 'valor_moneda_historico', 'monto_usd_historico', 'editado', 'fecha_edicion', 'usuario_editor']
    
    fieldsets = (
        ('Información de la Remesa', {
            'fields': ('remesa',)
        }),
        ('Información del Pago', {
            'fields': ('pago_id', 'tipo_pago', 'tipo_moneda', 'cantidad', 'estado')
        }),
        ('Información del Destinatario', {
            'fields': ('destinatario', 'telefono', 'direccion', 'carnet_identidad')
        }),
        ('Detalles de Transferencia', {
            'fields': ('tarjeta', 'comprobante_pago'),
            'classes': ('collapse',),
        }),
        ('Valores Históricos', {
            'fields': ('valor_moneda_historico', 'monto_usd_historico'),
            'classes': ('collapse',),
        }),
        ('Control de Ediciones', {
            'fields': ('editado', 'fecha_edicion', 'usuario_editor'),
            'classes': ('collapse',),
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'fecha_creacion', 'usuario')
        }),
    )
