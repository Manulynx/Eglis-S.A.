from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ConfiguracionNotificacion(models.Model):
    """Configuración para las notificaciones de WhatsApp"""
    
    # Configuración de Twilio (recomendado)
    twilio_account_sid = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Account SID de Twilio"
    )
    twilio_auth_token = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Auth Token de Twilio"
    )
    twilio_phone_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Número de WhatsApp Business de Twilio (formato: +1234567890)"
    )
    
    # Configuración de WhatsApp Business API (alternativo)
    whatsapp_business_token = models.TextField(
        blank=True, 
        null=True,
        help_text="Token de acceso de WhatsApp Business API"
    )
    whatsapp_business_phone_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="ID del número de teléfono de WhatsApp Business"
    )
    
    # Configuración de CallMeBot (GRATIS y SIMPLE)
    callmebot_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="API Key de CallMeBot (obtenida enviando mensaje a +34 644 84 44 84)"
    )
    
    # Configuración general
    activo = models.BooleanField(
        default=True,
        help_text="Activar/desactivar notificaciones"
    )
    
    # Tipos de notificaciones a enviar
    notificar_remesas = models.BooleanField(
        default=True,
        help_text="Enviar notificaciones para nuevas remesas"
    )
    notificar_pagos = models.BooleanField(
        default=True,
        help_text="Enviar notificaciones para nuevos pagos"
    )
    notificar_cambios_estado = models.BooleanField(
        default=True,
        help_text="Enviar notificaciones para cambios de estado"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Notificación"
        verbose_name_plural = "Configuraciones de Notificación"
    
    def __str__(self):
        return f"Configuración WhatsApp - {'Activo' if self.activo else 'Inactivo'}"
    
    @classmethod
    def get_config(cls):
        """Obtiene la configuración activa o crea una nueva"""
        config, created = cls.objects.get_or_create(pk=1)
        return config


class DestinatarioNotificacion(models.Model):
    """Destinatarios que recibirán las notificaciones"""
    
    nombre = models.CharField(max_length=255, help_text="Nombre del destinatario")
    telefono = models.CharField(
        max_length=50, 
        help_text="Número de WhatsApp (formato: +1234567890)"
    )
    activo = models.BooleanField(default=True)
    
    # API Key personal de CallMeBot para este destinatario
    callmebot_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="API Key personal de CallMeBot para este número específico"
    )
    
    # Tipos de notificaciones que recibirá
    recibir_remesas = models.BooleanField(
        default=True,
        help_text="Recibir notificaciones de remesas"
    )
    recibir_pagos = models.BooleanField(
        default=True,
        help_text="Recibir notificaciones de pagos"
    )
    recibir_cambios_estado = models.BooleanField(
        default=True,
        help_text="Recibir notificaciones de cambios de estado"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Destinatario de Notificación"
        verbose_name_plural = "Destinatarios de Notificación"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} - {self.telefono}"


class LogNotificacion(models.Model):
    """Registro de notificaciones enviadas"""
    
    TIPO_CHOICES = [
        ('remesa_nueva', 'Nueva Remesa'),
        ('remesa_estado', 'Cambio Estado Remesa'),
        ('pago_nuevo', 'Nuevo Pago'),
        ('pago_estado', 'Cambio Estado Pago'),
    ]
    
    ESTADO_CHOICES = [
        ('enviado', 'Enviado'),
        ('fallido', 'Fallido'),
        ('pendiente', 'Pendiente'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    destinatario = models.ForeignKey(
        DestinatarioNotificacion, 
        on_delete=models.CASCADE
    )
    mensaje = models.TextField(help_text="Contenido del mensaje enviado")
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_CHOICES, 
        default='pendiente'
    )
    respuesta_api = models.TextField(
        blank=True, 
        null=True,
        help_text="Respuesta de la API de WhatsApp"
    )
    error_mensaje = models.TextField(
        blank=True, 
        null=True,
        help_text="Mensaje de error si falló el envío"
    )
    
    # Referencia al objeto relacionado
    remesa_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="ID de la remesa relacionada"
    )
    pago_id = models.IntegerField(
        blank=True, 
        null=True,
        help_text="ID del pago relacionado"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Log de Notificación"
        verbose_name_plural = "Logs de Notificación"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.destinatario.nombre} - {self.estado}"
