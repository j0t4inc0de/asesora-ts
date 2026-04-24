from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta, datetime
from .models import Servicio, HorarioAtencion, Cita
from .forms import FormularioDiagnostico

def home(request):
    servicios = Servicio.objects.all()
    form = FormularioDiagnostico()
    hoy = date.today().strftime('%Y-%m-%d')
    slots = obtener_slots_disponibles()
    
    return render(request, 'index.html', {
        'servicios': servicios, 
        'form': form, 
        'hoy': hoy,
        'slots_disponibles': slots
    })

def agendar_cita(request):
    if request.method == 'POST':
        form = FormularioDiagnostico(request.POST)
        fecha_hora_str = request.POST.get('fecha_hora_reserva')
        nombre_servicio = request.POST.get('servicio')

        if form.is_valid() and fecha_hora_str and nombre_servicio:
            datos = form.cleaned_data
            
            cliente = form.save()

            servicio_obj = Servicio.objects.get(nombre=nombre_servicio)
            fecha_hora_obj = timezone.make_aware(datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S'))
            
            Cita.objects.create(
                cliente=cliente,
                servicio=servicio_obj,
                fecha_hora=fecha_hora_obj,
                estado='P' # Pendiente
            )

            asunto = f"Nueva Cita Agendada: {datos['nombre']}"
            mensaje = f"""
            ¡Hola! Has recibido una nueva reserva en AsesoraTS Chile:
            - Paciente: {datos['nombre']} ({datos['rut']})
            - Motivo: {datos['motivo_consulta']}
            - Teléfono: {datos['telefono']}
            - HORA AGENDADA: {fecha_hora_obj.strftime('%d/%m/%Y a las %H:%M hrs')}
            """
            send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, [settings.EMAIL_HOST_USER], fail_silently=False)
            
            return redirect('confirmacion_solicitud')
        else:
            return render(request, 'index.html', {
                'form': form,
                'servicios': Servicio.objects.all(),
                'slots_disponibles': obtener_slots_disponibles(),
                'error': "Por favor, selecciona una hora y completa todos los campos correctamente."
            })

    return redirect('home')

def confirmacion_solicitud(request):
    return render(request, 'confirmacion.html')

def obtener_slots_disponibles():
    """Calcula las horas libres de los próximos 14 días."""
    hoy = timezone.now().date()
    slots_disponibles = []
    
    for i in range(14): # Revisaremos las próximas 2 semanas
        dia_actual = hoy + timedelta(days=i)
        dia_semana_num = dia_actual.weekday() # 0 = Lunes, 6 = Domingo
        
        horario = HorarioAtencion.objects.filter(dia_semana=dia_semana_num, activo=True).first()
        if not horario:
            continue # Si no hay horario creado para este día, saltamos
            
        hora_actual = datetime.combine(dia_actual, horario.hora_inicio)
        hora_fin = datetime.combine(dia_actual, horario.hora_fin)
        
        bloques_dia = []
        while hora_actual < hora_fin:
            # Hacer la hora "consciente" de la zona horaria (requerido por Django)
            hora_actual_tz = timezone.make_aware(hora_actual) if timezone.is_naive(hora_actual) else hora_actual
            
            if hora_actual_tz < timezone.now() + timedelta(hours=1):
                hora_actual += timedelta(hours=1)
                continue
                
            cita_ocupada = Cita.objects.filter(fecha_hora=hora_actual_tz).exclude(estado='X').exists()
            
            if not cita_ocupada:
                bloques_dia.append({
                    'valor': hora_actual_tz.strftime('%Y-%m-%d %H:%M:%S'),
                    'etiqueta': hora_actual_tz.strftime('%H:%M')
                })
            
            hora_actual += timedelta(hours=1)
        
        if bloques_dia: # Solo agregamos el día si le quedan horas libres
            slots_disponibles.append({
                'fecha_texto': f"{horario.get_dia_semana_display()} {dia_actual.strftime('%d/%m')}",
                'bloques': bloques_dia
            })
    print("HORARIOS ACTIVOS ENCONTRADOS:", HorarioAtencion.objects.filter(activo=True))
    print("SLOTS GENERADOS:", slots_disponibles)
            
    return slots_disponibles