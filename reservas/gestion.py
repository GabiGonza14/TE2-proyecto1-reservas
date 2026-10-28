"""Reglas para cancelar o modificar una reserva existente (HU4)."""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .disponibilidad import HORA_FIN, HORA_INICIO


class ReservaNoGestionable(Exception):
    """La reserva no se puede cancelar ni modificar (ya empezó o queda poco tiempo)."""


def antelacion_minima():
    """Horas mínimas antes del inicio para cancelar o modificar (configurable)."""
    return timedelta(hours=settings.RESERVA_ANTELACION_MINIMA_HORAS)


def puede_gestionarse(reserva, ahora=None):
    """Indica si aún se puede cancelar o modificar la reserva."""
    ahora = ahora or timezone.now()
    return reserva.start_time - ahora >= antelacion_minima()


def _comprobar_gestionable(reserva, ahora):
    if not puede_gestionarse(reserva, ahora):
        horas = settings.RESERVA_ANTELACION_MINIMA_HORAS
        raise ReservaNoGestionable(
            f'Solo se puede cancelar o modificar una reserva con al menos {horas} h de antelación.'
        )


def cancelar_reserva(reserva, ahora=None):
    """Borra la reserva; la franja vuelve a quedar libre."""
    _comprobar_gestionable(reserva, ahora or timezone.now())
    reserva.delete()


def modificar_reserva(reserva, fecha, hora, ahora=None):
    """
    Mueve la reserva a ``fecha`` y ``hora`` (hora local de inicio) manteniendo su duración.

    Aplica las mismas validaciones que al crear (solapamiento y bloqueos) y exige
    que tanto la reserva actual como la nueva franja respeten la antelación mínima.
    """
    ahora = ahora or timezone.now()
    _comprobar_gestionable(reserva, ahora)

    duracion = reserva.end_time - reserva.start_time
    inicio = timezone.make_aware(datetime.combine(fecha, time(hora)))
    fin = inicio + duracion
    fin_del_dia = timezone.make_aware(datetime.combine(fecha, time(HORA_FIN)))
    if hora < HORA_INICIO or fin > fin_del_dia:
        raise ValidationError(f'La reserva debe quedar entre las {HORA_INICIO}:00 y las {HORA_FIN}:00.')
    if inicio - ahora < antelacion_minima():
        horas = settings.RESERVA_ANTELACION_MINIMA_HORAS
        raise ValidationError(f'La nueva franja debe empezar con al menos {horas} h de antelación.')

    with transaction.atomic():
        reserva.start_time = inicio
        reserva.end_time = fin
        # clean() ya rechaza solapamientos (incluida la franja idéntica); validate_unique solo
        # duplicaría el mensaje con el texto genérico de unique_together.
        reserva.full_clean(validate_unique=False)
        reserva.save(update_fields=['start_time', 'end_time'])
    return reserva
