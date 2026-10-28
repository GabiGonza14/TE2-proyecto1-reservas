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

        usuario, creado = User.objects.get_or_create(username="demanda_historial")
        if creado:
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Usuario demanda_historial creado."))

        recursos = []
        for nombre, descripcion in RECURSOS_DEMO:
            recurso, creado = Resource.objects.get_or_create(
                name=nombre,
                defaults={"description": descripcion},
            )
            recursos.append(recurso)
            if creado:
                self.stdout.write(self.style.SUCCESS(f"Recurso {nombre} creado."))

        if options["limpiar"]:
            borradas = Booking.objects.filter(resource__in=recursos).count()
            Booking.objects.filter(resource__in=recursos).delete()
            self.stdout.write(self.style.WARNING(f"Reservas históricas borradas: {borradas}."))

        rng = random.Random(options["seed"])
        hoy = timezone.localdate()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio = inicio_semana - timedelta(weeks=semanas)

        creadas = 0
        for indice_recurso, recurso in enumerate(recursos):
            factor = FACTORES_RECURSO[indice_recurso]
            for indice_dia in range(semanas * 7):
                fecha = inicio + timedelta(days=indice_dia)
                media = PESO_DIA[fecha.weekday()] * factor
                cantidad = max(0, min(4, int(round(rng.gauss(media, 0.65)))))
                if cantidad == 0:
                    continue

                horas = []
                while len(horas) < cantidad:
                    hora = rng.choices(HORAS, weights=PESO_HORA, k=1)[0]
                    if hora not in horas:
                        horas.append(hora)

                for hora in horas:
                    inicio_reserva = timezone.make_aware(
                        datetime.combine(fecha, time(hora, 0))
                    )
                    fin_reserva = inicio_reserva + timedelta(hours=1)
                    ocupada = Booking.objects.filter(
                        resource=recurso,
                        start_time__lt=fin_reserva,
                        end_time__gt=inicio_reserva,
                    ).exists()
                    if ocupada:
                        continue
                    Booking.objects.create(
                        user=usuario,
                        resource=recurso,
                        start_time=inicio_reserva,
                        end_time=fin_reserva,
                    )
                    creadas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Histórico generado: {creadas} reservas nuevas en {semanas} semanas."
        ))
