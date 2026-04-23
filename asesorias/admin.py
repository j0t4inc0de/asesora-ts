from django.contrib import admin
from .models import Servicio, Cliente, Cita

# Register your models here.
@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    # 'select_related' evita múltiples consultas a la DB al mostrar datos relacionados 
    list_display = ('fecha_hora', 'cliente', 'servicio', 'estado')
    list_filter = ('estado', 'servicio')
    list_select_related = ('cliente', 'servicio') 

admin.site.register(Servicio)
admin.site.register(Cliente)