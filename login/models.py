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
        ('domicilio', 'Domicilio'),
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
    # Campo para monedas asignadas (para gestores y domicilios)
    monedas_asignadas = models.ManyToManyField(
        'remesas.Moneda',
        blank=True,
        verbose_name="Monedas Asignadas",
        help_text="Monedas que este usuario puede utilizar (solo para gestores y domicilios)",
        related_name='usuarios_asignados'
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
    
    def puede_usar_moneda(self, moneda):
        """
        Verifica si el usuario puede usar una moneda específica
        - Administradores y contables pueden usar todas las monedas
        - Gestores y domicilios solo pueden usar las monedas asignadas
        """
        if self.tipo_usuario in ['admin', 'contable']:
            return True
        
        if self.tipo_usuario in ['gestor', 'domicilio']:
            # Si no tiene monedas asignadas, puede usar todas por defecto
            if not self.monedas_asignadas.exists():
                return True
            return self.monedas_asignadas.filter(id=moneda.id).exists()
        
        return False
    
    def get_monedas_disponibles(self):
        """
        Retorna las monedas que el usuario puede utilizar
        """
        from remesas.models import Moneda
        
        if self.tipo_usuario in ['admin', 'contable']:
            return Moneda.objects.filter(activa=True)
        
        if self.tipo_usuario in ['gestor', 'domicilio']:
            # Si no tiene monedas asignadas, retornar todas las activas
            if not self.monedas_asignadas.exists():
                return Moneda.objects.filter(activa=True)
            return self.monedas_asignadas.filter(activa=True)
        
        return Moneda.objects.none()
    
    def calcular_balance_real(self):
        """
        Calcula el balance real del usuario basándose en remesas y pagos confirmados
        usando valores históricos guardados para mantener consistencia
        """
        from remesas.models import Remesa, Pago, PagoRemesa
        from decimal import Decimal
        import logging
        
        logger = logging.getLogger(__name__)
        balance_calculado = Decimal('0.00')
        
        # Sumar remesas confirmadas y completadas (dinero que entra)
        # Usar los mismos estados que en historial_usuario para consistencia
        remesas_validas = Remesa.objects.filter(
            gestor=self.user, 
            estado__in=['confirmada', 'completada'],
            importe__isnull=False
        ).select_related('moneda')
        
        total_remesas = Decimal('0.00')
        for remesa in remesas_validas:
            try:
                # Usar el método que prioriza valores históricos guardados
                monto_usd = remesa.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_remesas += Decimal(str(monto_usd))
            except Exception as e:
                logger.error(f"Error calculando monto USD para remesa {remesa.remesa_id}: {e}")
                continue
        
        balance_calculado += total_remesas
        
        # Restar pagos confirmados (dinero que sale)
        pagos_confirmados = Pago.objects.filter(
            usuario=self.user,
            estado='confirmado',
            cantidad__isnull=False
        ).select_related('tipo_moneda')

        pagos_remesa_confirmados = PagoRemesa.objects.filter(
            usuario=self.user,
            estado='confirmado',
            cantidad__isnull=False
        ).select_related('tipo_moneda')
        
        total_pagos = Decimal('0.00')
        for pago in pagos_confirmados:
            try:
                # Usar el método que prioriza valores históricos guardados
                monto_usd = pago.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_pagos += Decimal(str(monto_usd))
            except Exception as e:
                logger.error(f"Error calculando monto USD para pago {pago.pago_id}: {e}")
                continue

        for pago in pagos_remesa_confirmados:
            try:
                monto_usd = pago.calcular_monto_en_usd()
                if monto_usd is not None:
                    total_pagos += Decimal(str(monto_usd))
            except Exception as e:
                logger.error(f"Error calculando monto USD para pago remesa {pago.pago_id}: {e}")
                continue
        
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
