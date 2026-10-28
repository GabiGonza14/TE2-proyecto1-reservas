"""Cálculo de disponibilidad diaria para el calendario de reservas."""

from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Availability, Booking


HORA_INICIO = 9
HORA_FIN = 21
FRANJAS_POR_DIA = HORA_FIN - HORA_INICIO


def _normalizar_fecha(valor):
    """Convierte una fecha naive a la zona horaria local del proyecto."""
    if timezone.is_naive(valor):
        return timezone.make_aware(valor)
    return valor


def _fechas_del_rango(inicio, fin):
    """Devuelve las fechas locales cubiertas por un rango semiabierto."""
    inicio_local = timezone.localtime(inicio)
    fin_local = timezone.localtime(fin)
    fecha_inicio = inicio_local.date()
    fecha_fin = fin_local.date()
    if fin_local.time() != time(0, 0):
        fecha_fin += timedelta(days=1)

    fecha = fecha_inicio
    while fecha < fecha_fin:
        yield fecha
        fecha += timedelta(days=1)


def _solapa(intervalos, inicio, fin):
    """Indica si alguna franja de ``intervalos`` se cruza con [inicio, fin)."""
    return any(
        inicio_intervalo < fin and fin_intervalo > inicio
        for inicio_intervalo, fin_intervalo in intervalos
    )


def calcular_dias_disponibilidad(resource, inicio, fin, hoy=None, ahora=None):
    """
    Calcula el estado de cada día del rango para un recurso.

    Cada día se divide en franjas de una hora entre 09:00 y 21:00. Una franja
    cuenta como reservada si hay una reserva que la cruza y como bloqueada si
    hay un ``Availability`` que la cruza. En el día actual, las franjas ya
    terminadas también se descuentan. El estado del día puede ser
    ``disponible``, ``parcial``, ``completo`` o ``pasado``.
    """
    inicio = _normalizar_fecha(inicio)
    fin = _normalizar_fecha(fin)
    ahora = _normalizar_fecha(ahora or timezone.now())
    hoy = hoy or timezone.localdate(ahora)

    reservas = list(
        Booking.objects.filter(
            resource=resource,
            start_time__lt=fin,
            end_time__gt=inicio,
        ).values_list("start_time", "end_time")
    )
    bloqueos = list(
        Availability.objects.filter(
            resource=resource,
            start_time__lt=fin,
            end_time__gt=inicio,
        ).values_list("start_time", "end_time")
    )

    dias = []
    for fecha in _fechas_del_rango(inicio, fin):
        franjas_reservadas = 0
        franjas_bloqueadas = 0
        franjas_pasadas = 0
        for hora in range(HORA_INICIO, HORA_FIN):
            inicio_franja = timezone.make_aware(datetime.combine(fecha, time(hora)))
            fin_franja = inicio_franja + timedelta(hours=1)
            if fecha == hoy and fin_franja <= ahora:
                franjas_pasadas += 1
            elif _solapa(reservas, inicio_franja, fin_franja):
                franjas_reservadas += 1
            elif _solapa(bloqueos, inicio_franja, fin_franja):
                franjas_bloqueadas += 1

        franjas_libres = (
            FRANJAS_POR_DIA - franjas_reservadas - franjas_bloqueadas - franjas_pasadas
        )
        if fecha < hoy:
            estado = "pasado"
        elif franjas_libres <= 0:
            estado = "completo"
        elif franjas_libres < FRANJAS_POR_DIA:
            estado = "parcial"
        else:
            estado = "disponible"

        dias.append({
            "fecha": fecha.isoformat(),
            "estado": estado,
            "franjas_libres": franjas_libres,
            "franjas_reservadas": franjas_reservadas,
            "franjas_bloqueadas": franjas_bloqueadas,
            "franjas_pasadas": franjas_pasadas,
            "total_franjas": FRANJAS_POR_DIA,
        })

    return dias


def obtener_eventos_disponibilidad(resource, inicio, fin):
    """Devuelve reservas y bloqueos en el rango para FullCalendar."""
    inicio = _normalizar_fecha(inicio)
    fin = _normalizar_fecha(fin)

    eventos = []
    reservas = Booking.objects.filter(
        resource=resource,
        start_time__lt=fin,
        end_time__gt=inicio,
    )
    for reserva in reservas:
        eventos.append({
            "id": f"reserva-{reserva.id}",
            "start": reserva.start_time.isoformat(),
            "end": reserva.end_time.isoformat(),
            "title": "Reservado",
            "color": "#10b981",
            "extendedProps": {"tipo": "reserva", "booking_id": reserva.id},
        })

    bloqueos = Availability.objects.filter(
        resource=resource,
        start_time__lt=fin,
        end_time__gt=inicio,
    )
    for bloqueo in bloqueos:
        eventos.append({
            "id": f"bloqueo-{bloqueo.id}",
            "start": bloqueo.start_time.isoformat(),
            "end": bloqueo.end_time.isoformat(),
            "title": "Bloqueo administrativo",
            "color": "#ef4444",
            "extendedProps": {"tipo": "bloqueo", "availability_id": bloqueo.id},
        })

    return eventos
