from django import forms
from .models import ConfiguracionNotificacion, DestinatarioNotificacion


class ConfiguracionForm(forms.ModelForm):
    """Formulario para configurar las notificaciones"""
    
    callmebot_api_key = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="API Key obtenida de CallMeBot"
    )
    
    twilio_auth_token = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Token de autenticación de Twilio"
    )
    
    whatsapp_business_token = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        help_text="Token de acceso de WhatsApp Business API"
    )
    
    class Meta:
        model = ConfiguracionNotificacion
        fields = [
            'callmebot_api_key',
            'twilio_account_sid',
            'twilio_auth_token', 
            'twilio_phone_number',
            'whatsapp_business_token',
            'whatsapp_business_phone_id',
            'activo',
            'notificar_remesas',
            'notificar_pagos',
            'notificar_cambios_estado'
        ]
        widgets = {
            'twilio_account_sid': forms.TextInput(attrs={'class': 'form-control'}),
            'twilio_phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'whatsapp_business_phone_id': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notificar_remesas': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notificar_pagos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notificar_cambios_estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DestinatarioForm(forms.ModelForm):
    """Formulario para agregar destinatarios de notificaciones"""
    
    class Meta:
        model = DestinatarioNotificacion
        fields = [
            'nombre',
            'telefono',
            'activo',
            'recibir_remesa_nueva',
            'recibir_remesa_confirmada',
            'recibir_remesa_completada',
            'recibir_remesa_cancelada',
            'recibir_remesa_editada',
            'recibir_remesa_eliminada',
            'recibir_pago_nuevo',
            'recibir_pago_confirmado',
            'recibir_pago_cancelado',
            'recibir_pago_editado',
            'recibir_pago_eliminado',
            'monedas',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_nueva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_confirmada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_completada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_cancelada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_editada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_remesa_eliminada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_pago_nuevo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_pago_confirmado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_pago_cancelado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_pago_editado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recibir_pago_eliminado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monedas': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
