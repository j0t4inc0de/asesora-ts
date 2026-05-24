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
import mercadopago
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
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

                cita = Cita.objects.create(
                    cliente=cliente,
                    servicio=servicio_obj,
                    fecha_hora=fecha_hora_obj,
                    estado='P',  # Pendiente
                    estado_pago='NO' # No pagado
                )

            except IntegrityError:
                cliente.delete()
                messages.error(
                    request, "Esa hora se ocupó en este preciso instante. Selecciona otra disponibilidad.")
                return redirect(reverse('home') + '#seccion-reserva')

            # --- INTEGRACION MERCADO PAGO ---
            try:
                sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                
                # Usar SITE_URL para entornos locales o producción
                site_url = settings.SITE_URL
                
                preference_data = {
                    "items": [
                        {
                            "title": f"Asesoría: {servicio_obj.nombre}",
                            "quantity": 1,
                            "unit_price": servicio_obj.precio,
                            "currency_id": "CLP",
                        }
                    ],
                    "back_urls": {
                        "success": f"{site_url}{reverse('pago_exito')}",
                        "failure": f"{site_url}{reverse('pago_fallo')}",
                        "pending": f"{site_url}{reverse('pago_pendiente')}",
                    },
                    "external_reference": str(cita.id),
                    "notification_url": f"{site_url}{reverse('mp_webhook')}",
                }
                
                # MP exige un dominio público para auto_return. Si estamos en localhost, lo omitimos.
                if "localhost" not in site_url and "127.0.0.1" not in site_url:
                    preference_data["auto_return"] = "approved"
                
                preference_response = sdk.preference().create(preference_data)
                
                if preference_response.get("status") not in (200, 201):
                    error_msg = preference_response.get("response", "Error desconocido")
                    raise Exception(f"MP devolvió error {preference_response.get('status')}: {error_msg}")
                    
                preference = preference_response["response"]
                
                # Guardar el preference_id en la cita
                cita.mp_preference_id = preference["id"]
                cita.save()
                
                # Redirigir al Checkout Pro
                url_checkout = preference["sandbox_init_point"] if settings.DEBUG else preference["init_point"]
                return redirect(url_checkout)
                
            except Exception as e:
                # Si falla Mercado Pago, cancelar cita y avisar
                cita.estado = 'X'
                cita.save()
                messages.error(request, f"Hubo un error con Mercado Pago: {str(e)}")
                return redirect(reverse('home') + '#seccion-reserva')

        else:
            messages.error(
                request, "Por favor, completa todos los campos correctamente y asegúrate de seleccionar una hora.")
            return redirect(reverse('home') + '#seccion-reserva')

    return redirect('home')


def _enviar_email_confirmacion(cita):
    cliente = cita.cliente
    servicio = cita.servicio
    fecha_hora_obj = cita.fecha_hora
    
    asunto = f"Nueva Cita Agendada y Pagada: {cliente.nombre}"
    mensaje = f"""¡Hola! Has recibido una nueva reserva pagada en AsesoraTS Chile:

HORA AGENDADA: {fecha_hora_obj.strftime('%d/%m/%Y a las %H:%M hrs')}
    
    • Cliente: 
        NOMBRES: {cliente.nombre}
        RUT: {cliente.rut}
    • Teléfono: {cliente.telefono}
    • Servicio: {servicio.nombre}
    • Motivo: {cliente.motivo_consulta}
    • Transacción MP: {cita.transaccion_id}
"""
    try:
        send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, [
                  settings.EMAIL_HOST_USER], fail_silently=False)
    except Exception as e:
        print(f"Error al enviar correo: {e}")


def pago_exito(request):
    payment_id = request.GET.get('payment_id')
    external_ref = request.GET.get('external_reference')
    
    if external_ref:
        cita = Cita.objects.filter(id=external_ref).first()
        if cita and cita.estado_pago != 'PA':
            cita.estado_pago = 'PA'
            cita.estado = 'C' # Confirmada
            cita.transaccion_id = payment_id
            cita.save()
            _enviar_email_confirmacion(cita)
    
    return render(request, 'pago/exito.html')


def pago_fallo(request):
    external_ref = request.GET.get('external_reference')
    if external_ref:
        cita = Cita.objects.filter(id=external_ref).first()
        if cita and cita.estado_pago != 'PA':
            cita.estado_pago = 'NO'
            cita.estado = 'X' # Cancelada
            cita.save()
            
    return render(request, 'pago/fallo.html')


def pago_pendiente(request):
    external_ref = request.GET.get('external_reference')
    if external_ref:
        cita = Cita.objects.filter(id=external_ref).first()
        if cita and cita.estado_pago != 'PA':
            cita.estado_pago = 'PE'
            cita.save()
            
    return render(request, 'pago/pendiente.html')


@csrf_exempt
def mercadopago_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Mercado Pago envía 'action' y 'type' en las IPN/Webhooks
            if data.get('type') == 'payment' or data.get('topic') == 'payment':
                payment_id = data.get('data', {}).get('id')
                if not payment_id and 'id' in data: # IPN a veces manda el id en raiz
                    payment_id = data['id']
                    
                if payment_id:
                    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                    payment_info = sdk.payment().get(payment_id)
                    payment = payment_info['response']
                    
                    external_ref = payment.get('external_reference')
                    status = payment.get('status')
                    
                    if external_ref:
                        cita = Cita.objects.filter(id=external_ref).first()
                        if cita:
                            cita.transaccion_id = str(payment_id)
                            if status == 'approved':
                                if cita.estado_pago != 'PA':
                                    cita.estado_pago = 'PA'
                                    cita.estado = 'C'
                                    _enviar_email_confirmacion(cita)
                            elif status in ('pending', 'in_process', 'authorized'):
                                cita.estado_pago = 'PE'
                            elif status in ('rejected', 'cancelled', 'refunded', 'charged_back'):
                                cita.estado_pago = 'NO'
                                cita.estado = 'X'
                            cita.save()
                            
            return HttpResponse(status=200)
        except Exception as e:
            print(f"Webhook error: {e}")
            return HttpResponse(status=400)
    
    return HttpResponse(status=405)


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
