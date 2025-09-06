from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone

class PerfilUsuario(models.Model):
    """
    Modelo para extender la información del usuario
    """
    TIPO_USUARIO_CHOICES = [
        ('admin', 'Administrador'),
        ('gestor', 'Gestor'),
        ('contable', 'Contable'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES, default='gestor', verbose_name="Tipo de Usuario")
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Balance")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    # Nuevo campo para tipo de valor de moneda
    tipo_valor_moneda = models.ForeignKey(
        'remesas.TipoValorMoneda', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Tipo de Valor de Moneda",
        help_text="Tipo de valor de moneda que utiliza este usuario para los cálculos"
    )
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")
    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Avatar")
    
    # Campos específicos para gestores de remesas
    codigo_gestor = models.CharField(max_length=10, unique=True, blank=True, null=True, verbose_name="Código de Gestor")
    limite_remesas = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Límite de Remesas")
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Comisión (%)")
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='perfiles_creados')
    
    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"
    
    def __str__(self):
        return f"Perfil de {self.user.username}"
    
    @property
    def nombre_completo(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    def calcular_balance_real(self):
        """
        Calcula el balance real del usuario basándose en remesas y pagos confirmados
        usando el tipo de valor de moneda asignado al usuario
        """
        from remesas.models import Remesa, Pago
        from decimal import Decimal
        import logging
        
        logger = logging.getLogger(__name__)
        balance_calculado = Decimal('0.00')
        
        # Sumar remesas completadas (dinero que entra)
        remesas_completadas = Remesa.objects.filter(
            gestor=self.user, 
            estado='completada',
            importe__isnull=False
        ).select_related('moneda')
        
        total_remesas = Decimal('0.00')
        for remesa in remesas_completadas:
            if remesa.importe and remesa.importe > 0:
                # Convertir a USD usando el valor específico del usuario
                if remesa.moneda and remesa.moneda.codigo != 'USD':
                    try:
                        valor_para_usuario = remesa.moneda.get_valor_para_usuario(self.user)
                        if valor_para_usuario and valor_para_usuario > 0:
                            importe_usd = remesa.importe / valor_para_usuario
                            total_remesas += importe_usd
                        else:
                            logger.warning(f"Moneda {remesa.moneda.codigo} tiene valor inválido para usuario {self.user.username}: {valor_para_usuario}")
                    except (ZeroDivisionError, AttributeError) as e:
                        logger.error(f"Error convirtiendo remesa {remesa.remesa_id}: {e}")
                else:
                    # Remesa en USD o sin moneda específica
                    total_remesas += remesa.importe
        
        balance_calculado += total_remesas
        
        # Restar pagos confirmados (dinero que sale)
        pagos_confirmados = Pago.objects.filter(
            usuario=self.user,
            estado='confirmado',
            cantidad__isnull=False
        ).select_related('tipo_moneda')
        
        total_pagos = Decimal('0.00')
        for pago in pagos_confirmados:
            if pago.cantidad and pago.cantidad > 0:
                # Convertir a USD usando el valor específico del usuario
                if pago.tipo_moneda and pago.tipo_moneda.codigo != 'USD':
                    try:
                        valor_para_usuario = pago.tipo_moneda.get_valor_para_usuario(self.user)
                        if valor_para_usuario and valor_para_usuario > 0:
                            cantidad_usd = pago.cantidad / valor_para_usuario
                            total_pagos += cantidad_usd
                        else:
                            logger.warning(f"Moneda {pago.tipo_moneda.codigo} tiene valor inválido para usuario {self.user.username}: {valor_para_usuario}")
                    except (ZeroDivisionError, AttributeError) as e:
                        logger.error(f"Error convirtiendo pago {pago.pago_id}: {e}")
                else:
                    # Pago en USD o sin moneda específica
                    total_pagos += pago.cantidad
        
        balance_calculado -= total_pagos
        
        # Log para debugging si es necesario
        logger.debug(f"Balance calculado para {self.user.username}: Remesas={total_remesas}, Pagos={total_pagos}, Balance={balance_calculado}")
        
        return balance_calculado
    
    def actualizar_balance(self):
        """
        Actualiza el campo balance con el balance real calculado
        """
        balance_real = self.calcular_balance_real()
        self.balance = balance_real
        self.save()
        return balance_real
    
    def clean(self):
        """
        Validaciones personalizadas del modelo
        """
        from django.core.exceptions import ValidationError
        
        # Validar consistencia entre tipo_usuario y status de superuser
        if self.user.is_superuser and self.tipo_usuario != 'admin':
            raise ValidationError({
                'tipo_usuario': 'Los superusers deben tener tipo de usuario "admin"'
            })
    
    def save(self, *args, **kwargs):
        """
        Sobrescribir save para aplicar validaciones automáticas
        """
        # Auto-corregir tipo de usuario para superusers
        if self.user.is_superuser and self.tipo_usuario != 'admin':
            self.tipo_usuario = 'admin'
        
        super().save(*args, **kwargs)

class SesionUsuario(models.Model):
    """
    Modelo para rastrear sesiones de usuarios
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    ultima_actividad = models.DateTimeField(auto_now=True)
    activa = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Sesión de Usuario"
        verbose_name_plural = "Sesiones de Usuarios"
    
    def __str__(self):
        return f"Sesión de {self.usuario.username}"
    
    @property
    def duracion_sesion(self):
        return self.ultima_actividad - self.fecha_inicio

class HistorialAcciones(models.Model):
    """
    Modelo para auditoría de acciones de usuarios
    """
    TIPOS_ACCION = [
        ('login', 'Inicio de Sesión'),
        ('logout', 'Cierre de Sesión'),
        ('create', 'Creación'),
        ('update', 'Actualización'),
        ('delete', 'Eliminación'),
        ('view', 'Consulta'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historial_acciones')
    accion = models.CharField(max_length=20, choices=TIPOS_ACCION)
    descripcion = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    
    # Para relacionar con modelos específicos (opcional)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Historial de Acción"
        verbose_name_plural = "Historial de Acciones"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.get_accion_display()} - {self.fecha}"

# Función para crear automáticamente el perfil cuando se crea un usuario
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        # Crear perfil con tipo correcto según si es superuser
        tipo_usuario = 'admin' if instance.is_superuser else 'gestor'
        
        # Obtener tipo de valor por defecto
        from remesas.models import TipoValorMoneda
        tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
        
        PerfilUsuario.objects.create(
            user=instance, 
            tipo_usuario=tipo_usuario,
            tipo_valor_moneda=tipo_valor_defecto
        )
    else:
        # Usuario existente - sincronizar tipo de usuario si tiene perfil
        if hasattr(instance, 'perfil'):
            tipo_esperado = 'admin' if instance.is_superuser else instance.perfil.tipo_usuario
            
            # Solo actualizar si un superuser no tiene tipo 'admin'
            if instance.is_superuser and instance.perfil.tipo_usuario != 'admin':
                instance.perfil.tipo_usuario = 'admin'
                instance.perfil.save()
            
            # Asignar tipo de valor por defecto si no tiene uno
            if not instance.perfil.tipo_valor_moneda:
                from remesas.models import TipoValorMoneda
                tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
                if tipo_valor_defecto:
                    instance.perfil.tipo_valor_moneda = tipo_valor_defecto
                    instance.perfil.save()
