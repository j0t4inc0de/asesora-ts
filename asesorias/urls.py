from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('agendar/', views.agendar_cita, name='agendar_cita'),
    path('confirmacion/', views.confirmacion_solicitud, name='confirmacion_solicitud'),
]