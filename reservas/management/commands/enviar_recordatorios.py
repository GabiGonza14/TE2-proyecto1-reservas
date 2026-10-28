"""Envía recordatorios de las reservas que empiezan en las próximas 24 h (HU5).

Pensado para ejecutarse periódicamente (cron o el Programador de tareas de Windows, p. ej. cada hora).
Cada reserva recibe un solo recordatorio: se marca antes de enviar, así dos ejecuciones simultáneas
no lo duplican, y se desmarca si el envío falla para reintentarlo en la siguiente ejecución.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from reservas.models import Booking
from reservas.notificaciones import enviar_aviso

VENTANA = timedelta(hours=24)


class Command(BaseCommand):
    help = "Envía recordatorios por correo de las reservas de las próximas 24 horas, sin duplicar envíos."

    def handle(self, *args, **options):
        ahora = timezone.now()
        pendientes = (
            Booking.objects.filter(
                start_time__gt=ahora,
                start_time__lte=ahora + VENTANA,
                recordatorio_enviado_en__isnull=True,
            )
            .exclude(user__email='')
            .select_related('user', 'resource')
        )
        enviados = 0
        for reserva in pendientes:
            # Reclamar la reserva de forma atómica: si otra ejecución ya la marcó, se salta.
            if not Booking.objects.filter(pk=reserva.pk, recordatorio_enviado_en__isnull=True).update(
                recordatorio_enviado_en=ahora
            ):
                continue
            franja = [(reserva.start_time, reserva.end_time)]
            if enviar_aviso('recordatorio', reserva.user, reserva.resource, franja):
                enviados += 1
            else:
                Booking.objects.filter(pk=reserva.pk).update(recordatorio_enviado_en=None)
        self.stdout.write(self.style.SUCCESS(f"Recordatorios enviados: {enviados}"))
