import json
import os
import subprocess
import sys
import warnings
from io import StringIO
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from .models import Booking, PaymentMethod, Resource
from .pagos import PagoInvalido, detectar_marca, validar_tarjeta


TARJETA_VALIDA = {
    "holder_name": "Ana Pérez",
    "number": "4242 4242 4242 4242",
    "exp_month": 12,
    "exp_year": datetime.now().year + 2,
    "cvv": "123",
}


def _dt(days=1, hour=10):
    """Fecha futura fija a una hora concreta (UTC)."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return (base + timedelta(days=days)).replace(hour=hour)


class BookingModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="clave-segura-123")
        self.resource = Resource.objects.create(name="Pista 1")

    def test_clean_rechaza_reserva_solapada(self):
        Booking.objects.create(
            user=self.user, resource=self.resource,
            start_time=_dt(hour=10), end_time=_dt(hour=11),
        )
        solapada = Booking(
            user=self.user, resource=self.resource,
            start_time=_dt(hour=10) + timedelta(minutes=30), end_time=_dt(hour=12),
        )
        with self.assertRaises(ValidationError):
            solapada.clean()

    def test_clean_permite_reservas_contiguas(self):
        Booking.objects.create(
            user=self.user, resource=self.resource,
            start_time=_dt(hour=10), end_time=_dt(hour=11),
        )
        contigua = Booking(
            user=self.user, resource=self.resource,
            start_time=_dt(hour=11), end_time=_dt(hour=12),
        )
        contigua.clean()  # no debe lanzar


class CrearReservaApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="clave-segura-123")
        self.resource = Resource.objects.create(name="Pista 1")
        self.url = reverse("api_crear_reserva")

    def _payload(self, start, end, repeat=0):
        return json.dumps({
            "resource_id": self.resource.id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "repeat_weeks": repeat,
            "card": TARJETA_VALIDA,
        })

    def _post(self, client, start, end, repeat=0, **extra):
        return client.post(
            self.url, self._payload(start, end, repeat),
            content_type="application/json", **extra,
        )

    def test_requiere_login(self):
        resp = self._post(self.client, _dt(hour=10), _dt(hour=11))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Booking.objects.exists())

    def test_crea_reserva(self):
        self.client.force_login(self.user)
        resp = self._post(self.client, _dt(hour=10), _dt(hour=11))
        self.assertTrue(resp.json()["success"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_rechaza_solapamiento(self):
        self.client.force_login(self.user)
        self._post(self.client, _dt(hour=10), _dt(hour=11))
        resp = self._post(self.client, _dt(hour=10), _dt(hour=11))
        self.assertFalse(resp.json()["success"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_reserva_recurrente_crea_una_por_semana(self):
        self.client.force_login(self.user)
        resp = self._post(self.client, _dt(hour=10), _dt(hour=11), repeat=2)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(Booking.objects.count(), 3)

    def test_sin_token_csrf_se_rechaza(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        resp = self._post(client, _dt(hour=10), _dt(hour=11))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Booking.objects.exists())

    def test_con_token_csrf_del_calendario_se_acepta(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("calendario_full", args=[self.resource.id]))
        token = client.cookies["csrftoken"].value
        resp = self._post(client, _dt(hour=10), _dt(hour=11), HTTP_X_CSRFTOKEN=token)
        self.assertTrue(resp.json()["success"])

    def test_metodo_get_no_permitido(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class VistasTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Pista 1")

    def test_home_lista_recursos(self):
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Pista 1")

    def test_calendario_full_recurso_inexistente_da_404(self):
        resp = self.client.get(reverse("calendario_full", args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_api_reservas_devuelve_json(self):
        user = User.objects.create_user("ana", password="clave-segura-123")
        Booking.objects.create(
            user=user, resource=self.resource,
            start_time=_dt(hour=10), end_time=_dt(hour=11),
        )
        resp = self.client.get(reverse("api_reservas", args=[self.resource.id]))
        self.assertEqual(len(resp.json()), 1)


class ReservasDemoTests(TestCase):
    def test_reservas_demo_usan_fechas_con_zona_horaria(self):
        """Antes el comando usaba datetime.now() sin zona horaria y Django avisaba con RuntimeWarning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            call_command("crear_reservas_demo", stdout=StringIO())
        self.assertEqual(Booking.objects.count(), 15)

    def test_reservas_demo_en_horario_local_del_calendario(self):
        """Las reservas demo deben caer entre 09:00 y 21:00 en la hora local del proyecto."""
        call_command("crear_reservas_demo", stdout=StringIO())
        for reserva in Booking.objects.all():
            self.assertGreaterEqual(dj_timezone.localtime(reserva.start_time).hour, 9)
            self.assertLessEqual(dj_timezone.localtime(reserva.end_time).hour, 21)

    def test_zona_horaria_por_defecto_es_panama(self):
        self.assertEqual(settings.TIME_ZONE, "America/Panama")


class ConfiguracionSeguraTests(TestCase):
    """Los settings se importan en un proceso aparte para probar cada combinación de variables."""

    CODIGO = (
        "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_reservas.settings');"
        "from django.conf import settings; print(settings.DEBUG, settings.SECRET_KEY)"
    )

    def _importar_settings(self, **variables):
        env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        env.update(variables)
        return subprocess.run(
            [sys.executable, "-c", self.CODIGO],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True,
        )

    def test_sin_variables_falla_en_vez_de_usar_clave_insegura(self):
        resultado = self._importar_settings()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", resultado.stderr)

    def test_con_secret_key_debug_queda_apagado_por_defecto(self):
        resultado = self._importar_settings(DJANGO_SECRET_KEY="clave-de-prueba")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout.strip(), "False clave-de-prueba")

    def test_en_desarrollo_usa_clave_local(self):
        resultado = self._importar_settings(DJANGO_DEBUG="True")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue(resultado.stdout.startswith("True django-insecure-"))


class ValidarTarjetaTests(TestCase):
    def test_tarjeta_valida_devuelve_solo_datos_guardables(self):
        datos = validar_tarjeta(TARJETA_VALIDA)
        self.assertEqual(datos["brand"], "Visa")
        self.assertEqual(datos["last4"], "4242")
        self.assertNotIn("number", datos)
        self.assertNotIn("cvv", datos)

    def test_numero_que_no_pasa_luhn_se_rechaza(self):
        with self.assertRaises(PagoInvalido):
            validar_tarjeta({**TARJETA_VALIDA, "number": "4242 4242 4242 4241"})

    def test_tarjeta_vencida_se_rechaza(self):
        with self.assertRaises(PagoInvalido):
            validar_tarjeta({**TARJETA_VALIDA, "exp_month": 1, "exp_year": 2020})

    def test_cvv_invalido_se_rechaza(self):
        with self.assertRaises(PagoInvalido):
            validar_tarjeta({**TARJETA_VALIDA, "cvv": "12"})

    def test_detecta_marcas(self):
        self.assertEqual(detectar_marca("5555555555554444"), "Mastercard")
        self.assertEqual(detectar_marca("378282246310005"), "Amex")


class PagoGuardadoTests(TestCase):
    """HU1: reservar con datos de pago guardados."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", password="clave-segura-123")
        self.beto = User.objects.create_user("beto", password="clave-segura-123")
        self.resource = Resource.objects.create(name="Pista 1")
        self.url = reverse("api_crear_reserva")
        self.client.force_login(self.ana)

    def _reservar(self, hour=10, repeat=0, **pago):
        return self.client.post(self.url, json.dumps({
            "resource_id": self.resource.id,
            "start_time": _dt(hour=hour).isoformat(),
            "end_time": _dt(hour=hour + 1).isoformat(),
            "repeat_weeks": repeat,
            **pago,
        }), content_type="application/json")

    def _metodo(self, user, **extra):
        datos = {"holder_name": "X", "brand": "Visa", "last4": "4242",
                 "exp_month": 12, "exp_year": datetime.now().year + 2, **extra}
        return PaymentMethod.objects.create(user=user, **datos)

    def test_sin_pago_no_se_reserva(self):
        resp = self._reservar()
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_guardar_tarjeta_solo_guarda_datos_no_sensibles(self):
        resp = self._reservar(card={**TARJETA_VALIDA, "save": True})
        self.assertTrue(resp.json()["success"])
        metodo = PaymentMethod.objects.get(user=self.ana)
        self.assertEqual((metodo.brand, metodo.last4), ("Visa", "4242"))
        campos = {f.name for f in PaymentMethod._meta.get_fields()}
        self.assertFalse({"number", "cvv"} & campos)
        self.assertEqual(Booking.objects.get().payment_method, metodo)

    def test_sin_marcar_guardar_no_se_guarda_la_tarjeta(self):
        resp = self._reservar(card={**TARJETA_VALIDA, "save": False})
        self.assertTrue(resp.json()["success"])
        self.assertFalse(PaymentMethod.objects.exists())

    def test_reserva_en_un_clic_con_metodo_guardado(self):
        metodo = self._metodo(self.ana)
        resp = self._reservar(payment_method_id=metodo.id)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(Booking.objects.get().payment_method, metodo)

    def test_no_puede_usar_metodo_de_otro_usuario(self):
        ajeno = self._metodo(self.beto)
        resp = self._reservar(payment_method_id=ajeno.id)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Booking.objects.exists())

    def test_metodo_guardado_vencido_se_rechaza(self):
        vencido = self._metodo(self.ana, exp_month=1, exp_year=2020)
        resp = self._reservar(payment_method_id=vencido.id)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_tarjeta_invalida_no_crea_reserva_ni_guarda(self):
        resp = self._reservar(card={**TARJETA_VALIDA, "number": "1234", "save": True})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(PaymentMethod.objects.exists())

    def test_conflicto_no_guarda_la_tarjeta(self):
        self._reservar(card=TARJETA_VALIDA)
        resp = self._reservar(card={**TARJETA_VALIDA, "save": True})
        self.assertFalse(resp.json()["success"])
        self.assertFalse(PaymentMethod.objects.exists())

    def test_recurrente_con_conflicto_no_crea_ninguna(self):
        otra = _dt(hour=10) + timedelta(weeks=1)
        Booking.objects.create(user=self.beto, resource=self.resource,
                               start_time=otra, end_time=otra + timedelta(hours=1))
        resp = self.client.post(self.url, json.dumps({
            "resource_id": self.resource.id,
            "start_time": _dt(hour=10).isoformat(),
            "end_time": _dt(hour=11).isoformat(),
            "repeat_weeks": 2,
            "card": {**TARJETA_VALIDA, "save": True},
        }), content_type="application/json")
        self.assertFalse(resp.json()["success"])
        self.assertEqual(Booking.objects.filter(user=self.ana).count(), 0)
        self.assertFalse(PaymentMethod.objects.exists())

    def test_semanas_de_repeticion_invalidas_se_rechazan(self):
        # Revisión de Derlin en PR #8: con -1 respondía éxito sin reservas pero guardaba la tarjeta
        for repeat in (-1, "abc", 1.5, None, True):
            with self.subTest(repeat=repeat):
                resp = self._reservar(repeat=repeat, card={**TARJETA_VALIDA, "save": True})
                self.assertEqual(resp.status_code, 400)
                self.assertFalse(resp.json()["success"])
                self.assertFalse(Booking.objects.exists())
                self.assertFalse(PaymentMethod.objects.exists())

    def test_pagina_lista_solo_mis_metodos(self):
        self._metodo(self.ana, last4="1111")
        self._metodo(self.beto, last4="9999")
        resp = self.client.get(reverse("metodos_pago"))
        self.assertContains(resp, "1111")
        self.assertNotContains(resp, "9999")

    def test_eliminar_metodo_propio(self):
        metodo = self._metodo(self.ana)
        self.client.post(reverse("metodos_pago"), {"metodo_id": metodo.id})
        self.assertFalse(PaymentMethod.objects.exists())

    def test_no_puede_eliminar_metodo_ajeno(self):
        ajeno = self._metodo(self.beto)
        resp = self.client.post(reverse("metodos_pago"), {"metodo_id": ajeno.id})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(PaymentMethod.objects.filter(id=ajeno.id).exists())

    def test_pagina_de_metodos_requiere_login(self):
        self.client.logout()
        resp = self.client.get(reverse("metodos_pago"))
        self.assertEqual(resp.status_code, 302)

    def test_calendario_ofrece_metodos_guardados(self):
        metodo = self._metodo(self.ana, last4="7777")
        resp = self.client.get(reverse("calendario_full", args=[self.resource.id]))
        self.assertContains(resp, "7777")
        self.assertEqual(resp.context["metodos_pago"][0]["id"], metodo.id)
