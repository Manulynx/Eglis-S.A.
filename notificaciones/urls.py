from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('configuracion/', views.configuracion_notificaciones, name='configuracion'),
    path('destinatarios/', views.destinatarios_notificaciones, name='destinatarios'),
    path('destinatarios/<int:destinatario_id>/editar/', views.editar_destinatario, name='editar_destinatario'),
    path('destinatarios/<int:destinatario_id>/toggle-estado/', views.toggle_estado_destinatario, name='toggle_estado_destinatario'),
    path('destinatarios/<int:destinatario_id>/eliminar/', views.eliminar_destinatario, name='eliminar_destinatario'),
    path('destinatarios/<int:destinatario_id>/enviar-test/', views.enviar_test_destinatario, name='enviar_test_destinatario'),
    path('logs/', views.logs_notificaciones, name='logs'),
    path('test-conexion/', views.test_conexion, name='test_conexion'),
    path('enviar-test/', views.enviar_test, name='enviar_test'),
]
