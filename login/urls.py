from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'login'

urlpatterns = [
    # Login y logout
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login_form'),
    path('logout/', views.logout_view, name='logout'),
    
    # Administración de usuarios (requiere permisos de staff)
    path('admin/usuarios/', views.administrar_usuarios, name='administrar_usuarios'),
    path('admin/usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('admin/usuarios/obtener/<int:user_id>/', views.obtener_usuario, name='obtener_usuario'),
    path('admin/usuarios/editar/<int:user_id>/', views.editar_usuario, name='editar_usuario'),
    path('admin/usuarios/eliminar/<int:user_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('admin/usuarios/toggle/<int:user_id>/', views.toggle_usuario, name='toggle_usuario'),
    path('admin/usuarios/historial/<int:user_id>/', views.historial_usuario, name='historial_usuario'),
    
    # AJAX endpoints
    path('ajax/usuario/<int:user_id>/', views.obtener_usuario_ajax, name='obtener_usuario_ajax'),
]
