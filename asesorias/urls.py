from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("about/", views.ir_portafolio, name="portafolio"),
    path('agendar/', views.agendar_cita, name='agendar_cita'),
    path('confirmacion/', views.confirmacion_solicitud, name='confirmacion_solicitud'),
    path('servicio/<int:servicio_id>/', views.detalle_servicio, name='detalle_servicio'),
]