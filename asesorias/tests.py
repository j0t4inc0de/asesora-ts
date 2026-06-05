from django.test import TestCase
from django.utils import timezone
from datetime import timedelta, datetime
from django.urls import reverse
from django.core.management import call_command
from .models import Servicio, Cliente, Cita, HorarioAtencion

class SistemaReservasTests(TestCase):

    def setUp(self):
        # Crear servicio de prueba
        self.servicio = Servicio.objects.create(
            nombre="Diagnóstico Gratuito",
            descripcion="Servicio de prueba",
            precio=10000
        )
        # Crear un horario para que obtener_slots funcione
        self.hoy = timezone.localdate()
        self.dia_semana_hoy = self.hoy.weekday()
        HorarioAtencion.objects.create(
            dia_semana=self.dia_semana_hoy,
            hora_inicio=datetime.strptime("09:00", "%H:%M").time(),
            hora_fin=datetime.strptime("13:00", "%H:%M").time(),
            activo=True
        )

    def test_verificar_slot_disponible(self):
        # Fecha y hora en el futuro
        fecha_futura = datetime.combine(self.hoy, datetime.strptime("10:00", "%H:%M").time())
        fecha_futura_tz = timezone.make_aware(fecha_futura)
        fecha_str = fecha_futura_tz.strftime('%Y-%m-%d %H:%M:%S')

        # Si no hay cita, debe responder que está disponible
        response = self.client.get(reverse('verificar_slot'), {'fecha_hora': fecha_str})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['disponible'], True)

        # Crear una cita ocupando ese slot
        cliente = Cliente.objects.create(
            nombre="Juan Perez",
            rut="12345678-5",
            email="juan@gmail.com",
            telefono="+56912345678",
            motivo_consulta="Prueba"
        )
        cita = Cita.objects.create(
            cliente=cliente,
            servicio=self.servicio,
            fecha_hora=fecha_futura_tz,
            estado='P',
            estado_pago='NO'
        )

        # Si ya hay una cita en el slot, debe responder que no está disponible
        response = self.client.get(reverse('verificar_slot'), {'fecha_hora': fecha_str})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['disponible'], False)

        # Si cancelamos la cita (estado = 'X'), el slot debe figurar como disponible de nuevo
        cita.estado = 'X'
        cita.save()

        response = self.client.get(reverse('verificar_slot'), {'fecha_hora': fecha_str})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['disponible'], True)

    def test_evitar_citas_duplicadas_y_eliminar_canceladas(self):
        fecha_futura = datetime.combine(self.hoy, datetime.strptime("11:00", "%H:%M").time())
        fecha_futura_tz = timezone.make_aware(fecha_futura)
        fecha_str = fecha_futura_tz.strftime('%Y-%m-%d %H:%M:%S')

        # Crear una cita cancelada primero
        cliente_c = Cliente.objects.create(
            nombre="Cancelado",
            rut="12345678-5",
            email="c@gmail.com",
            telefono="+56912345678",
            motivo_consulta="Prueba"
        )
        cita_c = Cita.objects.create(
            cliente=cliente_c,
            servicio=self.servicio,
            fecha_hora=fecha_futura_tz,
            estado='X',
            estado_pago='NO'
        )

        # Intentar agendar en el mismo slot. agendar_cita() debe limpiar la cancelada y reservar.
        post_data = {
            'nombre': 'Nuevo Cliente',
            'email': 'n@gmail.com',
            'telefono': '+56987654321',
            'rut': '12345678-5',
            'motivo_consulta': 'Consulta real',
            'fecha_hora_reserva': fecha_str,
            'servicio': self.servicio.nombre
        }

        # Mockear mercadopago SDK para que no haga llamada a la API externa
        import unittest.mock as mock
        with mock.patch('mercadopago.SDK') as mock_sdk:
            instance = mock_sdk.return_value
            instance.preference.return_value.create.return_value = {
                'status': 201,
                'response': {
                    'id': 'mock-pref-id-123',
                    'sandbox_init_point': 'http://mock-sandbox-url',
                    'init_point': 'http://mock-url'
                }
            }

            response = self.client.post(reverse('agendar_cita'), post_data)
            # Si falla, podemos ver qué mensajes devolvió para depurar
            if response.status_code != 302 or 'mock' not in response.url:
                from django.contrib.messages import get_messages
                messages = [str(m) for m in get_messages(response.wsgi_request)]
                print("ERRORES OBSERVADOS EN EL FORMULARIO/VISTA:", messages)

            # Debe redirigir a Mercado Pago
            self.assertEqual(response.status_code, 302)
            self.assertIn('mock', response.url)

            # Verificar que la cita vieja cancelada fue eliminada
            self.assertFalse(Cita.objects.filter(id=cita_c.id).exists())

            # Verificar que la nueva cita fue creada y está activa (pendiente de pago)
            cita_nueva = Cita.objects.get(fecha_hora=fecha_futura_tz)
            self.assertEqual(cita_nueva.cliente.nombre, 'Nuevo Cliente')
            self.assertEqual(cita_nueva.estado, 'P')
            self.assertEqual(cita_nueva.mp_preference_id, 'mock-pref-id-123')

    def test_expirar_citas_command(self):
        fecha_futura = datetime.combine(self.hoy, datetime.strptime("12:00", "%H:%M").time())
        fecha_futura_tz = timezone.make_aware(fecha_futura)

        cliente = Cliente.objects.create(
            nombre="Expirable",
            rut="12345678-5",
            email="e@gmail.com",
            telefono="+56912345678",
            motivo_consulta="Prueba"
        )
        
        cita = Cita.objects.create(
            cliente=cliente,
            servicio=self.servicio,
            fecha_hora=fecha_futura_tz,
            estado='P',
            estado_pago='NO'
        )
        Cita.objects.filter(id=cita.id).update(creada_en=timezone.now() - timedelta(minutes=45))

        # Cita confirmada (no debe expirar aunque sea vieja)
        cita_c = Cita.objects.create(
            cliente=cliente,
            servicio=self.servicio,
            fecha_hora=timezone.now() - timedelta(minutes=50),
            estado='C',
            estado_pago='PA'
        )

        # Cita reciente en el futuro (no debe expirar)
        cita_f = Cita.objects.create(
            cliente=cliente,
            servicio=self.servicio,
            fecha_hora=timezone.now() + timedelta(hours=2),
            estado='P',
            estado_pago='NO'
        )

        # Ejecutar el comando expirar_citas
        call_command('expirar_citas', minutes=30)

        # Refrescar de base de datos
        cita.refresh_from_db()
        cita_c.refresh_from_db()
        cita_f.refresh_from_db()

        self.assertEqual(cita.estado, 'X')
        self.assertEqual(cita_c.estado, 'C')
        self.assertEqual(cita_f.estado, 'P')

    def test_reserva_gratuita(self):
        # Crear servicio gratuito
        servicio_gratis = Servicio.objects.create(
            nombre="Charla Inicial Gratis",
            descripcion="Charla gratuita",
            precio=0
        )

        fecha_futura = datetime.combine(self.hoy, datetime.strptime("12:30", "%H:%M").time())
        fecha_futura_tz = timezone.make_aware(fecha_futura)
        fecha_str = fecha_futura_tz.strftime('%Y-%m-%d %H:%M:%S')

        post_data = {
            'nombre': 'Cliente Gratis',
            'email': 'gratis@gmail.com',
            'telefono': '+56987654321',
            'rut': '12345678-5',
            'motivo_consulta': 'Consulta gratis',
            'fecha_hora_reserva': fecha_str,
            'servicio': servicio_gratis.nombre
        }

        response = self.client.post(reverse('agendar_cita'), post_data)

        # Debe redirigir de inmediato al éxito (pago_exito)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('pago_exito'), response.url)

        # Verificar que la cita fue creada como Confirmada ('C') y Pagada ('PA')
        cita = Cita.objects.get(fecha_hora=fecha_futura_tz)
        self.assertEqual(cita.cliente.nombre, 'Cliente Gratis')
        self.assertEqual(cita.estado, 'C')
        self.assertEqual(cita.estado_pago, 'PA')
        self.assertTrue(cita.transaccion_id.startswith('FREE-'))
