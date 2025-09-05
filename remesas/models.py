from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid
from datetime import date, datetime
from django.db.models import Sum
import random

def generar_id_remesa(metodo_pago='transferencia', cantidad=0):
    """Genera un ID único para la remesa en formato REM-MM/DD-T###-HHMMSS o REM-MM/DD-E###-HHMMSS"""
    ahora = datetime.now()
    mes = f"{ahora.month:02d}"
    dia = f"{ahora.day:02d}"
    # Usar la cantidad en lugar de número aleatorio
    cantidad_str = f"{int(cantidad):03d}" if cantidad else "000"
    hora = f"{ahora.hour:02d}{ahora.minute:02d}{ahora.second:02d}"
    # T para transferencia, E para efectivo
    tipo_letra = 'T' if metodo_pago == 'transferencia' else 'E'
    return f"REM-{mes}/{dia}-{tipo_letra}{cantidad_str}-{hora}"

def generar_id_pago(tipo_pago='transferencia', cantidad=0):
    """Genera un ID único para el pago en formato PAGO-MM/DD-T###-HHMMSS o PAGO-MM/DD-E###-HHMMSS"""
    ahora = datetime.now()
    mes = f"{ahora.month:02d}"
    dia = f"{ahora.day:02d}"
    # Usar la cantidad en lugar de número aleatorio
    cantidad_str = f"{int(cantidad):03d}" if cantidad else "000"
    hora = f"{ahora.hour:02d}{ahora.minute:02d}{ahora.second:02d}"
    # T para transferencia, E para efectivo
    tipo_letra = 'T' if tipo_pago == 'transferencia' else 'E'
    return f"PAGO-{mes}/{dia}-{tipo_letra}{cantidad_str}-{hora}"

class ClienteR(models.Model):
    nombre = models.CharField(max_length=255, help_text="Nombre del cliente receptor")
    apellidos = models.CharField(max_length=255, help_text="Apellidos del cliente receptor")
    carnet_identidad = models.CharField(max_length=50, blank=True, null=True, help_text="Carnet de identidad")
    numero_cuenta = models.CharField(max_length=100, blank=True, null=True, help_text="Número de cuenta")
    correo = models.EmailField(blank=True, null=True, help_text="Correo electrónico")
    telefonos = models.CharField(max_length=255, blank=True, null=True, help_text="Teléfonos")

    def __str__(self):
        return f"{self.nombre} {self.apellidos}"


class ClienteD(models.Model):
    nombre = models.CharField(max_length=255, help_text="Nombre del cliente destinatario")
    apellidos = models.CharField(max_length=255, help_text="Apellidos del cliente destinatario")
    carnet_identidad = models.CharField(max_length=50, blank=True, null=True, help_text="Carnet de identidad")
    numero_cuenta = models.CharField(max_length=100, blank=True, null=True, help_text="Número de cuenta")
    correo = models.EmailField(blank=True, null=True, help_text="Correo electrónico")
    telefonos = models.CharField(max_length=255, blank=True, null=True, help_text="Teléfonos")

    def __str__(self):
        return f"{self.nombre} {self.apellidos}"



from django.db import models


class Moneda(models.Model):
    TIPO_MONEDA_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
    ]
    
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    valor_actual = models.DecimalField(
        max_digits=15, 
        decimal_places=6,
        verbose_name='Valor Actual',
        help_text='Valor actual de la moneda respecto al USD'
    )
    valor_comercial = models.DecimalField(
        max_digits=15, 
        decimal_places=6,
        verbose_name='Valor Comercial',
        help_text='Valor comercial de la moneda para transacciones'
    )
    tipo_moneda = models.CharField(
        max_length=20,
        choices=TIPO_MONEDA_CHOICES,
        default='transferencia',
        verbose_name='Tipo de Moneda',
        help_text='Tipo de moneda: efectivo o transferencia'
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Balance(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Usuario')
    saldo = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name='Saldo',
        help_text='Saldo disponible del usuario'
    )
    moneda = models.ForeignKey(
        Moneda, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Moneda',
        help_text='Moneda del balance'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Balance'
        verbose_name_plural = 'Balances'
        ordering = ['usuario__username']

    def __str__(self):
        moneda_codigo = self.moneda.codigo if self.moneda else 'USD'
        return f"{self.usuario.username} - {self.saldo} {moneda_codigo}"

    def agregar_saldo(self, cantidad):
        """Agrega saldo al balance del usuario"""
        self.saldo += cantidad
        self.save()

    def restar_saldo(self, cantidad):
        """Resta saldo del balance del usuario si hay suficiente"""
        if self.saldo >= cantidad:
            self.saldo -= cantidad
            self.save()
            return True
        return False

    def tiene_saldo_suficiente(self, cantidad):
        """Verifica si el usuario tiene saldo suficiente"""
        return self.saldo >= cantidad


class TipodePago(models.Model):

    nombre = models.CharField(max_length=255, help_text="Nombre del destinatario")

    def __str__(self):
        return self.nombre


class Pago(models.Model):
    TIPO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('efectivo', 'Efectivo'),
    ]
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
    ]
    
    pago_id = models.CharField(max_length=50, unique=True, blank=True, help_text="ID único del pago")
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, help_text="Tipo de pago")
    tipo_moneda = models.ForeignKey(Moneda, on_delete=models.SET_NULL, blank=True, null=True, help_text="Tipo de moneda")
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, help_text="Cantidad a pagar")
    destinatario = models.CharField(max_length=255, help_text="Nombre del destinatario")
    telefono = models.CharField(max_length=20, blank=True, null=True, help_text="Teléfono del destinatario")
    direccion = models.TextField(blank=True, null=True, help_text="Dirección del destinatario")
    carnet_identidad = models.CharField(max_length=50, blank=True, null=True, help_text="Carnet de identidad del destinatario")
    fecha_creacion = models.DateTimeField(auto_now_add=True, help_text="Fecha de creación del pago")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, help_text="Usuario que realizó el pago")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', help_text="Estado del pago")
    
    # Campos específicos para transferencia
    tarjeta = models.CharField(max_length=19, blank=True, null=True, help_text="Número de tarjeta (para transferencias)")
    comprobante_pago = models.ImageField(upload_to='comprobantes_pagos/', blank=True, null=True, help_text="Comprobante de pago")
    
    # Campos opcionales
    observaciones = models.TextField(blank=True, null=True, help_text="Observaciones del pago")
    
    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ['-fecha_creacion']
    
    def save(self, *args, **kwargs):
        # Generar ID automáticamente si no existe
        if not self.pago_id:
            cantidad = float(self.cantidad) if self.cantidad else 0
            self.pago_id = generar_id_pago(self.tipo_pago, cantidad)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.pago_id} - {self.get_tipo_pago_display()} - {self.destinatario} - {self.cantidad}"
    
    def get_estado_badge(self):
        """Retorna la clase de Bootstrap para el badge según el estado"""
        return {
            'pendiente': 'warning',
            'confirmado': 'success',
            'cancelado': 'danger',
        }.get(self.estado, 'secondary')

    def get_estado_display(self):
        """Retorna el texto para mostrar del estado"""
        return {
            'pendiente': 'Pendiente',
            'confirmado': 'Confirmado',
            'cancelado': 'Cancelado',
        }.get(self.estado, 'Desconocido')

    def puede_confirmar(self):
        """Verifica si el pago puede pasar de pendiente a confirmado"""
        return self.estado == 'pendiente'
    
    def puede_cancelar(self):
        """Verifica si el pago puede ser cancelado (solo desde pendiente)"""
        return self.estado == 'pendiente'
    
    def confirmar(self):
        """Confirma el pago y descuenta del balance del usuario"""
        if self.puede_confirmar():
            self.estado = 'confirmado'
            # Solo descontar del balance cuando se confirma
            success = self.descontar_del_balance_usuario()
            if success:
                self.save()
                return True
            else:
                # Si falla el descuento, no confirmar
                self.estado = 'pendiente'
                return False
        return False
    
    def cancelar(self):
        """Cancela el pago"""
        if self.puede_cancelar():
            self.estado = 'cancelado'
            self.save()
            return True
        return False
    
    def calcular_monto_en_usd(self):
        """Calcula el monto del pago convertido a USD"""
        from decimal import Decimal
        
        if not self.cantidad or not self.tipo_moneda:
            return Decimal('0')
        
        try:
            if self.tipo_moneda.codigo == 'USD':
                # Si ya está en USD, no necesita conversión
                return self.cantidad
            else:
                # Convertir dividiendo por el valor actual de la moneda
                # Ejemplo: 100,000 COP ÷ 4,250 (COP por USD) = 23.53 USD
                monto_usd = self.cantidad / self.tipo_moneda.valor_actual
                return monto_usd
        except Exception:
            return Decimal('0')
    
    def descontar_del_balance_usuario(self):
        """DEPRECATED: El balance ahora se calcula dinámicamente"""
        # Esta funcionalidad está deshabilitada porque el balance
        # se calcula dinámicamente en base a las transacciones
        return True
    
    def reembolsar_al_balance_usuario(self):
        """DEPRECATED: El balance ahora se calcula dinámicamente"""
        # Esta funcionalidad está deshabilitada porque el balance
        # se calcula dinámicamente en base a las transacciones
        return True


class Remesa(models.Model):
    TIPO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('efectivo', 'Efectivo'),
    ]
    
    remesa_id = models.CharField(max_length=50, unique=True, blank=True, help_text="ID único de la remesa")
    fecha = models.DateTimeField(auto_now_add=True, help_text="Fecha de la remesa")
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, blank=True, null=True, help_text="Tipo de pago")
    moneda = models.ForeignKey(Moneda, on_delete=models.SET_NULL, blank=True, null=True, help_text="Moneda usada en la remesa")
    importe = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Importe")
    receptor_nombre = models.CharField(max_length=255, blank=True, null=True, help_text="Nombre del remitente")
    observaciones = models.TextField(blank=True, null=True, help_text="Observaciones")
    comprobante = models.ImageField(upload_to='comprobantes/', blank=True, null=True, help_text="Foto del comprobante")
    gestor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, help_text="Usuario gestor que creó la remesa")

    estado = models.CharField(max_length=50, choices=[
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ], default='pendiente')

    def save(self, *args, **kwargs):
        # Generar ID automáticamente si no existe
        if not self.remesa_id:
            # Usar el tipo_pago directamente
            metodo_pago_tipo = self.tipo_pago if self.tipo_pago else 'transferencia'
            
            # Usar el importe como cantidad
            cantidad = float(self.importe) if self.importe else 0
            self.remesa_id = generar_id_remesa(metodo_pago_tipo, cantidad)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Remesa {self.remesa_id}"

    def get_estado_badge(self):
        """Retorna la clase de Bootstrap para el badge según el estado"""
        return {
            'pendiente': 'warning',
            'confirmada': 'info',
            'completada': 'success',
            'procesada': 'success',
            'cancelada': 'danger',
            'error': 'danger'
        }.get(self.estado, 'secondary')

    def get_estado_display(self):
        """Retorna el texto para mostrar del estado"""
        return {
            'pendiente': 'Pendiente',
            'confirmada': 'Confirmada',
            'completada': 'Completada',
            'cancelada': 'Cancelada',
            'procesada': 'Procesada',
            'error': 'Error'
        }.get(self.estado, 'Desconocido')

    def puede_confirmar(self):
        """Verifica si la remesa puede pasar de pendiente a confirmada"""
        return self.estado == 'pendiente'
    
    def puede_completar(self):
        """Verifica si la remesa puede pasar de confirmada a completada"""
        return self.estado == 'confirmada'
    
    def puede_cancelar(self):
        """Verifica si la remesa puede ser cancelada (solo desde pendiente)"""
        return self.estado == 'pendiente'
    
    def confirmar(self):
        """Cambia el estado de pendiente a confirmada y actualiza el balance"""
        if self.puede_confirmar():
            self.estado = 'confirmada'
            self.save()  # Los signals se encargarán de actualizar el balance
            return True
        return False
    
    def completar(self):
        """Cambia el estado de confirmada a completada"""
        if self.puede_completar():
            self.estado = 'completada'
            self.save()
            return True
        return False
    
    def cancelar(self):
        """Cambia el estado a cancelada (desde pendiente o confirmada)"""
        if self.puede_cancelar():
            self.estado = 'cancelada'
            self.save()
            return True
        return False

    def calcular_monto_en_usd(self):
        """Calcula el monto de la remesa convertido a USD"""
        from decimal import Decimal
        
        if not self.importe or not self.moneda:
            return Decimal('0')
        
        try:
            if self.moneda.codigo == 'USD':
                # Si ya está en USD, no necesita conversión
                return self.importe
            else:
                # Convertir dividiendo por el valor actual de la moneda
                # Ejemplo: 100,000 COP ÷ 4,250 (COP por USD) = 23.53 USD
                monto_usd = self.importe / self.moneda.valor_actual
                return monto_usd
        except Exception:
            return Decimal('0')

    def actualizar_balance_usuario(self):
        """DEPRECATED: El balance ahora se calcula dinámicamente"""
        # Esta funcionalidad está deshabilitada porque el balance
        # se calcula dinámicamente en base a las transacciones
        return True


class RegistroRemesas(models.Model):
    TIPO_REGISTRO = [
        ('procesada', 'Remesa Procesada'),
        ('cancelada', 'Remesa Cancelada'),
        ('satisfactoria', 'Remesa Satisfactoria'),
        ('error', 'Remesa con Error')
    ]

    remesa = models.ForeignKey(Remesa, on_delete=models.CASCADE, related_name='registros')
    tipo = models.CharField(max_length=20, choices=TIPO_REGISTRO)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField(blank=True, null=True)
    usuario_registro = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='registros_remesas'
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    def get_tipo_badge(self):
        """Retorna la clase de Bootstrap para el badge según el tipo"""
        return {
            'procesada': 'primary',
            'cancelada': 'danger',
            'satisfactoria': 'success',
            'error': 'warning'
        }.get(self.tipo, 'secondary')

    class Meta:
        verbose_name = "Registro de Remesa"
        verbose_name_plural = "Registros de Remesas"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.remesa.remesa_id} ({self.fecha_registro})"


# Signals para actualizar el balance automáticamente
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

@receiver(pre_save, sender=Remesa)
def guardar_estado_anterior_remesa(sender, instance, **kwargs):
    """
    Signal que se ejecuta antes de guardar una remesa para almacenar el estado anterior.
    """
    if instance.pk:
        try:
            instance._estado_anterior = Remesa.objects.get(pk=instance.pk).estado
        except Remesa.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None

@receiver(post_save, sender=Remesa)
def invalidar_cache_balance_remesa(sender, instance, **kwargs):
    """
    Invalidar cache del balance cuando cambia una remesa
    """
    if instance.gestor:
        from .context_processors import invalidate_user_balance_cache
        invalidate_user_balance_cache(instance.gestor.id)

@receiver(post_save, sender=Pago)
def invalidar_cache_balance_pago(sender, instance, **kwargs):
    """
    Invalidar cache del balance cuando cambia un pago
    """
    if instance.usuario:
        from .context_processors import invalidate_user_balance_cache
        invalidate_user_balance_cache(instance.usuario.id)

@receiver(post_delete, sender=Remesa)
def invalidar_cache_balance_remesa_eliminada(sender, instance, **kwargs):
    """
    Invalidar cache del balance cuando se elimina una remesa
    """
    if instance.gestor:
        from .context_processors import invalidate_user_balance_cache
        invalidate_user_balance_cache(instance.gestor.id)

@receiver(post_delete, sender=Pago)
def invalidar_cache_balance_pago_eliminado(sender, instance, **kwargs):
    """
    Invalidar cache del balance cuando se elimina un pago
    """
    if instance.usuario:
        from .context_processors import invalidate_user_balance_cache
        invalidate_user_balance_cache(instance.usuario.id)
