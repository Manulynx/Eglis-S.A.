from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid
from datetime import date, datetime
from django.db.models import Sum
import random

class TipoValorMoneda(models.Model):
    """
    Modelo para definir diferentes tipos de valores para las monedas
    """
    nombre = models.CharField(max_length=50, unique=True, verbose_name='Nombre del Tipo de Valor')
    descripcion = models.TextField(blank=True, null=True, verbose_name='Descripción')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden de Visualización')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tipos_valor_creados')
    
    class Meta:
        verbose_name = "Tipo de Valor de Moneda"
        verbose_name_plural = "Tipos de Valores de Monedas"
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre
    
    @classmethod
    def get_tipo_por_defecto(cls):
        """Retorna el primer tipo de valor creado (por defecto)"""
        return cls.objects.filter(activo=True).first()


class ValorMoneda(models.Model):
    """
    Modelo para almacenar los diferentes valores de cada moneda según el tipo
    """
    moneda = models.ForeignKey('Moneda', on_delete=models.CASCADE, related_name='valores')
    tipo_valor = models.ForeignKey(TipoValorMoneda, on_delete=models.CASCADE, related_name='valores_moneda')
    valor = models.DecimalField(
        max_digits=15, 
        decimal_places=6,
        default=0,
        verbose_name='Valor',
        help_text='Valor de la moneda respecto al USD para este tipo'
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='valores_actualizados')
    
    class Meta:
        verbose_name = "Valor de Moneda"
        verbose_name_plural = "Valores de Monedas"
        unique_together = ['moneda', 'tipo_valor']
        ordering = ['moneda__codigo', 'tipo_valor__orden']
    
    def __str__(self):
        return f"{self.moneda.codigo} - {self.tipo_valor.nombre}: {self.valor}"

def generar_id_remesa(metodo_pago='transferencia', cantidad=0, fecha=None):
    """Genera un ID único para la remesa en formato REM-MM/DD-T###-HHMMSS o REM-MM/DD-E###-HHMMSS
    
    Args:
        metodo_pago: 'transferencia' o 'efectivo'
        cantidad: cantidad de la transacción para incluir en el ID
        fecha: datetime con zona horaria. Si no se proporciona, usa timezone.now()
    """
    ahora = fecha if fecha else timezone.now()  # Usar la fecha proporcionada o timezone.now() con zona horaria de Cuba
    mes = f"{ahora.month:02d}"
    dia = f"{ahora.day:02d}"
    # Usar la cantidad en lugar de número aleatorio
    cantidad_str = f"{int(cantidad):03d}" if cantidad else "000"
    hora = f"{ahora.hour:02d}{ahora.minute:02d}{ahora.second:02d}"
    # T para transferencia, E para efectivo
    tipo_letra = 'T' if metodo_pago == 'transferencia' else 'E'
    return f"REM-{mes}/{dia}-{tipo_letra}{cantidad_str}-{hora}"

def generar_id_pago(tipo_pago='transferencia', cantidad=0, fecha=None):
    """Genera un ID único para el pago en formato PAGO-MM/DD-T###-HHMMSS o PAGO-MM/DD-E###-HHMMSS
    
    Args:
        tipo_pago: 'transferencia' o 'efectivo'
        cantidad: cantidad de la transacción para incluir en el ID
        fecha: datetime con zona horaria. Si no se proporciona, usa timezone.now()
    """
    ahora = fecha if fecha else timezone.now()  # Usar la fecha proporcionada o timezone.now() con zona horaria de Cuba
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
    # Campos deprecados - mantener por compatibilidad temporal
    valor_actual = models.DecimalField(
        max_digits=15, 
        decimal_places=6,
        default=0,
        verbose_name='Valor Actual (Deprecado)',
        help_text='Campo deprecado - usar ValorMoneda'
    )
    valor_comercial = models.DecimalField(
        max_digits=15, 
        decimal_places=6,
        default=0,
        verbose_name='Valor Comercial (Deprecado)',
        help_text='Campo deprecado - usar ValorMoneda'
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
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    def get_valor_para_usuario(self, usuario):
        """
        Obtiene el valor de esta moneda para un usuario específico
        """
        if not usuario or not hasattr(usuario, 'perfil') or not usuario.perfil.tipo_valor_moneda:
            # Usar tipo por defecto si no tiene asignado
            tipo_defecto = TipoValorMoneda.get_tipo_por_defecto()
            if not tipo_defecto:
                # Fallback al valor_actual si no hay tipos configurados
                return self.valor_actual
            tipo_valor = tipo_defecto
        else:
            tipo_valor = usuario.perfil.tipo_valor_moneda
        
        try:
            valor_moneda = self.valores.get(tipo_valor=tipo_valor)
            return valor_moneda.valor
        except ValorMoneda.DoesNotExist:
            # Fallback al valor_actual si no existe el valor para este tipo
            return self.valor_actual
    
    def get_valor_para_tipo(self, tipo_valor):
        """
        Obtiene el valor de esta moneda para un tipo de valor específico
        """
        try:
            valor_moneda = self.valores.get(tipo_valor=tipo_valor)
            return valor_moneda.valor
        except ValorMoneda.DoesNotExist:
            return self.valor_actual
    
    def set_valor_para_tipo(self, tipo_valor, valor, usuario=None):
        """
        Establece el valor de esta moneda para un tipo específico
        """
        valor_moneda, created = ValorMoneda.objects.get_or_create(
            moneda=self,
            tipo_valor=tipo_valor,
            defaults={'valor': valor, 'actualizado_por': usuario}
        )
        if not created:
            valor_moneda.valor = valor
            valor_moneda.actualizado_por = usuario
            valor_moneda.save()
        return valor_moneda
    
    def crear_valores_para_todos_los_tipos(self):
        """
        Crea entradas de ValorMoneda con valor 0 para todos los tipos existentes
        """
        tipos_existentes = TipoValorMoneda.objects.filter(activo=True)
        for tipo in tipos_existentes:
            ValorMoneda.objects.get_or_create(
                moneda=self,
                tipo_valor=tipo,
                defaults={'valor': 0}
            )

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
    
    # Campos para valores históricos (inmutables una vez guardados)
    valor_moneda_historico = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Valor de la moneda al momento de crear el pago (inmutable)"
    )
    monto_usd_historico = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monto en USD calculado al momento de crear el pago (inmutable)"
    )
    
    # Campos para controlar ediciones
    editado = models.BooleanField(
        default=False,
        help_text="Indica si el pago ha sido editado después de su creación"
    )
    fecha_edicion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de la última edición"
    )
    usuario_editor = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_editados',
        help_text="Usuario que realizó la última edición"
    )
    
    destinatario = models.CharField(max_length=255, help_text="Nombre del destinatario")
    telefono = models.CharField(max_length=20, blank=True, null=True, help_text="Teléfono del destinatario")
    direccion = models.TextField(blank=True, null=True, help_text="Dirección del destinatario")
    carnet_identidad = models.CharField(max_length=50, blank=True, null=True, help_text="Carnet de identidad del destinatario")
    fecha_creacion = models.DateTimeField(default=timezone.now, help_text="Fecha de creación del pago con zona horaria de Cuba")
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
        from decimal import Decimal
        
        # Generar ID automáticamente si no existe
        if not self.pago_id:
            # Obtener la fecha actual con zona horaria de Cuba (configurada en settings.py)
            fecha_actual = timezone.now()
            
            cantidad = float(self.cantidad) if self.cantidad else 0
            
            # Generar el ID usando la misma fecha que se usará para el campo 'fecha_creacion'
            self.pago_id = generar_id_pago(self.tipo_pago, cantidad, fecha_actual)
            
            # Si es un nuevo pago, establecer la fecha_creacion manualmente para que coincida con el ID
            # Nota: fecha_creacion tiene auto_now_add=True, así que se establecerá automáticamente,
            # pero al establecerla aquí nos aseguramos de usar exactamente la misma fecha
            if not self.pk and not self.fecha_creacion:
                self.fecha_creacion = fecha_actual
        
        # Calcular y guardar valores históricos solo al crear (no al editar)
        if not self.pk and self.tipo_moneda and self.cantidad and self.usuario:
            # Obtener el valor de la moneda para el usuario al momento de crear
            valor_para_usuario = self.tipo_moneda.get_valor_para_usuario(self.usuario)
            self.valor_moneda_historico = Decimal(str(valor_para_usuario))
            
            # Calcular el monto en USD al momento de crear
            if self.tipo_moneda.codigo == 'USD':
                self.monto_usd_historico = Decimal(str(self.cantidad))
            else:
                cantidad_decimal = Decimal(str(self.cantidad))
                if self.valor_moneda_historico > 0:
                    self.monto_usd_historico = cantidad_decimal / self.valor_moneda_historico
                else:
                    self.monto_usd_historico = Decimal('0')
        
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
    
    def calcular_monto_en_usd(self, usuario=None):
        """
        Retorna el monto del pago convertido a USD
        Usa valores históricos si están disponibles (inmutables),
        sino calcula dinámicamente para compatibilidad con registros antiguos
        """
        from decimal import Decimal
        
        if not self.cantidad:
            return Decimal('0')
        
        # Si tenemos el valor histórico guardado, usarlo (inmutable)
        if self.monto_usd_historico is not None:
            return self.monto_usd_historico
        
        # Fallback para registros antiguos sin valores históricos
        if not self.tipo_moneda:
            return Decimal('0')
        
        try:
            if self.tipo_moneda.codigo == 'USD':
                return self.cantidad
            else:
                # Solo calcular dinámicamente si no hay valor histórico
                usuario_calculo = usuario or self.usuario
                valor_para_usuario = self.tipo_moneda.get_valor_para_usuario(usuario_calculo)
                
                if valor_para_usuario and valor_para_usuario > 0:
                    monto_usd = self.cantidad / valor_para_usuario
                    return monto_usd
                else:
                    # Fallback al valor_actual si no hay valor específico
                    if self.tipo_moneda.valor_actual and self.tipo_moneda.valor_actual > 0:
                        return self.cantidad / self.tipo_moneda.valor_actual
                    return Decimal('0')
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

    def recalcular_valores_por_edicion(self):
        """
        Recalcula y actualiza los valores históricos cuando se edita el pago
        Usa las tasas actuales al momento de la edición
        """
        from decimal import Decimal
        from django.utils import timezone
        
        if self.tipo_moneda and self.cantidad and self.usuario:
            # Obtener el valor actual de la moneda para el usuario
            valor_actual = self.tipo_moneda.get_valor_para_usuario(self.usuario)
            self.valor_moneda_historico = Decimal(str(valor_actual))
            
            # Calcular nuevo monto en USD con la tasa actual
            if self.tipo_moneda.codigo == 'USD':
                self.monto_usd_historico = Decimal(str(self.cantidad))
            else:
                cantidad_decimal = Decimal(str(self.cantidad))
                if valor_actual > 0:
                    self.monto_usd_historico = cantidad_decimal / Decimal(str(valor_actual))
                else:
                    self.monto_usd_historico = Decimal('0')
            
            # Marcar como editado
            self.editado = True
            self.fecha_edicion = timezone.now()
            # El usuario_editor se debe establecer desde la vista
            
            # Guardar sin llamar save() completo para evitar recursión
            super(Pago, self).save(update_fields=['valor_moneda_historico', 'monto_usd_historico', 'editado', 'fecha_edicion', 'usuario_editor'])
            return True
        return False


class Remesa(models.Model):
    TIPO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('efectivo', 'Efectivo'),
    ]
    
    remesa_id = models.CharField(max_length=50, unique=True, blank=True, help_text="ID único de la remesa")
    fecha = models.DateTimeField(default=timezone.now, help_text="Fecha de la remesa con zona horaria de Cuba")
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, blank=True, null=True, help_text="Tipo de pago")
    moneda = models.ForeignKey(Moneda, on_delete=models.SET_NULL, blank=True, null=True, help_text="Moneda usada en la remesa")
    importe = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Importe")
    
    # Campos para valores históricos (inmutables una vez guardados)
    valor_moneda_historico = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Valor de la moneda al momento de crear la remesa (inmutable)"
    )
    monto_usd_historico = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monto en USD calculado al momento de crear la remesa (inmutable)"
    )
    
    # Campos para controlar ediciones
    editada = models.BooleanField(
        default=False,
        help_text="Indica si la remesa ha sido editada después de su creación"
    )
    fecha_edicion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de la última edición"
    )
    usuario_editor = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='remesas_editadas',
        help_text="Usuario que realizó la última edición"
    )
    
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
        from decimal import Decimal
        
        # Generar ID automáticamente si no existe
        if not self.remesa_id:
            # Obtener la fecha actual con zona horaria de Cuba (configurada en settings.py)
            fecha_actual = timezone.now()
            
            # Usar el tipo_pago directamente
            metodo_pago_tipo = self.tipo_pago if self.tipo_pago else 'transferencia'
            
            # Usar el importe como cantidad
            cantidad = float(self.importe) if self.importe else 0
            
            # Generar el ID usando la misma fecha que se usará para el campo 'fecha'
            self.remesa_id = generar_id_remesa(metodo_pago_tipo, cantidad, fecha_actual)
            
            # Si es una nueva remesa, establecer la fecha manualmente para que coincida con el ID
            if not self.pk and not self.fecha:
                self.fecha = fecha_actual
        
        # Calcular y guardar valores históricos solo al crear (no al editar)
        if not self.pk and self.moneda and self.importe and self.gestor:
            # Obtener el valor de la moneda para el usuario al momento de crear
            valor_para_usuario = self.moneda.get_valor_para_usuario(self.gestor)
            self.valor_moneda_historico = Decimal(str(valor_para_usuario))
            
            # Calcular el monto en USD al momento de crear
            if self.moneda.codigo == 'USD':
                self.monto_usd_historico = Decimal(str(self.importe))
            else:
                importe_decimal = Decimal(str(self.importe))
                if self.valor_moneda_historico > 0:
                    self.monto_usd_historico = importe_decimal / self.valor_moneda_historico
                else:
                    self.monto_usd_historico = Decimal('0')
        
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

    def calcular_monto_en_usd(self, usuario=None):
        """
        Retorna el monto de la remesa convertido a USD
        Usa valores históricos si están disponibles (inmutables),
        sino calcula dinámicamente para compatibilidad con registros antiguos
        """
        from decimal import Decimal
        
        if not self.importe:
            return Decimal('0')
        
        # Si tenemos el valor histórico guardado, usarlo (inmutable)
        if self.monto_usd_historico is not None:
            return self.monto_usd_historico
        
        # Fallback para registros antiguos sin valores históricos
        if not self.moneda:
            return Decimal('0')
        
        try:
            if self.moneda.codigo == 'USD':
                return self.importe
            else:
                # Solo calcular dinámicamente si no hay valor histórico
                usuario_calculo = usuario or self.gestor
                valor_para_usuario = self.moneda.get_valor_para_usuario(usuario_calculo)
                
                if valor_para_usuario and valor_para_usuario > 0:
                    monto_usd = self.importe / valor_para_usuario
                    return monto_usd
                else:
                    # Fallback al valor_actual si no hay valor específico
                    if self.moneda.valor_actual and self.moneda.valor_actual > 0:
                        return self.importe / self.moneda.valor_actual
                    return Decimal('0')
        except Exception:
            return Decimal('0')

    def actualizar_balance_usuario(self):
        """DEPRECATED: El balance ahora se calcula dinámicamente"""
        # Esta funcionalidad está deshabilitada porque el balance
        # se calcula dinámicamente en base a las transacciones
        return True

    def recalcular_valores_por_edicion(self):
        """
        Recalcula y actualiza los valores históricos cuando se edita la remesa
        Usa las tasas actuales al momento de la edición
        """
        from decimal import Decimal
        from django.utils import timezone
        
        if self.moneda and self.importe and self.gestor:
            # Obtener el valor actual de la moneda para el gestor
            valor_actual = self.moneda.get_valor_para_usuario(self.gestor)
            self.valor_moneda_historico = Decimal(str(valor_actual))
            
            # Calcular nuevo monto en USD con la tasa actual
            if self.moneda.codigo == 'USD':
                self.monto_usd_historico = Decimal(str(self.importe))
            else:
                importe_decimal = Decimal(str(self.importe))
                if valor_actual > 0:
                    self.monto_usd_historico = importe_decimal / Decimal(str(valor_actual))
                else:
                    self.monto_usd_historico = Decimal('0')
            
            # Marcar como editada
            self.editada = True
            self.fecha_edicion = timezone.now()
            # El usuario_editor se debe establecer desde la vista
            
            # Guardar sin llamar save() completo para evitar recursión
            super(Remesa, self).save(update_fields=['valor_moneda_historico', 'monto_usd_historico', 'editada', 'fecha_edicion', 'usuario_editor'])
            return True
        return False

# Signals para manejar la creación automática de valores
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# Signal deshabilitado temporalmente para evitar errores de UNIQUE constraint
# @receiver(post_save, sender=TipoValorMoneda)
# def crear_valores_para_monedas_existentes(sender, instance, created, **kwargs):
#     """
#     Cuando se crea un nuevo tipo de valor, crear entradas con valor 0 
#     para todas las monedas existentes
#     """
#     if created:
#         from django.db import IntegrityError
#         monedas_existentes = Moneda.objects.filter(activa=True)
#         for moneda in monedas_existentes:
#             try:
#                 ValorMoneda.objects.get_or_create(
#                     moneda=moneda,
#                     tipo_valor=instance,
#                     defaults={'valor': 0}
#                 )
#             except IntegrityError:
#                 # Si ya existe, simplemente continuar con la siguiente moneda
#                 pass

@receiver(post_save, sender=Moneda)
def crear_valores_para_tipos_existentes(sender, instance, created, **kwargs):
    """
    Cuando se crea una nueva moneda, crear entradas con valor 0 
    para todos los tipos de valores existentes
    """
    if created:
        instance.crear_valores_para_todos_los_tipos()


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
