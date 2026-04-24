from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.conf import settings
from datetime import date
from .models import Servicio
from .forms import FormularioDiagnostico

def home(request):
    servicios = Servicio.objects.all()
    form = FormularioDiagnostico()
    hoy = date.today().strftime('%Y-%m-%d')
    
    return render(request, 'index.html', {
        'servicios': servicios, 
        'form': form, 
        'hoy': hoy
    })

def agendar_cita(request):
    if request.method == 'POST':
        form = FormularioDiagnostico(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            cliente = form.save()

            asunto = f"Nuevo Formulario de Contacto: {datos['nombre']}"
            mensaje = f"""
            Has recibido una nueva solicitud en AsesoraTS Chile:
            - Nombre: {datos['nombre']}
            - RUT: {datos['rut']}
            - Teléfono: {datos['telefono']}
            - Email: {datos['email']}
            - Motivo: {datos['motivo_consulta']}
            - Fecha sugerida: {datos['fecha_deseada'] if datos['fecha_deseada'] else 'No especificada'}
            """
            send_mail(
                asunto, mensaje, settings.EMAIL_HOST_USER,
                [settings.EMAIL_HOST_USER], fail_silently=False,
            )
            return redirect('confirmacion_solicitud')
        else:
            servicios = Servicio.objects.all()
            hoy = date.today().strftime('%Y-%m-%d')
            return render(request, 'index.html', {
                'form': form,
                'servicios': servicios,
                'hoy': hoy
            })

    return redirect('home')

def confirmacion_solicitud(request):
    return render(request, 'confirmacion.html')