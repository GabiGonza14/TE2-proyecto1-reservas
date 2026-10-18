# AI Development Log

Registro de los usos de IA que afectaron significativamente el desarrollo (no cada prompt).
Cada integrante agrega sus filas al trabajar en su rol.

**Equipo y roles por historia**

| Issue | Developer | Reviewer | QA |
|---|---|---|---|
| #1 Preparación | A (GabiGonza14) | B | C |
| #2 HU1 Pago con datos guardados | A | B | C |
| #3 HU2 Calendario disponible/ocupado | B | C | A |
| #4 HU3 Previsión de demanda | C | A | B |
| #5 HU4 Cancelar o modificar reserva | A | C | B |
| #6 HU5 Correo de confirmación | B | A | C |

## Registro

| Fecha | Issue | Actividad | Herramienta IA | Qué se solicitó | Resultado | Decisión humana | Quién |
|---|---|---|---|---|---|---|---|
| 2026-10-18 | — | Análisis | Claude | Resumir el enunciado del proyecto (PDF) | Resumen de requisitos y entregables | Aceptado | A |
| 2026-10-18 | — | Arquitectura | Claude | Comparar los 4 repositorios candidatos | Recomendó Gestor-de-reservas (Django + FullCalendar) | Aceptado: se eligió ese repo | A |
| 2026-10-18 | #1 | Análisis | Claude | Analizar el repo antes de modificarlo | Detectó: sin requirements, 0 pruebas, migración pendiente, db versionada, endpoint con `csrf_exempt`, `INSTALLED_APPS` duplicado | Aceptado; se creó el issue #1 | A |
| 2026-10-18 | #1–#6 | Planificación | Claude | Redactar issues con criterios de aceptación | 6 issues | HU4 y HU5 elegidas por el equipo entre 4 propuestas | A |
| 2026-10-18 | #1 | Código | Claude | Implementar la preparación del proyecto | .gitignore, requirements, settings por entorno, migración, CSRF | Pendiente de revisión (PR) | A |
| 2026-10-18 | #1 | Testing | Claude | Crear primeras pruebas automatizadas | 12 pruebas, todas pasan | Pendiente de revisión (PR) | A |

## Respuestas incorrectas de la IA

| Fecha | Issue | Herramienta | Qué dijo/hizo mal | Cómo se detectó | Corrección |
|---|---|---|---|---|---|

## Cambios de la IA rechazados

| Fecha | Issue | Herramienta | Cambio propuesto | Por qué se rechazó |
|---|---|---|---|---|

## Decisiones humanas

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-18 | Repo base: Gestor-de-reservas | Python, fácil de levantar, ya trae FullCalendar |
| 2026-10-18 | Historias propias: cancelar/modificar reserva y correo de confirmación | Elegidas entre 4 propuestas |
| 2026-10-18 | La preparación (#1) la hace A como Developer | No estaba en la rotación; A también es Dev de HU1 |
