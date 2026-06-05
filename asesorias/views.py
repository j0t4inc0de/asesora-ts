from django.shortcuts import redirect, render, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.db.models import Q
from datetime import date, timedelta, datetime
from .models import Servicio, HorarioAtencion, Cita, SobreMi
from .forms import FormularioDiagnostico
import mercadopago
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
import json
import logging

logger = logging.getLogger('asesorias.reservas')

def home(request):
    servicios = Servicio.objects.all()
    form = FormularioDiagnostico()
    hoy = timezone.localdate().strftime('%Y-%m-%d')
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
            try:
                fecha_hora_obj = timezone.make_aware(
                    datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S'))
            except (ValueError, TypeError):
                messages.error(request, "Formato de fecha inválido. Intenta de nuevo.")
                return redirect(reverse('home') + '#seccion-reserva')

            # Validar que la hora no sea pasada
            if fecha_hora_obj <= timezone.now():
                messages.error(request, "No puedes agendar una hora que ya pasó.")
                return redirect(reverse('home') + '#seccion-reserva')

            # Buscar servicio por nombre (con manejo de error)
            try:
                servicio_obj = Servicio.objects.get(nombre=nombre_servicio)
            except Servicio.DoesNotExist:
                messages.error(request, "El servicio seleccionado no existe.")
                return redirect(reverse('home') + '#seccion-reserva')

            logger.info(
                f"RESERVA_INTENTO | slot={fecha_hora_str} | "
                f"IP={request.META.get('REMOTE_ADDR')} | "
                f"servicio={nombre_servicio}")

            try:
                with transaction.atomic():
                    # Limpiar citas canceladas que bloquean este slot (fix para unique=True)
                    Cita.objects.filter(fecha_hora=fecha_hora_obj, estado='X').delete()

                    # Verificar disponibilidad DENTRO de la transacción
                    if Cita.objects.filter(fecha_hora=fecha_hora_obj).exists():
                        raise ValueError("Hora no disponible")

                    cliente = form.save()
                    cita = Cita.objects.create(
                        cliente=cliente,
                        servicio=servicio_obj,
                        fecha_hora=fecha_hora_obj,
                        estado='P',
                        estado_pago='NO'
                    )
                    logger.info(f"RESERVA_OK | cita_id={cita.id} | slot={fecha_hora_str}")

            except (ValueError, IntegrityError) as e:
                logger.warning(
                    f"RESERVA_CONFLICTO | slot={fecha_hora_str} | error={type(e).__name__}")
                messages.error(
                    request,
                    "¡Ups! Esa hora acaba de ser reservada por otra persona. "
                    "Por favor, selecciona una nueva hora.")
                return redirect(reverse('home') + '#seccion-reserva')

            # Si el servicio es gratuito, no llamamos a Mercado Pago
            if servicio_obj.precio == 0:
                try:
                    cita.estado_pago = 'PA'
                    cita.estado = 'C'  # Confirmada
                    cita.transaccion_id = f"FREE-{cita.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    cita.save()
                    _enviar_email_confirmacion(cita)
                    logger.info(f"RESERVA_GRATIS_OK | cita_id={cita.id}")
                    messages.success(request, "¡Tu reserva gratuita ha sido agendada con éxito!")
                    # Redirigir a pago_exito simulando los parámetros para que muestre la pantalla de éxito
                    return redirect(reverse('pago_exito') + f"?payment_id={cita.transaccion_id}&external_reference={cita.id}")
                except Exception as e:
                    cita.estado = 'X'
                    cita.save()
                    logger.error(f"RESERVA_GRATIS_ERROR | cita_id={cita.id} | error={e}")
                    messages.error(request, "Hubo un problema al procesar la reserva gratuita.")
                    return redirect(reverse('home') + '#seccion-reserva')

            # --- INTEGRACION MERCADO PAGO ---
            try:
                sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
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

                if "localhost" not in site_url and "127.0.0.1" not in site_url:
                    preference_data["auto_return"] = "approved"

                preference_response = sdk.preference().create(preference_data)

                if preference_response.get("status") not in (200, 201):
                    error_msg = preference_response.get("response", "Error desconocido")
                    raise Exception(f"MP devolvió error {preference_response.get('status')}: {error_msg}")

                preference = preference_response["response"]
                cita.mp_preference_id = preference["id"]
                cita.save()

                url_checkout = preference["sandbox_init_point"] if settings.DEBUG else preference["init_point"]
                return redirect(url_checkout)

            except Exception as e:
                cita.estado = 'X'
                cita.save()
                logger.error(f"MERCADOPAGO_ERROR | cita_id={cita.id} | error={e}")
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
        logger.error(f"EMAIL_ERROR | cita_id={cita.id} | error={e}")


def pago_exito(request):
    payment_id = request.GET.get('payment_id')
    external_ref = request.GET.get('external_reference')
    
    if external_ref and payment_id:
        cita = Cita.objects.filter(id=external_ref).first()
        if cita and cita.estado_pago != 'PA':
            # Verificar con la API de MercadoPago que el pago es real
            try:
                sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                payment_info = sdk.payment().get(int(payment_id))
                payment = payment_info.get('response', {})

                if (payment.get('status') == 'approved' and
                    str(payment.get('external_reference')) == str(cita.id)):
                    cita.estado_pago = 'PA'
                    cita.estado = 'C'
                    cita.transaccion_id = str(payment_id)
                    cita.save()
                    _enviar_email_confirmacion(cita)
                    logger.info(f"PAGO_EXITO_VERIFICADO | cita_id={cita.id} | payment={payment_id}")
            except Exception as e:
                logger.warning(f"PAGO_EXITO_NO_VERIFICADO | cita_id={cita.id} | error={e}")
                # El webhook se encargará de confirmar
    
    return render(request, 'pago/exito.html')


def pago_fallo(request):
    external_ref = request.GET.get('external_reference')
    if external_ref:
        cita = Cita.objects.filter(id=external_ref).first()
        if cita and cita.estado_pago != 'PA':
            cita.estado_pago = 'NO'
            cita.estado = 'X' # Cancelada
            cita.save()
            logger.info(f"PAGO_FALLO | cita_id={cita.id} | external_ref={external_ref}")
            
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
            logger.error(f"WEBHOOK_ERROR | error={e}", exc_info=True)
            return HttpResponse(status=400)
    
    return HttpResponse(status=405)


def obtener_slots_disponibles():
    """Calcula las horas libres de los próximos 7 días."""
    hoy = timezone.localdate()
    slots_disponibles = []

    # Auto-expirar citas pendientes sin pago de hace más de 30 minutos
    limite_expiracion = timezone.now() - timedelta(minutes=30)
    Cita.objects.filter(
        estado='P',
        estado_pago='NO'
    ).filter(
        Q(creada_en__lt=limite_expiracion) | Q(creada_en__isnull=True, fecha_hora__lt=limite_expiracion)
    ).update(estado='X')

    # Pre-cargar TODAS las horas ocupadas del rango en una sola query
    fecha_fin_rango = hoy + timedelta(days=7)
    horas_ocupadas = set(
        Cita.objects.filter(
            fecha_hora__date__gte=hoy,
            fecha_hora__date__lt=fecha_fin_rango
        ).exclude(estado='X').values_list('fecha_hora', flat=True)
    )

    for i in range(7):
        dia_actual = hoy + timedelta(days=i)
        dia_semana_num = dia_actual.weekday()

        horario = HorarioAtencion.objects.filter(
            dia_semana=dia_semana_num, activo=True).first()
        if not horario:
            continue

        hora_actual = datetime.combine(dia_actual, horario.hora_inicio)
        hora_fin = datetime.combine(dia_actual, horario.hora_fin)

        bloques_dia = []
        while hora_actual < hora_fin:
            hora_actual_tz = timezone.make_aware(
                hora_actual) if timezone.is_naive(hora_actual) else hora_actual

            if hora_actual_tz < timezone.now() + timedelta(hours=1):
                hora_actual += timedelta(hours=1)
                continue

            if hora_actual_tz not in horas_ocupadas:
                bloques_dia.append({
                    'valor': hora_actual_tz.strftime('%Y-%m-%d %H:%M:%S'),
                    'etiqueta': hora_actual_tz.strftime('%H:%M')
                })

            hora_actual += timedelta(hours=1)

        if bloques_dia:
            slots_disponibles.append({
                'fecha_texto': f"{horario.get_dia_semana_display()} {dia_actual.strftime('%d/%m')}",
                'bloques': bloques_dia
            })

    return slots_disponibles


def verificar_slot(request):
    """Verifica si un slot de fecha y hora específico está disponible (no ocupado por una cita activa)."""
    fecha_hora_str = request.GET.get('fecha_hora')
    if not fecha_hora_str:
        return JsonResponse({'disponible': False, 'error': 'Falta el parámetro fecha_hora'}, status=400)

    try:
        fecha_hora_obj = timezone.make_aware(
            datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
        )
    except (ValueError, TypeError):
        return JsonResponse({'disponible': False, 'error': 'Formato de fecha inválido'}, status=400)

    # Verificar si existe una cita para esta hora que no esté cancelada ('X')
    ocupado = Cita.objects.filter(fecha_hora=fecha_hora_obj).exclude(estado='X').exists()
    return JsonResponse({'disponible': not ocupado})


def terminos_condiciones(request):
    """Renderiza la página de Términos y Condiciones de Servicio."""
    return render(request, 'legal/terminos.html')


def politica_privacidad(request):
    """Renderiza la página de Política de Privacidad."""
    return render(request, 'legal/privacidad.html')
