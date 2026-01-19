from django.contrib import admin
from .models import ConfiguracionNotificacion, DestinatarioNotificacion, LogNotificacion, NotificacionInterna


@admin.register(ConfiguracionNotificacion)
class ConfiguracionNotificacionAdmin(admin.ModelAdmin):
    list_display = [
        'activo', 
        'notificar_remesas', 
        'notificar_pagos', 
        'notificar_cambios_estado',
        'fecha_actualizacion'
    ]
    fieldsets = (
        ('Configuración CallMeBot (GRATIS y FÁCIL)', {
            'fields': ('callmebot_api_key',)
        }),
        ('Configuración Twilio (Alternativo)', {
            'fields': ('twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number'),
            'classes': ('collapse',)
        }),
        ('Configuración WhatsApp Business API', {
            'fields': ('whatsapp_business_token', 'whatsapp_business_phone_id'),
            'classes': ('collapse',)
        }),
        ('Configuración General', {
            'fields': ('activo', 'notificar_remesas', 'notificar_pagos', 'notificar_cambios_estado')
        }),
    )


@admin.register(DestinatarioNotificacion)
class DestinatarioNotificacionAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 
        'telefono', 
        'activo', 
        'tiene_api_key',
        'recibir_remesas', 
        'recibir_pagos',
        'fecha_creacion'
    ]
    list_filter = ['activo', 'recibir_remesas', 'recibir_pagos']
    search_fields = ['nombre', 'telefono']
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'telefono', 'activo')
        }),
        ('Configuración CallMeBot', {
            'fields': ('callmebot_api_key',),
            'description': 'API Key personal obtenida enviando "I allow callmebot to send me messages" al +34 644 84 44 84'
        }),
        ('Tipos de Notificaciones', {
            'fields': ('recibir_remesas', 'recibir_pagos', 'recibir_cambios_estado')
        }),
    )
    
    def tiene_api_key(self, obj):
        return bool(obj.callmebot_api_key)
    tiene_api_key.boolean = True
    tiene_api_key.short_description = 'API Key'


@admin.register(LogNotificacion)
class LogNotificacionAdmin(admin.ModelAdmin):
    list_display = [
        'tipo', 
        'destinatario', 
        'estado', 
        'fecha_creacion', 
        'fecha_envio'
    ]
    list_filter = ['tipo', 'estado', 'fecha_creacion']
    search_fields = ['destinatario__nombre', 'mensaje']
    readonly_fields = ['fecha_creacion', 'fecha_envio']
    
    def has_add_permission(self, request):
        return False  # No permitir crear logs manualmente


@admin.register(NotificacionInterna)
class NotificacionInternaAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'message', 'level', 'created_at', 'read_at']
    list_filter = ['level', 'created_at', 'read_at']
    search_fields = ['recipient__username', 'message', 'verb', 'link']
    readonly_fields = ['created_at']
