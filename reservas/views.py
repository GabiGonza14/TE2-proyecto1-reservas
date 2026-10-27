import json
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.dateformat import format as date_format
from django.utils.dateparse import parse_datetime
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Resource, Booking, Availability, PaymentMethod
from .pagos import PagoInvalido, metodo_vigente, validar_tarjeta


# Horario por defecto (si no hay Availability definida)
DEFAULT_START = time(9, 0)   # 09:00
DEFAULT_END = time(21, 0)    # 21:00


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
    """
    resource = get_object_or_404(Resource, id=resource_id)

    reservas = Booking.objects.filter(resource=resource).order_by('start_time')
    bloqueos = Availability.objects.filter(resource=resource)

    # Lista de reservas
    reservas_json = [
        {
            "start": reserva.start_time.isoformat(),
            "end": reserva.end_time.isoformat(),
            "title": f"Reservado por {reserva.user.username}",
            "color": "#10b981",  # Verde reservas
        }
        for reserva in reservas
    ]

    # Lista de bloqueos (rojo)
    bloqueos_json = [
        {
            "start": bloqueo.start_time.isoformat(),
            "end": bloqueo.end_time.isoformat(),
        }
        for bloqueo in bloqueos
    ]

    metodos = []
    if request.user.is_authenticated:
        metodos = [
            {'id': m.id, 'label': str(m), 'vigente': metodo_vigente(m)}
            for m in request.user.payment_methods.all()
        ]

    return render(request, 'reservas/calendario_full.html', {
        'resource': resource,
        'metodos_pago': metodos,
        'reservas_json': json.dumps(reservas_json),
        'bloqueos_json': json.dumps(bloqueos_json),
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


def _buscar_conflicto(resource_id, franjas):
    """Devuelve el mensaje de conflicto de la primera franja ocupada, o None."""
    for i, (start, end) in enumerate(franjas):
        if Booking.objects.filter(resource_id=resource_id, start_time__lt=end, end_time__gt=start).exists():
            return f'Conflicto: hay una reserva en la semana {i + 1} ({start}).'
    return None


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
        repeat_weeks = int(data.get('repeat_weeks', 0))

        # 1. Validar el pago antes de tocar la base de datos
        metodo_guardado, datos_tarjeta = _resolver_pago(data, request.user)

        # 2. Comprobar todas las semanas antes de crear nada
        franjas = [
            (start_time + timedelta(weeks=i), end_time + timedelta(weeks=i))
            for i in range(repeat_weeks + 1)
        ]
        conflicto = _buscar_conflicto(resource_id, franjas)
        if conflicto:
            return JsonResponse({'success': False, 'error': conflicto})

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
            "title": f"Reservado por {reserva.user.username}",
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


