"""Correos de confirmación y recordatorio de reservas (HU5)."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import formats, timezone

logger = logging.getLogger(__name__)

ASUNTOS = {
    'creada': 'Reserva confirmada',
    'modificada': 'Reserva modificada',
    'cancelada': 'Reserva cancelada',
    'recordatorio': 'Recordatorio de tu reserva',
}


def describir_franja(inicio, fin):
    """Texto en hora local, p. ej. «jueves 5 de noviembre de 2026, 10:00–11:00»."""
    inicio, fin = timezone.localtime(inicio), timezone.localtime(fin)
    dia = formats.date_format(inicio, r'l j \d\e F \d\e Y')
    return f"{dia}, {inicio:%H:%M}–{fin:%H:%M}"


def enviar_aviso(tipo, user, recurso, franjas, anterior=None):
    """
    Envía al usuario el correo de ``tipo`` sobre ``recurso`` y sus ``franjas`` [(inicio, fin), ...].

    Devuelve True si se envió. Si el usuario no tiene correo o el envío falla, devuelve False sin
    lanzar excepción: un problema con el correo nunca debe deshacer ni bloquear la reserva.
    """
    if not user.email:
        return False
    cuerpo = render_to_string('reservas/correo_reserva.txt', {
        'tipo': tipo,
        'usuario': user.get_full_name() or user.username,
        'recurso': recurso.name,
        'franjas': [describir_franja(inicio, fin) for inicio, fin in franjas],
        'anterior': describir_franja(*anterior) if anterior else None,
        'antelacion_horas': settings.RESERVA_ANTELACION_MINIMA_HORAS,
    })
    try:
        send_mail(
            f"{ASUNTOS[tipo]}: {recurso.name}", cuerpo, settings.DEFAULT_FROM_EMAIL, [user.email],
        )
    except Exception:  # SMTP caído, credenciales mal configuradas, etc.
        logger.exception("No se pudo enviar el correo '%s' a %s", tipo, user.email)
        return False
    return True
