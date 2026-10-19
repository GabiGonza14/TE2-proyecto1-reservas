# AI Development Log

Registro de los usos de IA que afectaron significativamente el desarrollo (no cada prompt).
Cada integrante agrega sus filas al trabajar en su rol.

**Equipo:** Gabriel (GabiGonza14), Derlin, Isalleth

**Roles por historia**

| Issue | Developer | Reviewer | QA |
|---|---|---|---|
| #1 Preparación | Gabriel | Derlin | Isalleth |
| #2 HU1 Pago con datos guardados | Gabriel | Derlin | Isalleth |
| #3 HU2 Calendario disponible/ocupado | Derlin | Isalleth | Gabriel |
| #4 HU3 Previsión de demanda | Isalleth | Gabriel | Derlin |
| #5 HU4 Cancelar o modificar reserva | Isalleth | Derlin | Gabriel |
| #6 HU5 Correo de confirmación | Derlin | Gabriel | Isalleth |

## Registro

| Fecha | Issue | Actividad | Herramienta IA | Qué se solicitó | Resultado | Decisión humana | Quién |
|---|---|---|---|---|---|---|---|
| 2026-10-18 | — | Análisis | Claude | Resumir el enunciado del proyecto (PDF) | Resumen de requisitos y entregables | Aceptado | Gabriel |
| 2026-10-18 | — | Arquitectura | Claude | Comparar los 4 repositorios candidatos | Recomendó Gestor-de-reservas (Django + FullCalendar) | Aceptado: se eligió ese repo | Gabriel |
| 2026-10-18 | #1 | Análisis | Claude | Analizar el repo antes de modificarlo | Detectó: sin requirements, 0 pruebas, migración pendiente, db versionada, endpoint con `csrf_exempt`, `INSTALLED_APPS` duplicado | Aceptado; se creó el issue #1 | Gabriel |
| 2026-10-18 | #1–#6 | Planificación | Claude | Redactar issues con criterios de aceptación | 6 issues | HU4 y HU5 elegidas por el equipo entre 4 propuestas | Gabriel |
| 2026-10-18 | #1 | Código | Claude | Implementar la preparación del proyecto | .gitignore, requirements, settings por entorno, migración, CSRF | Pendiente de revisión (PR) | Gabriel |
| 2026-10-18 | #1 | Testing | Claude | Crear primeras pruebas automatizadas | 12 pruebas, todas pasan | Pendiente de revisión (PR) | Gabriel |
| 2026-10-19 | #1 | Debug | Claude | Corregir el problema de zona horaria reportado por Derlin | `TIME_ZONE` = America/Panama, fechas con zona horaria en `crear_reservas_demo`, 3 pruebas de regresión (fallan con el código anterior) | Pendiente de revisión (PR) | Gabriel |

## Respuestas incorrectas de la IA

| Fecha | Issue | Herramienta | Qué dijo/hizo mal | Cómo se detectó | Corrección |
|---|---|---|---|---|---|
| 2026-10-18 | #1 | Claude | El análisis inicial del repo y las 12 pruebas no detectaron que `crear_reservas_demo` usaba fechas sin zona horaria y que el sistema estaba en UTC: las reservas demo quedaban fuera del horario visible (04:00–08:00 en Panamá) | Revisión humana de Derlin al probar en local (comentario en PR #7) | Zona horaria del proyecto y fechas con zona horaria; pruebas de regresión |

## Cambios de la IA rechazados

| Fecha | Issue | Herramienta | Cambio propuesto | Por qué se rechazó |
|---|---|---|---|---|

## Decisiones humanas

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-18 | Repo base: Gestor-de-reservas | Python, fácil de levantar, ya trae FullCalendar |
| 2026-10-18 | Historias propias: cancelar/modificar reserva y correo de confirmación | Elegidas entre 4 propuestas |
| 2026-10-18 | La preparación (#1) la hace Gabriel como Developer | No estaba en la rotación |
| 2026-10-19 | Zona horaria del sistema: America/Panama (configurable con `DJANGO_TIME_ZONE`) | Los usuarios y el equipo están en Panamá; el calendario muestra 09:00–21:00 local |
| 2026-10-18 | HU4 pasa a Isalleth como Developer (Derlin Reviewer, Gabriel QA) | Equilibrar: cada integrante es Dev de 2 historias |
