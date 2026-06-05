"""
Management command: expirar_citas

Cancela automáticamente las citas que están en estado 'Pendiente' con
estado de pago 'No Pagado' que llevan más de N minutos sin completarse.

Esto libera los slots bloqueados por usuarios que abandonaron el
checkout de MercadoPago sin completar el pago.

Uso:
    python manage.py expirar_citas              # Expira citas > 30 min (default)
    python manage.py expirar_citas --minutes 15 # Expira citas > 15 min
    python manage.py expirar_citas --dry-run    # Solo muestra, no modifica

Programar con cron (cada 15 minutos):
    */15 * * * * cd /path/to/project && python manage.py expirar_citas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from asesorias.models import Cita


class Command(BaseCommand):
    help = 'Expira citas pendientes de pago que superan un tiempo límite'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Minutos de antigüedad para considerar una cita como expirada (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra las citas que se expirarían, sin modificarlas'
        )

    def handle(self, *args, **options):
        minutos = options['minutes']
        dry_run = options['dry_run']
        limite = timezone.now() - timedelta(minutes=minutos)

        # Buscar citas pendientes sin pago cuya hora ya pasó o fueron
        # creadas hace más del límite
        citas_expiradas = Cita.objects.filter(
            estado='P',
            estado_pago__in=['NO', 'PE'],
            fecha_hora__lt=limite
        )

        count = citas_expiradas.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] Se encontraron {count} citas para expirar:'))
            for cita in citas_expiradas[:20]:
                self.stdout.write(
                    f'  - Cita #{cita.id}: {cita.cliente.nombre} | '
                    f'{cita.fecha_hora.strftime("%d/%m/%Y %H:%M")} | '
                    f'Pago: {cita.get_estado_pago_display()}'
                )
            if count > 20:
                self.stdout.write(f'  ... y {count - 20} más')
        else:
            updated = citas_expiradas.update(estado='X')
            self.stdout.write(self.style.SUCCESS(
                f'{updated} citas expiradas correctamente '
                f'(antigüedad > {minutos} minutos)'))
