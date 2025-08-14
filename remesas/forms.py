from django import forms
from .models import Pago, Moneda

class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = [
            'tipo_pago',
            'tipo_moneda', 
            'cantidad',
            'destinatario',
            'telefono',
            'direccion',
            'carnet_identidad',
            'tarjeta',
            'comprobante_pago',
            'observaciones'
        ]
        widgets = {
            'tipo_pago': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'tipo_moneda': forms.Select(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'required': True
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True
            }),
            'destinatario': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'placeholder': 'Nombre completo del destinatario',
                'required': True
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'placeholder': '+1234567890',
                'pattern': r'[0-9\-\+\s\(\)]+',
                'title': 'Ingrese un número de teléfono válido'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'rows': 3,
                'placeholder': 'Dirección completa del destinatario'
            }),
            'carnet_identidad': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'placeholder': 'Número de cédula o documento de identidad'
            }),
            'tarjeta': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'placeholder': '1234-5678-9012-3456',
                'maxlength': '19'
            }),
            'comprobante_pago': forms.ClearableFileInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'accept': 'image/*'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            })
        }
        labels = {
            'tipo_pago': 'Tipo de Pago',
            'tipo_moneda': 'Moneda',
            'cantidad': 'Cantidad a Pagar',
            'destinatario': 'Destinatario',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
            'carnet_identidad': 'Cédula/Documento',
            'tarjeta': 'Número de Tarjeta',
            'comprobante_pago': 'Comprobante de Pago',
            'observaciones': 'Observaciones'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo monedas activas
        self.fields['tipo_moneda'].queryset = Moneda.objects.filter(activa=True)
        self.fields['tipo_moneda'].empty_label = "Seleccione una moneda"
        
        # Solo hacer obligatorio el tipo de pago inicialmente
        self.fields['tipo_pago'].required = True
        
        # Los demás campos serán validados condicionalmente en clean()
        self.fields['tipo_moneda'].required = False
        self.fields['cantidad'].required = False
        self.fields['destinatario'].required = False
        self.fields['telefono'].required = False
        self.fields['direccion'].required = False
        self.fields['tarjeta'].required = False

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a cero.")
        return cantidad

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono and len(telefono.strip()) > 0:
            # Limpiar el teléfono de caracteres especiales para validación básica
            telefono_limpio = ''.join(filter(str.isdigit, telefono))
            if len(telefono_limpio) < 7:
                raise forms.ValidationError("El teléfono debe tener al menos 7 dígitos.")
        return telefono

    def clean_tarjeta(self):
        tarjeta = self.cleaned_data.get('tarjeta')
        tipo_pago = self.cleaned_data.get('tipo_pago')
        
        if tipo_pago == 'transferencia' and tarjeta:
            # Remover guiones y espacios para validación
            tarjeta_limpia = ''.join(filter(str.isdigit, tarjeta))
            if len(tarjeta_limpia) != 16:
                raise forms.ValidationError("El número de tarjeta debe tener exactamente 16 dígitos.")
            
            # Reformatear con guiones
            tarjeta_formateada = '-'.join([tarjeta_limpia[i:i+4] for i in range(0, 16, 4)])
            return tarjeta_formateada
        
        return tarjeta

    def clean(self):
        cleaned_data = super().clean()
        tipo_pago = cleaned_data.get('tipo_pago')
        
        # Validaciones comunes a ambos tipos de pago
        if not cleaned_data.get('tipo_moneda'):
            self.add_error('tipo_moneda', 'La moneda es obligatoria.')
        
        if not cleaned_data.get('cantidad'):
            self.add_error('cantidad', 'La cantidad es obligatoria.')
        
        if not cleaned_data.get('destinatario'):
            self.add_error('destinatario', 'El destinatario es obligatorio.')
        
        # Validaciones específicas según el tipo de pago
        if tipo_pago == 'transferencia':
            tarjeta = cleaned_data.get('tarjeta')
            if not tarjeta:
                self.add_error('tarjeta', 'El número de tarjeta es obligatorio para transferencias.')
        elif tipo_pago == 'efectivo':
            telefono = cleaned_data.get('telefono')
            direccion = cleaned_data.get('direccion')
            
            if not telefono:
                self.add_error('telefono', 'El teléfono es obligatorio para pagos en efectivo.')
            if not direccion:
                self.add_error('direccion', 'La dirección es obligatoria para pagos en efectivo.')
        
        return cleaned_data
