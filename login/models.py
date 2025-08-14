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
        PerfilUsuario.objects.create(user=instance)
