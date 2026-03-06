# AsistenteAjedrez — Contexto del Proyecto

## Descripción
Bot de WhatsApp para gestionar clases de ajedrez. Permite registrar pagos, clases, cancelaciones, y sincronizar automáticamente con Google Calendar. Incluye un dashboard web para visualización y gestión.

## Stack técnico
- Python + Flask + Twilio (WhatsApp)
- SQLite (base de datos local)
- Claude API Haiku (intérprete de mensajes)
- Google Calendar API (fuente de verdad para clases)
- APScheduler (notificaciones automáticas)
- Dashboard web (HTML/JS/CSS vanilla, servido por Flask)

## Arquitectura principal
**Google Calendar es la fuente de verdad para clases.** El bot no crea ni mueve eventos en Calendar. Las clases se sincronizan desde Calendar a la DB. Las cancelaciones se manejan desde el bot (regla 24hs).

## Base de datos

### Tablas
- **alumnos** — info fija de cada alumno (nombre, país, moneda, método de pago, modalidad, representante, alias, activo)
- **pagos** — cada pago registrado (alumno_id, fecha, monto, moneda, metodo, notas)
- **clases** — cada clase agendada/dada/cancelada (alumno_id, fecha, hora, estado, origen, google_event_id, **pago_id**)
- **promociones** — rangos de precio por alumno (clases_desde, clases_hasta, precio_por_clase, moneda)
- **eventos_ignorados** — google_event_ids y títulos a ignorar en la sync

### Estados de clases
- `agendada` — clase programada
- `dada` — clase realizada
- `cancelada_con_anticipacion` — canceló a tiempo, queda como crédito
- `cancelada_sin_anticipacion` — canceló tarde, se cobra igual
- `cancelada_por_profesora` — no se cobra ni acredita

### Campo pago_id en clases
Cada clase tiene un `pago_id` (FK a pagos) que se asigna cuando se registra el pago. Esto permite saber qué clases están pagas y vincular pagos con clases específicas.

## Archivos principales

### bot_v3.py
Webhook de Flask + lógica de acciones. Sistema de `acciones_pendientes` para resolver ambigüedad de nombres. Manejo inteligente de pagos: detecta modalidad, clases sin pagar, calcula monto según promo y vincula clases al pago.

### interprete.py
Recibe mensajes en lenguaje natural y devuelve JSON con acción y datos usando Claude Haiku. Incluye historial de conversación para contexto. Reconoce "pago" y "pagó" (con y sin tilde).

### calendar_google.py
- `autenticar()` — conecta con Google Calendar
- `obtener_eventos(fecha_inicio, fecha_fin)` — trae eventos del calendario
- `buscar_alumno_en_evento(titulo)` — identifica alumno por título del evento con 3 pasadas: nombre completo → representante/alias → palabra suelta
- `sincronizar_mes(mes, anio)` — sincroniza un mes completo desde Calendar a DB

### sincronizacion.py
- `detectar_cambios(mes, anio)` — compara Calendar vs DB y devuelve nuevos/cancelados/modificados
- `procesar_cambios(cambios)` — procesa cambios y notifica
- `sincronizacion_diaria()` — sync automática del mes actual
- Los eventos ignorados se filtran por google_event_id Y por coincidencia parcial de título

### notificaciones.py
- `resumen_diario()` — clases del día a las 8am
- `recordatorio_pagos_mensuales()` — quién debe el día 1 a las 9am
- `resumen_cobros_mensuales()` — resumen de cobros del mes actual el día 1 a las 9am
- `alerta_paquetes()` — alumnos con 2 o menos clases restantes los lunes

### dashboard_routes.py
Blueprint Flask que sirve el dashboard web. Incluye:
- `/dashboard` — página principal
- `/dashboard/api/alumnos` — lista de alumnos con filtros
- `/dashboard/api/clases` — clases por mes con filtro por alumno y badge de pago
- `/dashboard/api/pagos` — pagos con clases asociadas (clases_resumen)
- `/dashboard/api/deuda` — cuánto debe cobrar por alumno/representante
- `/dashboard/api/sincronizar` — trigger manual de sync con Calendar
- `/dashboard/api/borrar_pago_id` — borrar un pago desde el dashboard
- Chat integrado: el dashboard puede enviar mensajes al bot y mostrar respuestas

### alumnos.py
CRUD de alumnos. `buscar_alumno_con_sugerencia()` con difflib (cutoff 0.4) busca por nombre Y representante. Cuando el fuzzy matchea por representante, no pide confirmación (es búsqueda válida). `buscar_en_todo()` busca tanto en nombres como en representantes.

### promociones.py
Lógica de precios escalonados. `resumen_cobro_alumno()` y `resumen_cobro_representante()` calculan el monto a cobrar dado un alumno/representante y un mes.

### pagos.py
Registro y consulta de pagos. `registrar_pago()` devuelve el `id` del pago insertado (necesario para vincular clases). `quien_debe_este_mes()` compara alumnos mensuales vs pagos del mes.

### clases.py
Agendar, cancelar (con regla 24hs), reprogramar clases. `alumnos_por_renovar_paquete()` detecta paquetes por vencer.

## Acciones del bot
1. `registrar_pago` — registrar un pago con vinculación automática de clases
2. `registrar_clase` — registrar clase con un alumno
3. `registrar_clases_multiple` — registrar clases con varios alumnos
4. `cancelar_clase` — cancelar próxima clase de un alumno
5. `quien_debe` — alumnos mensuales que no pagaron este mes
6. `cuanto_gane` — total cobrado en un mes
7. `resumen_alumno` — resumen de clases y pagos de un alumno
8. `alumno_nuevo` — agregar alumno con promo en un solo paso
9. `clases_del_mes` — clases agendadas de un alumno en un mes, con ✅ en las pagas
10. `que_tengo_hoy` — clases agendadas para hoy
11. `cuanto_debe_alumno` — cuánto cobrarle a un alumno/representante
12. `reprogramar_clase` — reprogramar clase a nueva fecha/hora
13. `ver_alumno` — ver todos los datos de un alumno o representante
14. `actualizar_dato_alumno` — modificar un campo de un alumno
15. `borrar_alumno` — dar de baja (inactivo) o borrar definitivamente
16. `actualizar_promo` — cambiar los rangos de precio de un alumno
17. `borrar_pago` — eliminar un pago registrado por error, con selección por clases asociadas
18. `ignorar_evento` — ignorar un evento de Calendar en syncs futuras
19. `aclaracion_alumno` — resolver ambigüedad cuando hay varios candidatos

## Lógica de pagos inteligente
Cuando se dice "X pagó" sin especificar monto:
1. Detecta la modalidad del alumno (Mensual, Semanal, Cada 10 clases)
2. Busca las clases sin pagar (`pago_id IS NULL`) del período correspondiente
3. Calcula el monto usando la promo del alumno según cantidad de clases
4. Si el monto coincide con la promo → registra directamente
5. Si hay diferencia → pide confirmación mostrando monto esperado vs recibido
6. Si las monedas son distintas → avisa y pide confirmación
7. Vincula las clases al pago (`pago_id`) para tracking

### Pagos de representantes (lógica combo)
Cuando un representante paga por varios alumnos:
1. Suma las clases de TODOS sus alumnos combinadas
2. Calcula el precio usando el total combinado (aplica promo de volumen correcta)
3. Distribuye el monto proporcionalmente: precio_unitario × clases_de_cada_alumno
4. Registra un pago separado por alumno pero al precio correcto del combo

Ejemplo: Charlie tiene Grace (4 clases) + Fiona (4 clases) = 8 clases totales → precio $25/clase (rango 6-8), no $26 (rango 4-5).

## Lógica de búsqueda de alumnos
1. LIKE por nombre de alumno (parcial)
2. LIKE por nombre de representante (parcial)  
3. Fuzzy matching por nombre de alumno (cutoff 0.4)
4. Fuzzy matching por nombre de representante (cutoff 0.4) → sin pedir confirmación
5. Si similitud < 0.4 → pregunta "¿quisiste decir X?" y espera confirmación
6. La comparación de similitud usa `max(sim_nombre, sim_representante)` para no penalizar búsquedas por apellido/representante

## Dashboard web
- Paleta de colores azul (--gold: #1a56a0, fondo blanco puro)
- Tabla de alumnos con columna ID visible
- Tabla de clases filtrable por alumno, con badge ✅ cuando la clase está paga
- Tabla de pagos con columna "Clases" que muestra días asociados
- Tabla de deuda agrupada por alumno/representante
- Botón de sync manual con Google Calendar
- Chat integrado para enviar mensajes al bot desde el dashboard
- Los pagos viejos (anteriores al campo pago_id) muestran "–" en clases asociadas

## Alumnos actuales
| Nombre | Representante | Moneda | Método | Modalidad |
|--------|--------------|--------|--------|-----------|
| Grace | Charlie Hettinger | Dólar | Wise | Online |
| Fiona | Charlie Hettinger | Dólar | Wise | Online |
| Henry Chen | Stephen Chen | Dólar | Wise | Online |
| Henry Cutler | Jeremy | Dólar | Wise | Online |
| Ximena | Lidia | Dólar | Wise | Online |
| Rafa | Lidia | Dólar | Wise | Online |
| Giuliana | Alison | Dólar | Wise | Online |
| John | — | Dólar | Wise | Cada 10 clases |
| Jeff | — | Dólar | Wise | Semanal |
| Michael | — | Dólar | PayPal | Semanal |
| Isabella | Roksana | Libra Esterlina | Wise | Mensual |
| Nouham (alias: noam) | — | Libra Esterlina | Wise | Mensual |
| Ruby | — | Libra Esterlina | Wise | Mensual |
| Kerem | Ozlam | Libra Esterlina | Wise | Mensual |
| Ilay | Karina | Pesos | Transferencia | Presencial domicilio (3h) |
| David y George | Morgan (Celia) | Pesos | Transferencia | Presencial domicilio (3h) |
| Lucas | — | Pesos | Transferencia | Presencial domicilio |
| Leila | Tameem | Dólar | Wise | Mensual |

## Horario semanal
- Lunes: Ilay 17:00, Henry Cutler 21:00
- Martes: Nouham 11:30, Michael 16:30, Ximena 19:00, Giuliana 20:30, Jeff 21:30
- Miércoles: Ruby 12:30, Kerem 14:00, Lucas 15:00, David y George 17:30
- Jueves: Isabella 15:00, Grace 17:30, Fiona 18:30, Rafa 20:30
- Viernes: Henry Chen 17:15, Leila 18:15
- Sábado: John 15:00

## Estado actual (marzo 2026)
- ✅ Bot funcionando en Railway (producción)
- ✅ Sync con Google Calendar operativa (automática 2x/día + manual desde dashboard)
- ✅ Dashboard web con chat integrado
- ✅ Registro de pagos con vinculación automática de clases (pago_id)
- ✅ Pagos de representantes con precio combo (total alumnos combinados)
- ✅ Clases muestran ✅ cuando están pagas
- ✅ Borrar pago muestra clases asociadas (no fecha de registro)
- ✅ Fuzzy matching por nombre Y representante sin falsos positivos
- ✅ Detección de moneda mejorada (ARS, GBP, USD, pesos, libras, etc.)
- ✅ Eventos de Calendar ignorables por título parcial
- ✅ Resumen de cobros mensuales automático el día 1
- ✅ Agregar alumno nuevo con promo en un solo paso

## Bugs conocidos / pendientes
- Pagos anteriores al campo pago_id no tienen clases vinculadas (datos históricos)
- Tabla de deuda en dashboard: pendiente agrupar por representante
- Promo de Fiona posiblemente corrupta (verificar y corregir si hace falta)

## Decisiones de diseño importantes
- Google Calendar es la fuente de verdad, el bot no crea eventos
- Clases presenciales (Ilay, Morgan): precio ya incluye hora de traslado (60000 pesos = 3h × 20000)
- Eventos recurrentes infinitos en Calendar → sync solo mira mes actual
- Alias de alumnos guardados en DB (columna `alias` en tabla alumnos)
- Reset de historial de conversación después de resolver ambigüedad de nombres
- `registrar_pago()` devuelve `cursor.lastrowid` para poder vincular clases
- Fuzzy matching de representantes no pide confirmación (es búsqueda legítima)
- Similitud calculada como `max(sim_nombre, sim_representante)` para evitar falsos rechazos

## Scripts de utilidad
- `cargar_clases.py` — carga clases recurrentes de un mes manualmente
- `cargar_promociones.py` — carga promos de todos los alumnos
- `test_bot.py` — prueba el bot en terminal sin WhatsApp
- `test_sincronizacion.py` — prueba la detección de cambios de Calendar
- `database.py` — crear tablas (correr una vez al inicio)
- `sincronizar_sheets.py` — sincronizar alumnos desde Google Sheets

# AsistenteAjedrez — Contexto del proyecto

## Stack técnico
- Python + Flask, SQLite, Twilio (WhatsApp), Claude API, Google Calendar API
- Hosting: Railway (~$5-7/mes)
- Archivos principales: bot.py, dashboard_routes.py, pagos.py, clases.py, sincronizacion.py, notificaciones.py, promociones.py, alumnos.py, database.py, calendar_google.py

## Estado actual del bot (WhatsApp)
Bot en producción. WhatsApp temporalmente bloqueado por verificación de Meta (pendiente resolver).

### Acciones implementadas
- registrar_pago (alumno individual y representante con precio combo)
- ver_clases / clases_del_mes — muestra estado con íconos 🟢 dada 🔵 agendada 🔴 cancelada ✅ paga
- clases_del_mes detecta representante automáticamente y muestra todas sus clases con nombre de alumno en cada línea, orden cronológico, sin preguntar
- cuanto_debe_alumno
- registrar_clase, cancelar_clase, reprogramar_clase
- borrar_pago
- agregar_alumno
- sincronizar (manual)

### Lógica de pagos
- Fecha del pago = primer día del mes de las clases (no la fecha de registro)
- Representantes: un pago por alumno con precio proporcional al combo
- Precio combo: se calcula sumando clases de todos los alumnos del representante

### Estados de clases
- agendada → clase futura en el calendario
- dada → clase pasada (se marca automáticamente en cada sync)
- cancelada_por_profesora / cancelada_con_anticipacion

### Sincronización
- Sync matutina (8:30): sincroniza calendario, marca clases pasadas como dadas
- Sync nocturna (20:00): marca clases de HOY como dadas, envía resumen por WhatsApp
- Al cancelar clase ya dada: desvincula pago_id (queda como crédito)

---

## Estado actual del dashboard

### Pestañas
- **Clases**: tabla con filtros (alumno, estado, pago, semana). Navegación por mes.
- **Cobros**: registro rápido de pagos con 3 vistas:
  - Por responsable: checkbox por grupo + Seleccionar todos → Abrir formularios → Registrar todos
  - Por semana: agrupado por semana con checkbox y registro en masa
  - Con checkboxes: selección libre, registra cada responsable por separado automáticamente
- **Pagos**: historial de pagos con borrado
- **Deuda**: alumnos con clases sin pagar agrupados por representante
- **Alumnos**: CRUD de alumnos
- **Gráficos**: barras anuales (agendadas/dadas/canceladas) + líneas de ingresos por moneda

### Métricas de cabecera
Alumnos activos, clases agendadas, canceladas, cobrado USD/GBP/ARS

### Chat integrado
Mismo bot que WhatsApp, accesible desde el dashboard

---

## Bugs conocidos / pendientes chicos
- Cobros por semana: handlers de sem-registrar-btn y sem-confirmar-btn a verificar
- Gráfico de ingresos: monedas en la misma escala (ARS vs USD/GBP incomparables) — PENDIENTE
- Vista por responsable: cobro en masa (abrir formularios + registrar todos) — implementado pero sin probar en prod aún

---

## Pendientes funcionales
1. Gráfico ingresos: selector de moneda + conversión estimada a USD via API tipo de cambio (frankfurter.app, sin key)
2. Cobros por semana: verificar que el flujo completo funciona en prod
3. Resolver verificación de WhatsApp con Meta

---

## Lo que faltaría para ser vendible a otros profes

### Mínimo viable (MVP vendible)
1. **Onboarding automatizado**: un script o flujo que configure un nuevo profe (nombre, alumnos, promociones, calendario) sin tocar código
2. **Multi-tenant**: cada profe tiene su propia DB o esquema aislado
3. **Deploy propio por cliente** o un SaaS compartido con autenticación por usuario
4. **Documentación mínima**: cómo usar el bot (5-6 comandos más comunes)
5. **Precio y modelo de cobro definido**: one-time setup + suscripción mensual por hosting, o SaaS fijo

### Ya resuelto (ventaja competitiva)
- Lógica de precio combo por volumen de clases
- Multi-moneda (USD, GBP, ARS)
- Representantes (padres que pagan por varios alumnos)
- Sync automática con Google Calendar
- Dashboard completo
- Notificaciones automáticas
- Tolerancia a errores tipográficos

### Riesgo principal
- Todavía depende de que cada cliente configure su propio Twilio + Google Calendar API + Claude API
- Eso requiere onboarding técnico o que lo hagas vos por cada cliente

---

## Historial de sesiones relevantes
- Sesión 1-N: construcción del bot base, lógica de promociones, pagos, alumnos
- Sesión reciente: dashboard con pestaña Cobros (3 vistas), cobros en masa, sync automática de clases dadas, gráficos anuales, fecha de pago = mes de las clases, clases_del_mes detecta representante
- Última sesión: fix bugs JS (function declarations anidadas, escapes \\' en triple-quoted HTML, SyntaxError por strings en Edge)