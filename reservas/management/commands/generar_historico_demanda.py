"""Genera reservas históricas de prueba para el dashboard de demanda."""

import random
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from reservas.models import Booking, Resource


RECURSOS_DEMO = (
    ("Pista Histórica A", "Pista de pádel con alta demanda"),
    ("Pista Histórica B", "Pista de pádel con demanda media"),
    ("Sala Histórica", "Sala multiusos con demanda baja"),
)
FACTORES_RECURSO = (1.25, 1.0, 0.75)
PESO_DIA = (1.0, 1.0, 1.1, 1.4, 1.8, 1.8, 1.4)  # lunes a domingo
HORAS = tuple(range(9, 21))
PESO_HORA = (1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 6, 4)


def _obtener_usuario():
    usuario, creado = User.objects.get_or_create(username="demanda_historial")
    if creado:
        usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    return usuario, creado


def _obtener_recursos():
    recursos = []
    creados = []
    for nombre, descripcion in RECURSOS_DEMO:
        recurso, creado = Resource.objects.get_or_create(
            name=nombre,
            defaults={"description": descripcion},
        )
        recursos.append(recurso)
        if creado:
            creados.append(nombre)
    return recursos, creados


def _limpiar_historico(recursos):
    filtro = Booking.objects.filter(resource__in=recursos)
    borradas = filtro.count()
    filtro.delete()
    return borradas


def _horas_para_dia(rng, cantidad):
    horas = []
    while len(horas) < cantidad:
        hora = rng.choices(HORAS, weights=PESO_HORA, k=1)[0]  # NOSONAR
        if hora not in horas:
            horas.append(hora)
    return horas


def _crear_reserva(usuario, recurso, fecha, hora):
    inicio = timezone.make_aware(datetime.combine(fecha, time(hora, 0)))
    fin = inicio + timedelta(hours=1)
    ocupada = Booking.objects.filter(
        resource=recurso,
        start_time__lt=fin,
        end_time__gt=inicio,
    ).exists()
    if ocupada:
        return False
    Booking.objects.create(
        user=usuario,
        resource=recurso,
        start_time=inicio,
        end_time=fin,
    )
    return True


def _generar_reservas(usuario, recursos, rng, semanas, inicio):
    creadas = 0
    for indice_recurso, recurso in enumerate(recursos):
        factor = FACTORES_RECURSO[indice_recurso]
        for indice_dia in range(semanas * 7):
            fecha = inicio + timedelta(days=indice_dia)
            media = PESO_DIA[fecha.weekday()] * factor
            cantidad = max(0, min(4, int(round(rng.gauss(media, 0.65)))))  # NOSONAR
            if cantidad == 0:
                continue
            for hora in _horas_para_dia(rng, cantidad):
                if _crear_reserva(usuario, recurso, fecha, hora):
                    creadas += 1
    return creadas


class Command(BaseCommand):
    help = "Genera reservas históricas de prueba para el dashboard de previsión de demanda."

    def add_arguments(self, parser):
        parser.add_argument(
            "--semanas",
            type=int,
            default=8,
            help="Semanas completas de histórico a generar (por defecto: 8).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Semilla para que el histórico sea reproducible (por defecto: 42).",
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra las reservas de los recursos históricos antes de generar.",
        )

    def handle(self, *args, **options):
        semanas = options["semanas"]
        if semanas < 1:
            raise CommandError("El número de semanas debe ser mayor que cero.")

        usuario, usuario_creado = _obtener_usuario()
        if usuario_creado:
            self.stdout.write(self.style.SUCCESS("Usuario demanda_historial creado."))

        recursos, recursos_creados = _obtener_recursos()
        for nombre in recursos_creados:
            self.stdout.write(self.style.SUCCESS(f"Recurso {nombre} creado."))

        if options["limpiar"]:
            borradas = _limpiar_historico(recursos)
            self.stdout.write(self.style.WARNING(f"Reservas históricas borradas: {borradas}."))

        rng = random.Random(options["seed"])  # NOSONAR: datos de prueba reproducibles
        hoy = timezone.localdate()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio = inicio_semana - timedelta(weeks=semanas)
        creadas = _generar_reservas(usuario, recursos, rng, semanas, inicio)

        self.stdout.write(self.style.SUCCESS(
            f"Histórico generado: {creadas} reservas nuevas en {semanas} semanas."
        ))
