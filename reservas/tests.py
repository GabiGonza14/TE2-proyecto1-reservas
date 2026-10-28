import json
import os
import subprocess
import sys
import warnings
from io import StringIO
from datetime import date, datetime, time, timedelta, timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from .disponibilidad import calcular_dias_disponibilidad
from .models import Availability, Booking, PaymentMethod, Resource
from .pagos import PagoInvalido, detectar_marca, validar_tarjeta
from .prevision import _prevision_semanas, construir_datos_prevision


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


class DisponibilidadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="clave-segura-123")
        self.resource = Resource.objects.create(name="Pista 1")
        self.url = reverse("api_disponibilidad", args=[self.resource.id])

    def _aware(self, fecha, hora=0):
        return dj_timezone.make_aware(datetime.combine(fecha, time(hora)))

    def test_calcula_estado_disponible_parcial_completo_y_pasado(self):
        Booking.objects.create(
            user=self.user,
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 2), 10),
            end_time=self._aware(date(2026, 11, 2), 11),
        )
        Availability.objects.create(
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 2), 12),
            end_time=self._aware(date(2026, 11, 2), 13),
        )
        Availability.objects.create(
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 3), 9),
            end_time=self._aware(date(2026, 11, 3), 21),
        )

        dias = calcular_dias_disponibilidad(
            self.resource,
            self._aware(date(2026, 11, 1)),
            self._aware(date(2026, 11, 5)),
            hoy=date(2026, 11, 2),
        )

        self.assertEqual(
            [dia["estado"] for dia in dias],
            ["pasado", "parcial", "completo", "disponible"],
        )
        self.assertEqual([dia["fecha"] for dia in dias], [
            "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04",
        ])
        self.assertEqual(dias[1]["franjas_reservadas"], 1)
        self.assertEqual(dias[1]["franjas_bloqueadas"], 1)
        self.assertEqual(dias[1]["franjas_libres"], 10)
        self.assertEqual(dias[2]["franjas_libres"], 0)

    def test_endpoint_carga_solo_el_rango_solicitado(self):
        Booking.objects.create(
            user=self.user,
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 2), 10),
            end_time=self._aware(date(2026, 11, 2), 11),
        )
        Availability.objects.create(
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 3), 12),
            end_time=self._aware(date(2026, 11, 3), 13),
        )
        Booking.objects.create(
            user=self.user,
            resource=self.resource,
            start_time=self._aware(date(2026, 11, 8), 10),
            end_time=self._aware(date(2026, 11, 8), 11),
        )

        resp = self.client.get(self.url, {
            "start": self._aware(date(2026, 11, 2)).isoformat(),
            "end": self._aware(date(2026, 11, 5)).isoformat(),
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["dias"]), 3)
        self.assertEqual(len(data["eventos"]), 2)
        self.assertEqual(
            {evento["extendedProps"]["tipo"] for evento in data["eventos"]},
            {"reserva", "bloqueo"},
        )
        titulos = {evento["title"] for evento in data["eventos"]}
        self.assertNotIn("ana", titulos)
        self.assertEqual(titulos, {"Reservado", "Bloqueo administrativo"})

    def test_endpoint_requiere_rango_valido(self):
        self.assertEqual(self.client.get(self.url).status_code, 400)
        resp = self.client.get(self.url, {
            "start": "2026-11-05",
            "end": "2026-11-02",
        })
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rechaza_rangos_de_mas_de_62_dias(self):
        resp = self.client.get(self.url, {
            "start": "2026-01-01",
            "end": "2026-04-01",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])
        self.assertIn("62", resp.json()["error"])

    def test_endpoint_acepta_rangos_de_hasta_62_dias(self):
        resp = self.client.get(self.url, {
            "start": "2026-01-01",
            "end": "2026-03-04",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["dias"]), 62)

    def test_dia_actual_descuenta_franjas_ya_pasadas(self):
        dias = calcular_dias_disponibilidad(
            self.resource,
            self._aware(date(2026, 11, 2)),
            self._aware(date(2026, 11, 3)),
            hoy=date(2026, 11, 2),
            ahora=self._aware(date(2026, 11, 2), 12),
        )

        self.assertEqual(dias[0]["franjas_pasadas"], 3)
        self.assertEqual(dias[0]["franjas_libres"], 9)
        self.assertEqual(dias[0]["estado"], "parcial")

    def test_clean_rechaza_reserva_que_cruza_un_bloqueo(self):
        Availability.objects.create(
            resource=self.resource,
            start_time=_dt(hour=10),
            end_time=_dt(hour=11),
        )
        reserva = Booking(
            user=self.user,
            resource=self.resource,
            start_time=_dt(hour=10),
            end_time=_dt(hour=11),
        )
        with self.assertRaises(ValidationError):
            reserva.clean()

    def test_api_rechaza_reserva_que_cruza_un_bloqueo(self):
        self.client.force_login(self.user)
        Availability.objects.create(
            resource=self.resource,
            start_time=_dt(hour=10),
            end_time=_dt(hour=11),
        )
        resp = self.client.post(
            reverse("api_crear_reserva"),
            json.dumps({
                "resource_id": self.resource.id,
                "start_time": _dt(hour=10).isoformat(),
                "end_time": _dt(hour=11).isoformat(),
                "repeat_weeks": 0,
                "card": TARJETA_VALIDA,
            }),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(PaymentMethod.objects.exists())

    def test_recurrente_con_bloqueo_no_crea_ninguna_reserva(self):
        self.client.force_login(self.user)
        Availability.objects.create(
            resource=self.resource,
            start_time=_dt(days=8, hour=10),
            end_time=_dt(days=8, hour=11),
        )
        resp = self.client.post(
            reverse("api_crear_reserva"),
            json.dumps({
                "resource_id": self.resource.id,
                "start_time": _dt(hour=10).isoformat(),
                "end_time": _dt(hour=11).isoformat(),
                "repeat_weeks": 2,
                "card": TARJETA_VALIDA,
            }),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(PaymentMethod.objects.exists())


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
        self.assertEqual(resp.json()[0]["title"], "Reservado")
        self.assertNotIn("ana", resp.json()[0]["title"])


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
        self.assertEqual(resp.json()["payment_method_id"], metodo.id)
        self.assertEqual(resp.json()["payment_method"], str(metodo))

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


class PrevisionDemandaTests(TestCase):
    """HU3: histórico y previsión por día de la semana."""

    def setUp(self):
        self.user = User.objects.create_user("ana", password="clave-segura-123")
        self.resource = Resource.objects.create(name="Pista A")
        self.resource2 = Resource.objects.create(name="Pista B")

    def _reserva(self, fecha, hora, resource=None):
        inicio = dj_timezone.make_aware(datetime.combine(fecha, time(hora, 0)))
        return Booking.objects.create(
            user=self.user,
            resource=resource or self.resource,
            start_time=inicio,
            end_time=inicio + timedelta(hours=1),
        )

    def test_calcula_historico_picos_y_prevision(self):
        hoy = date(2026, 10, 28)  # miércoles
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_historial = inicio_semana - timedelta(weeks=2)

        for semana in range(2):
            lunes = inicio_historial + timedelta(weeks=semana)
            self._reserva(lunes, 10)
            martes = lunes + timedelta(days=1)
            self._reserva(martes, 18)
            self._reserva(martes, 19)
            self._reserva(martes, 20)
            self._reserva(martes, 18, resource=self.resource2)
            miercoles = lunes + timedelta(days=2)
            self._reserva(miercoles, 9)
            self._reserva(miercoles, 11)

        datos = construir_datos_prevision(
            hoy=hoy, semanas_historial=2, semanas_futuras=2
        )

        self.assertTrue(datos["hay_historial"])
        self.assertEqual(datos["total_historico"], 14)
        self.assertEqual(datos["promedio_semanal"], 7.0)
        self.assertEqual(datos["pico_dia"], {"nombre": "Martes", "total": 8})
        self.assertEqual(datos["pico_hora"], {"hora": "18:00", "total": 4})
        self.assertEqual([semana["total"] for semana in datos["por_semana"]], [7, 7])
        self.assertEqual(datos["por_recurso"][0]["nombre"], "Pista A")
        self.assertEqual(datos["por_recurso"][0]["total"], 12)
        self.assertEqual(len(datos["por_dia"]), 14)

        prevision = datos["prevision_semanas"]
        self.assertEqual(len(prevision), 2)
        self.assertEqual(prevision[0]["total"], 7.0)
        self.assertEqual([dia["prediccion"] for dia in prevision[0]["dias"][:3]], [1.0, 4.0, 2.0])
        self.assertEqual(datos["prevision_total"], 14.0)

    def test_total_semanal_suma_antes_de_redondear(self):
        inicio_semana = date(2026, 10, 26)  # lunes
        promedios = {dia: 1.125 for dia in range(7)}

        semanas = _prevision_semanas(inicio_semana, 1, promedios)

        self.assertEqual(semanas[0]["total"], 7.9)
        self.assertEqual(
            round(sum(dia["prediccion"] for dia in semanas[0]["dias"]), 1),
            7.7,
        )

    def test_sin_historial_devuelve_ceros_y_no_falla(self):
        datos = construir_datos_prevision(hoy=date(2026, 10, 28))

        self.assertFalse(datos["hay_historial"])
        self.assertEqual(datos["total_historico"], 0)
        self.assertEqual(datos["promedio_semanal"], 0.0)
        self.assertIsNone(datos["pico_dia"])
        self.assertIsNone(datos["pico_hora"])
        self.assertEqual(datos["por_recurso"], [])
        self.assertEqual(datos["prevision_total"], 0)
        self.assertEqual(len(datos["prevision_semanas"]), 4)

    def test_no_cuenta_reservas_futuras_ni_de_la_semana_en_curso(self):
        hoy = date(2026, 10, 28)
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        self._reserva(inicio_semana - timedelta(days=7), 10)  # semana anterior
        self._reserva(inicio_semana, 10)  # lunes de la semana en curso
        self._reserva(hoy + timedelta(days=7), 10)  # futura

        datos = construir_datos_prevision(hoy=hoy, semanas_historial=8)

        self.assertEqual(datos["total_historico"], 1)


class PrevisionDemandaVistaTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            "staff", password="clave-segura-123", is_staff=True
        )
        self.normal = User.objects.create_user("normal", password="clave-segura-123")

    def test_anonimo_redirige_al_login_del_admin(self):
        resp = self.client.get(reverse("prevision_demanda"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login/", resp.url)

    def test_usuario_no_staff_no_accede(self):
        self.client.force_login(self.normal)
        resp = self.client.get(reverse("prevision_demanda"))
        self.assertEqual(resp.status_code, 302)

    def test_staff_accede_y_ve_el_dashboard(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse("prevision_demanda"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Previsión de demanda")
        self.assertContains(resp, "media de reservas de cada día")
        self.assertContains(resp, "<h1>Previsión de demanda</h1>", count=1)

    def test_admin_index_enlaza_al_dashboard(self):
        self.client.force_login(self.staff)
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Abrir previsión de demanda")


class GenerarHistoricoDemandaTests(TestCase):
    def test_genera_historico_pasado_y_es_idempotente(self):
        call_command(
            "generar_historico_demanda", "--semanas", "2", "--seed", "7",
            stdout=StringIO(),
        )
        total = Booking.objects.count()
        self.assertGreater(total, 0)
        self.assertTrue(Booking.objects.filter(user__username="demanda_historial").exists())

        hoy = dj_timezone.localdate()
        for reserva in Booking.objects.all():
            inicio = dj_timezone.localtime(reserva.start_time)
            fin = dj_timezone.localtime(reserva.end_time)
            self.assertLess(inicio.date(), hoy)
            self.assertGreaterEqual(inicio.hour, 9)
            self.assertLessEqual(fin.hour, 21)

        call_command(
            "generar_historico_demanda", "--semanas", "2", "--seed", "7",
            stdout=StringIO(),
        )
        self.assertEqual(Booking.objects.count(), total)

    def test_rechaza_semanas_invalidas(self):
        with self.assertRaises(CommandError):
            call_command(
                "generar_historico_demanda", "--semanas", "0", stdout=StringIO()
            )
