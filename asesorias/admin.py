from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import Servicio, Cliente, Cita, HorarioAtencion, SobreMi, Experiencia, Educacion, Proyecto

# Register your models here.


def expirar_citas_pendientes(modeladmin, request, queryset):
    from django.utils import timezone
    from datetime import timedelta
    count = queryset.filter(
        estado='P',
        estado_pago='NO',
        fecha_hora__lt=timezone.now() - timedelta(minutes=30)
    ).update(estado='X')
    modeladmin.message_user(request, f'{count} citas pendientes expiradas.')
expirar_citas_pendientes.short_description = 'Expirar citas pendientes sin pago (>30 min)'


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'cliente',
                    'servicio', 'estado', 'estado_pago', 'creada_en')
    list_filter = ('estado', 'estado_pago', 'servicio', 'fecha_hora')
    list_select_related = ('cliente', 'servicio')
    readonly_fields = ('transaccion_id', 'mp_preference_id', 'creada_en')
    actions = [expirar_citas_pendientes]

    def save_model(self, request, obj, form, change):
        if change:
            try:
                cita_anterior = Cita.objects.get(pk=obj.pk)
            except Cita.DoesNotExist:
                super().save_model(request, obj, form, change)
                return
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
                try:
                    send_mail(
                        asunto,
                        mensaje,
                        settings.EMAIL_HOST_USER,
                        [obj.cliente.email],
                        fail_silently=False,
                    )
                except Exception:
                    pass  # Don't block admin save if email fails
        super().save_model(request, obj, form, change)


admin.site.register(Servicio)
admin.site.register(Cliente)
admin.site.register(HorarioAtencion)


class ExperienciaInline(admin.TabularInline):
    model = Experiencia
    extra = 1


class EducacionInline(admin.TabularInline):
    model = Educacion
    extra = 1

class ProyectoInline(admin.StackedInline):
    model = Proyecto
    extra = 0
    classes = ['collapse']

@admin.register(SobreMi)
class SobreMiAdmin(admin.ModelAdmin):
    inlines = [ExperienciaInline, EducacionInline, ProyectoInline]
