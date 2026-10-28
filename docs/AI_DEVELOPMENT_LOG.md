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
| 2026-10-19 | #1 | Código | Claude | Atender la revisión de Derlin sobre `SECRET_KEY`/`DEBUG` | `DEBUG` apagado por defecto, `DJANGO_SECRET_KEY` obligatoria fuera de desarrollo, `manage.py` activa el modo desarrollo; 3 pruebas nuevas (2 fallan con la configuración anterior) | Pendiente de nueva revisión | Gabriel |
| 2026-10-27 | #1 | Testing (QA) | OpenCode (DeepSeek V4.1 Flash) | Ejecutar el checklist de QA del PR #7 en un clon limpio | 18/18 pruebas OK; instalación, migraciones, reservas manuales, recurrencia y admin verificados | Aceptado: QA OK; observación no bloqueante registrada abajo | Isalleth |
| 2026-10-27 | #2 | Revisión | ChatGPT (GPT-6) | Revisar seguridad, validación de tarjetas, transacciones, pruebas y calidad del PR #8 | 37/37 pruebas OK; error reproducido con `repeat_weeks=-1`: 0 reservas y 1 tarjeta guardada; sugerencia para ampliar pruebas recurrentes | Request changes; solicitar validación y prueba de regresión | Derlin |
| 2026-10-27 | #2 | Revisión (segunda) | ChatGPT (GPT-6) | Verificar las correcciones del PR #8 después de solicitar cambios | 38/38 pruebas OK; corregida la validación de semanas negativas y ampliadas las pruebas recurrentes | Approve tras verificar las correcciones | Derlin |

## Respuestas incorrectas de la IA

| Fecha | Issue | Herramienta | Qué dijo/hizo mal | Cómo se detectó | Corrección |
|---|---|---|---|---|---|
| 2026-10-18 | #1 | Claude | El análisis inicial del repo y las 12 pruebas no detectaron que `crear_reservas_demo` usaba fechas sin zona horaria y que el sistema estaba en UTC: las reservas demo quedaban fuera del horario visible (04:00–08:00 en Panamá) | Revisión humana de Derlin al probar en local (comentario en PR #7) | Zona horaria del proyecto y fechas con zona horaria; pruebas de regresión |
| 2026-10-18 | #1 | Claude | Al mover `SECRET_KEY` y `DEBUG` a variables de entorno dejó valores inseguros por defecto (clave fija y `DEBUG=True`): un despliegue sin variables quedaba inseguro | Revisión de Derlin en PR #7 | Configuración segura por defecto y pruebas |
| 2026-10-19 | #1 | Claude | Al corregir la configuración dejó una clave de desarrollo escrita en el código (`SECRET_KEY = "django-insecure-..."`) | SonarCloud marcó el Quality Gate en rojo (Security Rating E) | Clave aleatoria generada en `.dev_secret_key`, ignorado por git |
| 2026-10-27 | #1 | OpenCode (DeepSeek V4.1 Flash) | Las 18 pruebas no detectaron que el aviso de solapamiento del cliente (`isReserved`) usa la lista `reservas` cargada al abrir el calendario y no se actualiza tras crear una reserva; sin recargar, una segunda selección solapada solo la rechaza el servidor | QA manual del PR #7: crear una reserva y, sin recargar, seleccionar un rango que la solape | El servidor rechaza la reserva (no hay doble reserva); pendiente no bloqueante para HU2: actualizar la lista o validar siempre contra el servidor |

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
| 2026-10-19 | Configuración segura por defecto: `DEBUG=False` y `SECRET_KEY` obligatoria; solo `manage.py` activa el modo desarrollo | Revisión de Derlin: evitar despliegues inseguros sin complicar el trabajo local |
| 2026-10-19 | La validación de bloqueos (`Availability`) en el servidor se deja para HU2 (#3), no en este PR | Derlin es Dev de HU2 y es parte del calendario; queda como criterio de aceptación en #3 |
| 2026-10-18 | HU4 pasa a Isalleth como Developer (Derlin Reviewer, Gabriel QA) | Equilibrar: cada integrante es Dev de 2 historias |
| 2026-10-27 | Request changes en PR #8 (HU1) | Derlin reprodujo un caso donde una solicitud con semanas negativas guarda tarjeta sin crear reserva; requiere corrección y prueba de regresión antes de aprobar |
| 2026-10-27 | Approve en PR #8 (HU1) | Se verificaron las correcciones del commit d18ee42; las 38 pruebas pasaron y los hallazgos de la revisión anterior fueron atendidos |
