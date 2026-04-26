from django.shortcuts import redirect, render, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from django.db import IntegrityError
from datetime import date, timedelta, datetime
from .models import Servicio, HorarioAtencion, Cita, SobreMi
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


def ir_portafolio(request):
    portafolio = SobreMi.objects.all()

    return render(request, 'portafolio.html', {'portafolio': portafolio})


def detalle_servicio(request, servicio_id):
    servicio_obj = get_object_or_404(Servicio, id=servicio_id)
    return render(request, 'detalle_servicio.html', {'servicio': servicio_obj})


def agendar_cita(request):
    if request.method == 'POST':
        form = FormularioDiagnostico(request.POST)
        fecha_hora_str = request.POST.get('fecha_hora_reserva')
        nombre_servicio = request.POST.get('servicio')

        if form.is_valid() and fecha_hora_str and nombre_servicio:
            datos = form.cleaned_data
            fecha_hora_obj = timezone.make_aware(
                datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S'))

            if Cita.objects.filter(fecha_hora=fecha_hora_obj).exclude(estado='X').exists():
                messages.error(
                    request, "¡Ups! Esa hora acaba de ser reservada por otra persona mientras leías. Por favor, selecciona una nueva hora.")
                return redirect(reverse('home') + '#seccion-reserva')

            try:
                cliente = form.save()
                servicio_obj = Servicio.objects.get(nombre=nombre_servicio)

                Cita.objects.create(
                    cliente=cliente,
                    servicio=servicio_obj,
                    fecha_hora=fecha_hora_obj,
                    estado='P'  # Pendiente
                )

            except IntegrityError:
                cliente.delete()
                messages.error(
                    request, "Esa hora se ocupó en este preciso instante. Selecciona otra disponibilidad.")
                return redirect(reverse('home') + '#seccion-reserva')

            asunto = f"Nueva Cita Agendada: {datos['nombre']}"
            mensaje = f"""¡Hola! Has recibido una nueva reserva en AsesoraTS Chile:

HORA AGENDADA: {fecha_hora_obj.strftime('%d/%m/%Y a las %H:%M hrs')}
            
    • Cliente: 
        NOMBRES: {datos['nombre']}
        RUT: {datos['rut']}
    • Teléfono: {datos['telefono']}
    • Servicio: {nombre_servicio}
    • Motivo: {datos['motivo_consulta']}
"""
            send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, [
                      settings.EMAIL_HOST_USER], fail_silently=False)

            messages.success(request, "¡Tu cita ha sido solicitada con éxito!")
            return redirect('confirmacion_solicitud')

        else:
            messages.error(
                request, "Por favor, completa todos los campos correctamente y asegúrate de seleccionar una hora.")
            return redirect(reverse('home') + '#seccion-reserva')

    return redirect('home')


def confirmacion_solicitud(request):
    return render(request, 'confirmacion.html')


def obtener_slots_disponibles():
    """Calcula las horas libres de los próximos 14 días."""
    hoy = timezone.now().date()
    slots_disponibles = []

    for i in range(7):  # Revisaremos las próximas 2 semanas
        dia_actual = hoy + timedelta(days=i)
        dia_semana_num = dia_actual.weekday()  # 0 = Lunes, 6 = Domingo

        horario = HorarioAtencion.objects.filter(
            dia_semana=dia_semana_num, activo=True).first()
        if not horario:
            continue  # Si no hay horario creado para este día, saltamos

        hora_actual = datetime.combine(dia_actual, horario.hora_inicio)
        hora_fin = datetime.combine(dia_actual, horario.hora_fin)

        bloques_dia = []
        while hora_actual < hora_fin:
            # Hacer la hora "consciente" de la zona horaria (requerido por Django)
            hora_actual_tz = timezone.make_aware(
                hora_actual) if timezone.is_naive(hora_actual) else hora_actual

            if hora_actual_tz < timezone.now() + timedelta(hours=1):
                hora_actual += timedelta(hours=1)
                continue

            cita_ocupada = Cita.objects.filter(
                fecha_hora=hora_actual_tz).exclude(estado='X').exists()

            if not cita_ocupada:
                bloques_dia.append({
                    'valor': hora_actual_tz.strftime('%Y-%m-%d %H:%M:%S'),
                    'etiqueta': hora_actual_tz.strftime('%H:%M')
                })

            hora_actual += timedelta(hours=1)

        if bloques_dia:  # Solo agregamos el día si le quedan horas libres
            slots_disponibles.append({
                'fecha_texto': f"{horario.get_dia_semana_display()} {dia_actual.strftime('%d/%m')}",
                'bloques': bloques_dia
            })
    print("HORARIOS ACTIVOS ENCONTRADOS:",
          HorarioAtencion.objects.filter(activo=True))
    print("SLOTS GENERADOS:", slots_disponibles)

    return slots_disponibles
