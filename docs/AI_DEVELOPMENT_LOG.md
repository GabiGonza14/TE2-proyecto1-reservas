# AI Development Log

Registro de los usos de IA que afectaron significativamente el desarrollo (no cada prompt).
Cada integrante agrega sus filas al trabajar en su rol.

**Equipo:** Gabriel (GabiGonza14), Derlin, Isalleth

**Roles por historia** (actualizados el 2026-10-28: Derlin sigue en el equipo pero no puede hacer tareas; ver Decisiones humanas)

| Issue | Developer | Reviewer | QA |
|---|---|---|---|
| #1 Preparación | Gabriel | Derlin | Isalleth |
| #2 HU1 Pago con datos guardados | Gabriel | Derlin | Isalleth |
| #3 HU2 Calendario disponible/ocupado | Isalleth | Gabriel | Gabriel |
| #4 HU3 Previsión de demanda | Isalleth | Gabriel | Derlin |
| #5 HU4 Cancelar o modificar reserva | Gabriel | Isalleth | Isalleth |
| #6 HU5 Correo de confirmación | Gabriel | Isalleth | Isalleth |

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
| 2026-10-27 | #2 | Diseño | Claude | Diseñar HU1 (pago con datos guardados) | Modelo `PaymentMethod` sin número completo ni CVV, pago simulado con validación Luhn/vencimiento/CVV, reserva en un clic con método guardado | Pendiente de revisión (PR) | Gabriel |
| 2026-10-27 | #2 | Código | Claude | Implementar HU1: API, modal de pago en el calendario y página "Mis métodos de pago" | Pago obligatorio al reservar; creación atómica (si una semana choca no se crea ninguna ni se guarda la tarjeta) | Pendiente de revisión (PR) | Gabriel |
| 2026-10-27 | #2 | Testing | Claude | Pruebas automatizadas de HU1 y prueba del flujo en navegador | 19 pruebas nuevas (37 en total); flujo probado con Playwright: tarjeta nueva → guardada → reserva en un clic | Pendiente de revisión (PR) | Gabriel |
| 2026-10-28 | #2 | Debug | Claude | Corregir lo pedido por Derlin en la revisión del PR #8 | `repeat_weeks` validado como entero ≥ 0 (400 si no); prueba nueva (falla con el código anterior) y prueba de recurrencia con conflicto ampliada con `save: true` | Pendiente de nueva revisión | Gabriel |
| 2026-10-28 | #2 | Testing (QA) | OpenCode (DeepSeek V4.1 Flash) | Ejecutar el checklist de QA del PR #8 en un clon limpio | 38/38 pruebas OK; 9/9 pruebas manuales OK (pago simulado, tarjeta guardada, tarjetas inválidas, recurrencia con conflicto, aislamiento entre usuarios y admin) | Aceptado: QA OK | Isalleth |
| 2026-10-28 | #3 | Diseño | OpenCode (DeepSeek V4.1 Flash) | Diseñar HU2: calendario con disponibilidad por día y franjas | Estados calculados sobre franjas de 09:00–21:00, endpoint JSON por rango, bloqueo de selección en el cliente y validación de `Availability` en el servidor | Aceptado: se implementa en el PR | Isalleth |
| 2026-10-28 | #3 | Código | OpenCode (DeepSeek V4.1 Flash) | Implementar HU2 y los pendientes del issue #3 | Calendario mensual con colores disponible/parcial/completo/pasado, endpoint `/api/disponibilidad/`, validación de bloqueos en la API y en `Booking.clean`, refresco de eventos sin recargar y leyenda | Aceptado: 54/54 pruebas OK | Isalleth |
| 2026-10-28 | #3 | Testing | OpenCode (DeepSeek V4.1 Flash) | Crear pruebas del cálculo de disponibilidad, del endpoint por rango y de la validación de bloqueos | 6 pruebas nuevas: estados por día, filtrado por rango, rango inválido, `clean`, rechazo de API y recurrencia con bloqueo sin creación parcial; 54/54 en total | Aceptado: pendiente de revisión y QA de Gabriel | Isalleth |
| 2026-10-28 | #3 | Revisión | Claude | Revisar el PR #10: código, pruebas y calendario en el navegador (comparado con `main`) | 54/54 pruebas OK; 3 bloqueantes: la selección de franjas falla por un error de JavaScript (`selectAllow` sin `view`), `/api/disponibilidad/` sin límite de rango (5 s y 10 MB con 200 años) y autoría equivocada en el AI log; 3 sugerencias no bloqueantes | Aceptado: Request changes | Gabriel |
| 2026-10-28 | #3 | Debug | OpenCode (DeepSeek V4.1 Flash) | Atender la revisión de Gabriel del PR #10: error de selección, rango del endpoint, autoría y sugerencias | Selección corregida usando la vista actual del calendario; endpoint limitado a 62 días con pruebas de rechazo y borde; franjas ya transcurridas del día actual descontadas; títulos de eventos sin nombre de usuario; tarjeta recién guardada disponible en la siguiente reserva sin recargar; 57/57 pruebas OK y flujo verificado en el navegador | Aceptado: pendiente nueva revisión y QA de Gabriel | Isalleth |
| 2026-10-28 | #3 | Testing (QA) | Claude | Volver a revisar y probar el PR #10 tras las correcciones (`9f15377`) | 57/57 pruebas OK; en el navegador: dos reservas creadas, franja ocupada no seleccionable, clic en el mes abre la vista diaria, tarjeta recién guardada disponible sin recargar, sin errores en consola; rango de 200 años rechazado con 400 | Aceptado: Approve y QA OK | Gabriel |
| 2026-10-28 | #4 | Diseño | OpenCode (DeepSeek V4.1 Flash) | Diseñar HU3: dashboard de previsión de demanda para staff | Histórico por día/semana y recurso, días/horas pico, previsión por media de cada día de la semana y comando de histórico reproducible | Aceptado: método simple y explicable; se implementa en el PR | Isalleth |
| 2026-10-28 | #4 | Código | OpenCode (DeepSeek V4.1 Flash) | Implementar la vista staff, el cálculo de previsión, el comando y el enlace desde el admin | `prevision.py`, vista con `staff_member_required`, dashboard administrativo, `generar_historico_demanda` y enlace en el índice del admin | Aceptado: 48/48 pruebas OK | Isalleth |
| 2026-10-28 | #4 | Testing | OpenCode (DeepSeek V4.1 Flash) | Crear pruebas del cálculo de previsión, picos, comando y control de acceso | 10 pruebas nuevas: histórico, previsión por día de la semana, total semanal sin redondear, sin datos, exclusión de futuras, acceso staff/no staff y comando idempotente | Aceptado: falta revisión de Gabriel y QA de Derlin | Isalleth |
| 2026-10-28 | #4 | Debug | OpenCode (DeepSeek V4.1 Flash) | Atender la revisión de Gabriel del PR #9: modo oscuro y sugerencias no bloqueantes | Dashboard con variables de color del admin, total semanal calculado antes de redondear, texto sobre el inicio de la previsión y nota de recursos demo en el README; 48/48 pruebas OK | Aceptado: pendiente de nueva revisión | Isalleth |
| 2026-10-28 | #4 | Revisión | Claude | Revisar el PR #9: código, pruebas y dashboard en el navegador | 47/47 pruebas OK, comando y control de acceso correctos; 3 sugerencias no bloqueantes; primero recomendó Approve | Rechazado en parte: se piden cambios por el modo oscuro (ver abajo) | Gabriel |
| 2026-10-28 | #4 | Testing (QA) | OpenCode (DeepSeek V4.1 Flash) | Ejecutar el checklist de QA del PR #9 en un clon limpio | 48/48 pruebas OK; 8/8 pruebas manuales OK (sin datos, histórico de 244 reservas, idempotencia, previsión, permisos, enlaces, modo claro/oscuro y fechas/horas); 2 observaciones de redondeo no bloqueantes | Aceptado: QA OK | Derlin |
| 2026-10-28 | #5 | Diseño | Claude | Diseñar HU4: cancelar o modificar mi reserva | Página "Mis reservas"; reglas en `reservas/gestion.py`; antelación mínima configurable (2 h por defecto); al modificar se mantiene la duración y se reutilizan las validaciones de solapamiento y bloqueos | Aceptado: se implementa en el PR | Gabriel |
| 2026-10-28 | #5 | Código | Claude | Implementar HU4: lista de mis reservas, cancelar y cambiar fecha/hora | Vistas solo por POST y solo del dueño (403 si no), mensajes de error claros, enlaces "Mis reservas" en la barra | Pendiente de revisión (PR) | Gabriel |
| 2026-10-28 | #5 | Testing | Claude | Pruebas automatizadas de HU4 y prueba del flujo en navegador | 14 pruebas nuevas (71 en total); flujo probado con Playwright: conflicto rechazado, cambio a franja libre y cancelación | Pendiente de revisión (PR) | Gabriel |

## Respuestas incorrectas de la IA

| Fecha | Issue | Herramienta | Qué dijo/hizo mal | Cómo se detectó | Corrección |
|---|---|---|---|---|---|
| 2026-10-18 | #1 | Claude | El análisis inicial del repo y las 12 pruebas no detectaron que `crear_reservas_demo` usaba fechas sin zona horaria y que el sistema estaba en UTC: las reservas demo quedaban fuera del horario visible (04:00–08:00 en Panamá) | Revisión humana de Derlin al probar en local (comentario en PR #7) | Zona horaria del proyecto y fechas con zona horaria; pruebas de regresión |
| 2026-10-18 | #1 | Claude | Al mover `SECRET_KEY` y `DEBUG` a variables de entorno dejó valores inseguros por defecto (clave fija y `DEBUG=True`): un despliegue sin variables quedaba inseguro | Revisión de Derlin en PR #7 | Configuración segura por defecto y pruebas |
| 2026-10-19 | #1 | Claude | Al corregir la configuración dejó una clave de desarrollo escrita en el código (`SECRET_KEY = "django-insecure-..."`) | SonarCloud marcó el Quality Gate en rojo (Security Rating E) | Clave aleatoria generada en `.dev_secret_key`, ignorado por git |
| 2026-10-27 | #1 | OpenCode (DeepSeek V4.1 Flash) | Las 18 pruebas no detectaron que el aviso de solapamiento del cliente (`isReserved`) usa la lista `reservas` cargada al abrir el calendario y no se actualiza tras crear una reserva; sin recargar, una segunda selección solapada solo la rechaza el servidor | QA manual del PR #7: crear una reserva y, sin recargar, seleccionar un rango que la solape | El servidor rechaza la reserva (no hay doble reserva); pendiente no bloqueante para HU2: actualizar la lista o validar siempre contra el servidor |
| 2026-10-27 | #2 | Claude | La página nueva "Mis métodos de pago" cargaba Tailwind desde el CDN sin `integrity`/`crossorigin`, y `api_crear_reserva` quedó con complejidad cognitiva 30 (límite 15) | SonarCloud marcó el Quality Gate en rojo en el PR #8 (Security Rating B) | Hash SRI (sha384) en el `<link>`, validación del pago y búsqueda de conflictos extraídas a funciones auxiliares; mismas 37 pruebas OK |
| 2026-10-28 | #2 | Claude | `api_crear_reserva` aceptaba `repeat_weeks` negativo: con -1 respondía éxito sin crear reservas pero guardaba la tarjeta; las 37 pruebas no lo cubrían | Revisión de Derlin en el PR #8 (probó la API a mano) | Validación de `repeat_weeks` y prueba de regresión |
| 2026-10-28 | #4 | OpenCode (DeepSeek V4.1 Flash) | La primera versión del dashboard duplicaba el título (`<title>` y `<h1>`) porque el template del admin ya renderiza `title`; además una prueba de hora pico asumía un desempate no determinista | Revisión en navegador y ejecución de las pruebas | Se eliminó el bloque de título y el `<h1>` propios; se ajustó el fixture para que la hora pico tenga un valor único |
| 2026-10-28 | #3 | OpenCode (DeepSeek V4.1 Flash) | La primera versión de la validación solo comprobaba reservas y devolvía HTTP 200 con `success: false` para un conflicto; un bloqueo de `Availability` podía permitir crear la reserva | Prueba de API de HU2: esperaba 400 y comprobaba que no se creara nada | Se añadió `Availability` a `_buscar_conflicto` y a `Booking.clean`, y el conflicto devuelve 400; 54/54 pruebas OK |
| 2026-10-28 | #3 | OpenCode (DeepSeek V4.1 Flash) | `selectAllow` de FullCalendar 6 no recibe `view`; la función lanzaba `TypeError: Cannot read properties of undefined (reading 'type')` al arrastrar una franja y las 54 pruebas (sin navegador) no lo detectaron | Revisión de Gabriel en el navegador y consola del PR #10 | Se usa `calendar.view.type` cuando `info.view` no existe; verificado con un arrastre real en el navegador: la selección abre el modal y una franja ocupada no lo abre |
| 2026-10-28 | #3 | OpenCode (DeepSeek V4.1 Flash) | `/api/disponibilidad/` no limitaba el rango: una petición de 200 años tardaba unos 5 s y devolvía unos 10 MB | Revisión de Gabriel en el PR #10 | Se rechazan rangos de más de 62 días con HTTP 400; pruebas del límite y del borde de 62 días |
| 2026-10-28 | #3 | OpenCode (DeepSeek V4.1 Flash) | El AI log y la descripción del PR asignaban HU2 a Derlin como developer y a Isalleth como reviewer, cuando los roles nuevos son Isalleth (developer) y Gabriel (review y QA) | Revisión de Gabriel en el PR #10 | Se actualizaron la tabla de roles, las filas de #3 y la descripción del PR |
| 2026-10-28 | #4 | OpenCode (DeepSeek V4.1 Flash) | La primera versión del comando de histórico superaba la complejidad cognitiva (26 > 15) y usaba `random` sin justificar, lo que hizo fallar el Quality Gate de SonarCloud | SonarCloud en el PR #9 | Se dividió el comando en funciones auxiliares, se justificó `random` con `# NOSONAR` para datos de prueba y se añadió `@require_GET` a la vista |
| 2026-10-28 | #4 | Claude | La revisión del PR #9 recomendó aprobar sin detectar que el dashboard no se lee en modo oscuro: los paneles tienen fondo blanco fijo y el texto hereda el color claro del admin | Gabriel al probar el dashboard en su navegador con modo oscuro | Revisión cambiada a Request changes: usar las variables de color del admin en lugar de colores fijos |
| 2026-10-28 | #5 | Claude | Al modificar una reserva a la misma franja que otra, mostraba dos errores: el propio y el genérico de `unique_together` ("Booking con este Resource, Start time y End time ya existe.") | Prueba del flujo en el navegador | `full_clean(validate_unique=False)`, porque `clean()` ya rechaza la franja idéntica; prueba que exige un único mensaje |

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
| 2026-10-27 | HU1: pago simulado sin pasarela real; solo se guardan titular, marca, últimos 4 dígitos y vencimiento | No hay pasarela en el alcance del curso y guardar el número completo o el CVV sería inseguro |
| 2026-10-27 | HU1 hace atómica la creación de reservas recurrentes (pendiente que estaba en HU2) | Al pagar no se puede guardar la tarjeta ni cobrar si una de las semanas falla |
| 2026-10-18 | HU4 pasa a Isalleth como Developer (Derlin Reviewer, Gabriel QA) | Equilibrar: cada integrante es Dev de 2 historias |
| 2026-10-28 | HU3: previsión con la media de cada día de la semana usando 8 semanas completas; histórico contado por fecha de uso | Método simple y explicable; la fecha de uso representa la demanda real del recurso y evita mezclar la fecha de creación de la reserva |
| 2026-10-28 | HU2 (#3): disponibilidad por franjas de 09:00–21:00, validación de bloqueos en el servidor y refresco del calendario por rango sin recargar | Criterios de aceptación del issue y hallazgo de QA del PR #7 sobre la lista local desactualizada |
| 2026-10-28 | Derlin sigue en el equipo pero no puede hacer tareas (se le dañó la computadora). Nuevos roles: HU2 Dev Isalleth (Review y QA Gabriel); HU4 y HU5 Dev Gabriel (Review y QA Isalleth); QA de HU3 pasa a Gabriel | Con dos personas, quien no desarrolla hace revisión y QA, y nadie aprueba su propio PR |
| 2026-10-28 | HU4: se puede cancelar o modificar hasta 2 h antes del inicio (configurable con `DJANGO_RESERVA_ANTELACION_HORAS`) | Dar tiempo a otro usuario para usar la franja liberada; el valor se puede ajustar sin tocar código |
| 2026-10-28 | HU4: al modificar se cambian fecha y hora de inicio, se mantiene la duración y no se cambia el recurso ni el pago | Cambio acotado y sin nuevo cobro; cambiar duración o recurso equivale a una reserva nueva |
