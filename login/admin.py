from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from .models import PerfilUsuario, SesionUsuario, HistorialAcciones

# Inline para el perfil de usuario
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil'
    fk_name = 'user'  # Especificar el campo FK correcto
    fields = ('tipo_usuario', 'tipo_valor_moneda', 'telefono', 'direccion', 'fecha_nacimiento', 'codigo_gestor', 'limite_remesas', 'comision_porcentaje')

# Extender el UserAdmin para incluir el perfil
class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

# Re-registrar UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo_usuario', 'tipo_valor_moneda', 'telefono', 'codigo_gestor', 'limite_remesas', 'comision_porcentaje', 'fecha_creacion')
    list_filter = ('tipo_usuario', 'tipo_valor_moneda', 'fecha_creacion', 'fecha_actualizacion')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'codigo_gestor', 'telefono')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('user', 'tipo_usuario', 'tipo_valor_moneda', 'telefono', 'direccion', 'fecha_nacimiento', 'avatar')
        }),
        ('Información de Gestor', {
            'fields': ('codigo_gestor', 'limite_remesas', 'comision_porcentaje')
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        })
    )

@admin.register(SesionUsuario)
class SesionUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'ip_address', 'fecha_inicio', 'ultima_actividad', 'activa')
    list_filter = ('activa', 'fecha_inicio', 'ultima_actividad')
    search_fields = ('usuario__username', 'ip_address')
    readonly_fields = ('fecha_inicio', 'ultima_actividad', 'session_key')
    ordering = ('-ultima_actividad',)

@admin.register(HistorialAcciones)
class HistorialAccionesAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'descripcion', 'ip_address', 'fecha')
    list_filter = ('accion', 'fecha')
    search_fields = ('usuario__username', 'descripcion', 'ip_address')
    readonly_fields = ('fecha',)
    ordering = ('-fecha',)
    date_hierarchy = 'fecha'
    
    def has_add_permission(self, request):
        return False  # No permitir agregar manualmente
    
    def has_change_permission(self, request, obj=None):
        return False  # No permitir editar
