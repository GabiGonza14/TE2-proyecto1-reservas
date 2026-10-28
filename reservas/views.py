import json
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.dateparse import parse_date, parse_datetime
from django.contrib.auth import authenticate, login, logout
from django.contrib import admin as django_admin
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Resource, Booking, Availability, PaymentMethod
from .disponibilidad import calcular_dias_disponibilidad, obtener_eventos_disponibilidad
from .pagos import PagoInvalido, metodo_vigente, validar_tarjeta
from .prevision import construir_datos_prevision


# Horario por defecto (si no hay Availability definida)
DEFAULT_START = time(9, 0)   # 09:00
DEFAULT_END = time(21, 0)    # 21:00

# Un mes de calendario ocupa como máximo 42 días. Se permite un margen para
# vistas semanales con navegación, pero se evita consultar años completos.
MAX_DIAS_DISPONIBILIDAD = 62


def calendario(request, resource_id):
    """
    Muestra un calendario semanal de reservas para un recurso.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    reservas = Booking.objects.filter(
        resource=resource,
        start_time__date__gte=inicio_semana,
        start_time__date__lte=inicio_semana + timedelta(days=6)
    ).order_by('start_time')

    reservas_por_dia = {date_format(dia, 'Y-m-d'): [] for dia in dias_semana}
    for reserva in reservas:
        clave = date_format(reserva.start_time, 'Y-m-d')
        reservas_por_dia[clave].append(reserva)

    return render(request, 'reservas/calendario.html', {
        'resource': resource,
        'dias_semana': dias_semana,
        'reservas_por_dia': reservas_por_dia,
    })


def calendario_navegable(request, resource_id):
    """
    Calendario semanal con botones de semana anterior/siguiente.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    hoy = datetime.today()
    delta = 0
    if request.GET.get('week') == 'prev':
        delta = -7
    elif request.GET.get('week') == 'next':
        delta = 7

    inicio_semana = (hoy - timedelta(days=hoy.weekday())) + timedelta(days=delta)
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    reservas = Booking.objects.filter(
        resource=resource,
        start_time__date__gte=inicio_semana,
        start_time__date__lte=inicio_semana + timedelta(days=6)
    ).order_by('start_time')

    reservas_por_dia = {date_format(dia, 'Y-m-d'): [] for dia in dias_semana}
    for reserva in reservas:
        clave = date_format(reserva.start_time, 'Y-m-d')
        reservas_por_dia[clave].append(reserva)

    return render(request, 'reservas/calendario.html', {
        'resource': resource,
        'dias_semana': dias_semana,
        'reservas_por_dia': reservas_por_dia,
    })


@ensure_csrf_cookie
def calendario_full(request, resource_id):
    """
    Calendario interactivo con FullCalendar.

    Los eventos y el estado de los días se cargan por rango desde
    ``api_disponibilidad``; no se envía todo el histórico al template.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    metodos = []
    if request.user.is_authenticated:
        metodos = [
            {'id': m.id, 'label': str(m), 'vigente': metodo_vigente(m)}
            for m in request.user.payment_methods.all()
        ]

    return render(request, 'reservas/calendario_full.html', {
        'resource': resource,
        'metodos_pago': metodos,
        'is_authenticated': request.user.is_authenticated,
    })



class _ErrorReserva(Exception):
    """Error de validación de una reserva, con el código HTTP a devolver."""

    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.status = status


def _resolver_pago(data, user):
    """
    Devuelve (metodo_guardado, datos_tarjeta) a partir del cuerpo de la petición.
    Lanza _ErrorReserva si el pago falta o no es válido.
    """
    if data.get('payment_method_id'):
        metodo = PaymentMethod.objects.filter(id=data['payment_method_id'], user=user).first()
        if metodo is None:
            raise _ErrorReserva('Método de pago no encontrado.', status=404)
        if not metodo_vigente(metodo):
            raise _ErrorReserva('El método de pago guardado está vencido.')
        return metodo, None
    if data.get('card'):
        try:
            return None, validar_tarjeta(data['card'])
        except PagoInvalido as e:
            raise _ErrorReserva(str(e)) from e
    raise _ErrorReserva('Debes indicar un método de pago.')


def _semanas_repeticion(valor):
    """Valida `repeat_weeks`: un entero mayor o igual que 0 (0 = sin repetición)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise _ErrorReserva('Las semanas de repetición deben ser un número entero mayor o igual que 0.')
    try:
        semanas = int(valor)
    except ValueError as e:
        raise _ErrorReserva('Las semanas de repetición deben ser un número entero mayor o igual que 0.') from e
    if semanas < 0:
        raise _ErrorReserva('Las semanas de repetición deben ser un número entero mayor o igual que 0.')
    return semanas


def _buscar_conflicto(resource_id, franjas):
    """Devuelve el mensaje del primer conflicto de reserva o bloqueo, o None."""
    for i, (start, end) in enumerate(franjas):
        if Booking.objects.filter(
            resource_id=resource_id,
            start_time__lt=end,
            end_time__gt=start,
        ).exists():
            return f'Conflicto: hay una reserva en la semana {i + 1} ({start}).'
        if Availability.objects.filter(
            resource_id=resource_id,
            start_time__lt=end,
            end_time__gt=start,
        ).exists():
            return f'Conflicto: la franja de la semana {i + 1} ({start}) está bloqueada.'
    return None


def _fecha_de_rango(valor, nombre):
    """Parsea una fecha ISO (con o sin hora) y la devuelve con zona horaria."""
    if not valor:
        raise ValueError(f'Falta el parámetro {nombre}.')
    fecha = parse_datetime(valor)
    if fecha is None:
        dia = parse_date(valor)
        if dia is None:
            raise ValueError(f'El parámetro {nombre} no es una fecha válida.')
        fecha = timezone.make_aware(datetime.combine(dia, time.min))
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return fecha


@require_GET
def api_disponibilidad(request, resource_id):
    """Devuelve días y eventos de disponibilidad para un rango de fechas."""
    resource = get_object_or_404(Resource, id=resource_id)
    try:
        inicio = _fecha_de_rango(request.GET.get('start'), 'start')
        fin = _fecha_de_rango(request.GET.get('end'), 'end')
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    if inicio >= fin:
        return JsonResponse(
            {'success': False, 'error': 'El rango de fechas no es válido.'},
            status=400,
        )
    if fin - inicio > timedelta(days=MAX_DIAS_DISPONIBILIDAD):
        return JsonResponse(
            {
                'success': False,
                'error': (
                    f'El rango no puede superar {MAX_DIAS_DISPONIBILIDAD} días.'
                ),
            },
            status=400,
        )

    return JsonResponse({
        'success': True,
        'resource_id': resource.id,
        'start': inicio.isoformat(),
        'end': fin.isoformat(),
        'dias': calcular_dias_disponibilidad(resource, inicio, fin),
        'eventos': obtener_eventos_disponibilidad(resource, inicio, fin),
    })


def api_crear_reserva(request):
    """
    Endpoint para crear una nueva reserva, con soporte para repeticiones semanales.

    Requiere un pago (simulado): un método guardado del usuario (`payment_method_id`)
    o una tarjeta nueva (`card`), que se guarda si `card.save` es verdadero.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Debes iniciar sesión para reservar.'}, status=403)
    try:
        data = json.loads(request.body)
        resource_id = data.get('resource_id')
        start_time = parse_datetime(data.get('start_time'))
        end_time = parse_datetime(data.get('end_time'))
        repeat_weeks = _semanas_repeticion(data.get('repeat_weeks', 0))

        # 1. Validar el pago antes de tocar la base de datos
        metodo_guardado, datos_tarjeta = _resolver_pago(data, request.user)

        # 2. Comprobar todas las semanas antes de crear nada
        franjas = [
            (start_time + timedelta(weeks=i), end_time + timedelta(weeks=i))
            for i in range(repeat_weeks + 1)
        ]
        conflicto = _buscar_conflicto(resource_id, franjas)
        if conflicto:
            return JsonResponse({'success': False, 'error': conflicto}, status=400)

        # 3. Crear todo junto: o se guardan todas las reservas (y la tarjeta) o ninguna
        with transaction.atomic():
            if datos_tarjeta and data['card'].get('save'):
                metodo_guardado = PaymentMethod.objects.create(user=request.user, **datos_tarjeta)
            for start, end in franjas:
                Booking.objects.create(
                    user=request.user,
                    resource_id=resource_id,
                    start_time=start,
                    end_time=end,
                    payment_method=metodo_guardado,
                )

        return JsonResponse({
            'success': True,
            'reservas': [{'start': s.isoformat(), 'end': e.isoformat()} for s, e in franjas],
            'payment_method': str(metodo_guardado) if metodo_guardado else None,
            'payment_method_id': metodo_guardado.id if metodo_guardado else None,
        })
    except _ErrorReserva as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=e.status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def metodos_pago(request):
    """
    Lista los métodos de pago guardados del usuario y permite eliminarlos.
    """
    if request.method == 'POST':
        metodo = get_object_or_404(PaymentMethod, id=request.POST.get('metodo_id'), user=request.user)
        metodo.delete()
        messages.success(request, 'Método de pago eliminado.')
        return redirect('metodos_pago')
    return render(request, 'reservas/metodos_pago.html', {
        'metodos': request.user.payment_methods.all(),
    })


@require_GET
@staff_member_required
def prevision_demanda(request):
    """Dashboard de histórico y previsión de demanda, solo para staff."""
    contexto = django_admin.site.each_context(request)
    contexto.update(construir_datos_prevision())
    contexto['title'] = 'Previsión de demanda'
    return render(request, 'reservas/prevision_demanda.html', contexto)


def login_view(request):
    """
    Vista para el inicio de sesión de usuarios.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('/')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, 'reservas/login.html')


def logout_view(request):
    """
    Cerrar sesión.
    """
    logout(request)
    return redirect('/login/')

def api_reservas(request, resource_id):
    """
    API que devuelve todas las reservas de un recurso en formato JSON.
    """
    reservas = Booking.objects.filter(resource_id=resource_id).order_by('start_time')
    eventos = [
        {
            "title": "Reservado",
            "start": reserva.start_time.isoformat(),
            "end": reserva.end_time.isoformat(),
            "color": "#10b981",  # Verde
        }
        for reserva in reservas
    ]
    return JsonResponse(eventos, safe=False)

def home(request):
    """
    Vista principal que muestra todas las pistas (resources).
    """
    resources = Resource.objects.all()  # Obtenemos todas las pistas
    return render(request, 'reservas/home.html', {'resources': resources})


