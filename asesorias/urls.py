from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("about/", views.ir_portafolio, name="portafolio"),
    path('agendar/', views.agendar_cita, name='agendar_cita'),
    path('pago/exito/', views.pago_exito, name='pago_exito'),
    path('pago/fallo/', views.pago_fallo, name='pago_fallo'),
    path('pago/pendiente/', views.pago_pendiente, name='pago_pendiente'),
    path('webhooks/mercadopago/', views.mercadopago_webhook, name='mp_webhook'),
    path('servicio/<int:servicio_id>/', views.detalle_servicio, name='detalle_servicio'),
    path('api/verificar-slot/', views.verificar_slot, name='verificar_slot'),
    path('terminos-y-condiciones/', views.terminos_condiciones, name='terminos_condiciones'),
    path('politica-de-privacidad/', views.politica_privacidad, name='politica_privacidad'),
]