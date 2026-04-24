from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import Servicio, Cliente, Cita, HorarioAtencion

# Register your models here.
@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'cliente', 'servicio', 'estado', 'estado_pago')
    list_filter = ('estado', 'estado_pago', 'servicio', 'fecha_hora')
    list_select_related = ('cliente', 'servicio') 

    def save_model(self, request, obj, form, change):
        if change: # Si se está modificando una cita existente
            cita_anterior = Cita.objects.get(pk=obj.pk)
            # Si el estado cambió a 'Cancelada' ('X')
            if cita_anterior.estado != 'X' and obj.estado == 'X':
                asunto = "Actualización de su hora - AsesoraTS"
                mensaje = f"""
                Estimado/a {obj.cliente.nombre},
                
                Le informamos que su hora agendada para el {obj.fecha_hora.strftime('%d/%m/%Y a las %H:%M')} 
                ha tenido que ser cancelada por motivos de fuerza mayor de la profesional.
                
                Por favor, ingrese nuevamente a nuestra plataforma para reagendar.
                Lamentamos los inconvenientes.
                
                Atentamente,
                AsesoraTS Chile.
                """
                send_mail(
                    asunto, 
                    mensaje, 
                    settings.EMAIL_HOST_USER,
                    [obj.cliente.email], 
                    fail_silently=False,
                )
        super().save_model(request, obj, form, change)

admin.site.register(Servicio)
admin.site.register(Cliente)
admin.site.register(HorarioAtencion)