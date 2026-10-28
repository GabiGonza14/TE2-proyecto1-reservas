"""
Validación de pagos simulados.

No hay pasarela real: se valida el formato de la tarjeta y se devuelven solo
los datos que se pueden guardar (titular, marca, últimos 4 dígitos y vencimiento).
"""
import re

from django.utils import timezone


class PagoInvalido(Exception):
    pass


def _luhn_valido(numero):
    total = 0
    for i, digito in enumerate(reversed(numero)):
        n = int(digito)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def detectar_marca(numero):
    if numero.startswith('4'):
        return 'Visa'
    if numero[:2] in ('34', '37'):
        return 'Amex'
    if 51 <= int(numero[:2]) <= 55 or 2221 <= int(numero[:4]) <= 2720:
        return 'Mastercard'
    return 'Tarjeta'


def validar_tarjeta(datos):
    """
    Valida los datos de una tarjeta nueva y devuelve los campos guardables.
    Lanza PagoInvalido con un mensaje para el usuario si algo no es válido.
    """
    titular = (datos.get('holder_name') or '').strip()
    numero = re.sub(r'[\s-]', '', str(datos.get('number') or ''))
    cvv = str(datos.get('cvv') or '').strip()

    if not titular:
        raise PagoInvalido('Indica el nombre del titular de la tarjeta.')
    if not numero.isdigit() or not 13 <= len(numero) <= 19 or not _luhn_valido(numero):
        raise PagoInvalido('El número de tarjeta no es válido.')
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        raise PagoInvalido('El CVV no es válido.')
    try:
        mes = int(datos.get('exp_month'))
        anio = int(datos.get('exp_year'))
    except (TypeError, ValueError):
        raise PagoInvalido('La fecha de vencimiento no es válida.')
    if anio < 100:
        anio += 2000
    hoy = timezone.localdate()
    if not 1 <= mes <= 12 or (anio, mes) < (hoy.year, hoy.month):
        raise PagoInvalido('La tarjeta está vencida o la fecha no es válida.')

    return {
        'holder_name': titular,
        'brand': detectar_marca(numero),
        'last4': numero[-4:],
        'exp_month': mes,
        'exp_year': anio,
    }


def metodo_vigente(metodo):
    hoy = timezone.localdate()
    return (metodo.exp_year, metodo.exp_month) >= (hoy.year, hoy.month)
