"""Cálculo de histórico y previsión de demanda para el panel de administración."""

from collections import Counter
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Booking


DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
HORAS = tuple(range(9, 21))  # Inicio de las franjas de reserva: 09:00-20:00


def _fecha_local(valor):
    """Devuelve la fecha local de un date/datetime (sin conversiones si es naive)."""
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            return timezone.localtime(valor).date()
        return valor.date()
    return valor


def _hora_local(valor):
    if timezone.is_aware(valor):
        return timezone.localtime(valor).hour
    return valor.hour


def _medianoche(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


def _rango_fechas(inicio, fin):
    actual = inicio
    while actual <= fin:
        yield actual
        actual += timedelta(days=1)


def _porcentaje(valor, maximo):
    return round(100 * valor / maximo) if maximo else 0


def _barras(contador, etiquetas):
    """Convierte un Counter en filas listas para el template."""
    maximo = max(contador.values(), default=0)
    return [
        {
            "etiqueta": etiqueta,
            "total": contador.get(clave, 0),
            "porcentaje": _porcentaje(contador.get(clave, 0), maximo),
        }
        for clave, etiqueta in etiquetas
    ]


def _reservas_historicas(inicio_historial, hoy):
    """Reservas cuya fecha local de uso está en el histórico solicitado."""
    reservas = list(
        Booking.objects.filter(
            start_time__gte=_medianoche(inicio_historial),
            start_time__lt=_medianoche(hoy),
        )
        .select_related("resource")
        .order_by("start_time")
    )
    return [
        reserva
        for reserva in reservas
        if inicio_historial <= _fecha_local(reserva.start_time) < hoy
    ]


def _semanas_historicas(inicio_historial, semanas_historial, por_dia):
    semanas = []
    for indice in range(semanas_historial):
        inicio = inicio_historial + timedelta(weeks=indice)
        fin = inicio + timedelta(days=6)
        total = sum(por_dia.get(fecha, 0) for fecha in _rango_fechas(inicio, fin))
        semanas.append({
            "etiqueta": f"{inicio:%d/%m}–{fin:%d/%m}",
            "total": total,
        })

    maximo = max((semana["total"] for semana in semanas), default=0)
    for semana in semanas:
        semana["porcentaje"] = _porcentaje(semana["total"], maximo)
    return semanas


def _dias_recientes(inicio_historial, hoy, por_dia):
    inicio = max(inicio_historial, hoy - timedelta(days=14))
    dias = []
    for fecha in _rango_fechas(inicio, hoy - timedelta(days=1)):
        dias.append({
            "etiqueta": f"{DIAS_CORTOS[fecha.weekday()]} {fecha:%d/%m}",
            "total": por_dia.get(fecha, 0),
        })

    maximo = max((dia["total"] for dia in dias), default=0)
    for dia in dias:
        dia["porcentaje"] = _porcentaje(dia["total"], maximo)
    return dias


def _recursos(por_recurso, total_historico):
    maximo = max(por_recurso.values(), default=0)
    return [
        {
            "nombre": nombre,
            "total": total,
            "porcentaje": _porcentaje(total, total_historico),
            "barra": _porcentaje(total, maximo),
        }
        for nombre, total in por_recurso.most_common()
    ]


def _promedios_por_dia(inicio_historial, semanas_historial, por_dia_semana):
    ocurrencias = Counter(
        (inicio_historial + timedelta(days=indice)).weekday()
        for indice in range(semanas_historial * 7)
    )
    return {
        indice: (
            por_dia_semana.get(indice, 0) / ocurrencias[indice]
            if ocurrencias[indice]
            else 0
        )
        for indice in range(7)
    }


def _prevision_semanas(inicio_semana_actual, semanas_futuras, promedios):
    inicio_prevision = inicio_semana_actual + timedelta(weeks=1)
    semanas = []
    for indice in range(semanas_futuras):
        inicio = inicio_prevision + timedelta(weeks=indice)
        dias = []
        total_semanal = 0
        for desplazamiento in range(7):
            fecha = inicio + timedelta(days=desplazamiento)
            prediccion = promedios[fecha.weekday()]
            total_semanal += prediccion
            dias.append({
                "etiqueta": DIAS_CORTOS[fecha.weekday()],
                "fecha": fecha,
                "prediccion": round(prediccion, 1),
            })
        semanas.append({
            "etiqueta": f"{inicio:%d/%m}–{(inicio + timedelta(days=6)):%d/%m}",
            "total": round(total_semanal, 1),
            "dias": dias,
        })

    maximo = max((semana["total"] for semana in semanas), default=0)
    for semana in semanas:
        semana["porcentaje"] = _porcentaje(semana["total"], maximo)
    return semanas


def construir_datos_prevision(hoy=None, semanas_historial=8, semanas_futuras=4):
    """
    Construye los datos del dashboard de demanda.

    La demanda histórica se cuenta por la fecha de inicio de cada reserva,
    no por la fecha en que se creó. La previsión usa la media de reservas
    de cada día de la semana en las últimas ``semanas_historial`` semanas
    completas: cada día futuro toma el promedio de su mismo día de semana.
    """
    if semanas_historial < 1 or semanas_futuras < 1:
        raise ValueError("Las semanas deben ser mayores que cero.")

    hoy = _fecha_local(hoy or timezone.localdate())
    inicio_semana_actual = hoy - timedelta(days=hoy.weekday())
    inicio_historial = inicio_semana_actual - timedelta(weeks=semanas_historial)

    reservas = _reservas_historicas(inicio_historial, hoy)
    fechas = [_fecha_local(reserva.start_time) for reserva in reservas]
    reservas_completas = [
        reserva for reserva in reservas
        if _fecha_local(reserva.start_time) < inicio_semana_actual
    ]
    fechas_completas = [_fecha_local(reserva.start_time) for reserva in reservas_completas]

    por_dia = Counter(fechas)
    por_hora = Counter(_hora_local(reserva.start_time) for reserva in reservas_completas)
    por_recurso = Counter(reserva.resource.name for reserva in reservas_completas)
    por_dia_semana = Counter(fecha.weekday() for fecha in fechas_completas)
    total_historico = len(fechas_completas)

    prom = _promedios_por_dia(inicio_historial, semanas_historial, por_dia_semana)
    prevision = _prevision_semanas(inicio_semana_actual, semanas_futuras, prom)
    horas_top = [
        {"hora": f"{hora:02d}:00", "total": total}
        for hora, total in por_hora.most_common(3)
        if total
    ]
    dias_top = [
        {"nombre": DIAS_SEMANA[indice], "total": total}
        for indice, total in por_dia_semana.most_common(3)
        if total
    ]

    return {
        "hoy": hoy,
        "semanas_historial": semanas_historial,
        "semanas_futuras": semanas_futuras,
        "total_historico": total_historico,
        "promedio_semanal": round(total_historico / semanas_historial, 1),
        "hay_historial": bool(fechas_completas),
        "por_semana": _semanas_historicas(inicio_historial, semanas_historial, por_dia),
        "por_dia": _dias_recientes(inicio_historial, hoy, por_dia),
        "por_hora": _barras(por_hora, [(hora, f"{hora:02d}:00") for hora in HORAS]),
        "por_dia_semana": _barras(
            por_dia_semana,
            [(indice, DIAS_SEMANA[indice]) for indice in range(7)],
        ),
        "por_recurso": _recursos(por_recurso, total_historico),
        "horas_top": horas_top,
        "dias_top": dias_top,
        "pico_hora": horas_top[0] if horas_top else None,
        "pico_dia": dias_top[0] if dias_top else None,
        "prevision_semanas": prevision,
        "prevision_total": round(sum(semana["total"] for semana in prevision), 1),
    }
