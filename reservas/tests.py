import json
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

from .models import Booking, Resource


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
