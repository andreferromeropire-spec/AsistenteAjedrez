# AsistenteAjedrez — Contexto del proyecto

## Qué es esto
Bot de WhatsApp + dashboard web para que Andrea (profesora de ajedrez argentina) gestione su negocio: alumnos, clases, pagos y cobros. Reemplaza planillas manuales.

Construido con Python/Flask, deployado en Railway. El bot corre en el mismo proceso que el dashboard.

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Backend | Python + Flask |
| Base de datos | SQLite (Railway volume en `/data`, ruta configurada con `DB_PATH`) |
| Bot WhatsApp | Twilio (activo) + Meta WhatsApp Business API (pendiente verificación) |
| Intérprete NLP | Claude API — modelo Haiku (barato, rápido) |
| Calendario | Google Calendar API |
| Hosting | Railway (~$5-7/mes) |
| Deploy | Push a GitHub → Railway auto-deploya |

**Archivos principales:**
- `bot.py` — lógica principal del bot, routing de acciones, `procesar_mensaje()`
- `interprete.py` — llama a Claude Haiku para parsear mensajes en JSON de acción+datos
- `dashboard_routes.py` — Flask Blueprint con todas las rutas del dashboard + HTML/CSS/JS embebido en un string triple-quoted
- `database.py` — `get_connection()`, `crear_tablas()`
- `clases.py` — `agendar_clase()`, `cancelar_clase()`, `resumen_clases_alumno_mes()`
- `pagos.py` — `registrar_pago()`
- `alumnos.py` — búsqueda y gestión de alumnos
- `promociones.py` — lógica de precios por volumen
- `sincronizacion.py` — sync con Google Calendar
- `notificaciones.py` — APScheduler para sync matutina (8:30) y nocturna (20:00)
- `calendar_google.py` — wrapper de Google Calendar API

**Scripts de utilidad (no corren en producción):**
- `cargar_clases.py` — carga clases recurrentes de un mes manualmente
- `cargar_promociones.py` — carga promos de todos los alumnos
- `test_bot.py` — prueba el bot en terminal sin WhatsApp
- `sincronizar_sheets.py` — importa alumnos desde Google Sheets

---

## Base de datos

### Tablas principales

**alumnos**
```
id, nombre, representante, pais, idioma, contacto_preferido, mail, whatsapp,
horas_semanales, dia_habitual, precio, moneda, metodo_pago, modalidad,
notas_recordatorio, alias, clases_credito
```
- `alias`: nombre alternativo para cuando Google Calendar usa un nombre distinto al de la DB (ej: "Noam" en Calendar → "Nouham" en DB)
- `clases_credito`: crédito acumulado si pagó más clases de las dadas
- `modalidad`: `"Mensual"` (combo, paga adelantado) o `"Semanal"` (clase suelta, paga después)

**clases**
```
id, alumno_id, fecha (YYYY-MM-DD), hora, estado, pago_id, ausente
```
- `estado`: `agendada` → `dada` (automático en sync) | `cancelada_con_anticipacion` | `cancelada_sin_anticipacion` | `cancelada_por_profesora`
- `ausente`: 0 (presente o no aplica) | 1 (faltó a clase dada)
- `pago_id`: FK a pagos — NULL significa no paga aún

**pagos**
```
id, alumno_id, fecha, monto, moneda, metodo, clases_ids (JSON), notas
```
- `fecha`: primer día del mes de las clases pagadas (no la fecha de registro)
- `clases_ids`: lista JSON de IDs de clases que cubre este pago

**promociones**
```
id, alumno_id, moneda, clases_desde, clases_hasta, precio_por_clase
```
Rangos de precio según volumen mensual. Ej: 1-3 clases → $35, 4-6 → $32, 7+ → $30.

---

## Lógica de negocio

### Modalidades de pago
- **Mensual (combo)**: paga al inicio del mes por todas las clases agendadas. Se cobra dadas + agendadas.
- **Semanal (clase suelta)**: paga después de cada clase. Precio siempre de 1 clase, aunque se cobren varias juntas.

### Representantes
Un adulto (padre/madre) puede ser representante de varios alumnos. El pago se registra a nombre del representante pero se vincula a cada alumno. El precio combo considera la suma de clases de todos los alumnos del representante.

### Precio combo
Se calcula sumando clases de todos los alumnos de un representante y buscando el rango en la tabla de promociones.

### Sincronización con Google Calendar
- Google Calendar es la **fuente de verdad** para las clases. El bot NO crea eventos de Calendar.
- Sync matutina (8:30): sincroniza calendario, marca clases pasadas como `dada`.
- Sync nocturna (20:00): marca clases de HOY como `dada`, envía resumen por WhatsApp.
- Al cancelar clase ya dada: desvincula `pago_id` (queda como crédito).
- Eventos recurrentes infinitos → sync solo mira el mes actual.
- Títulos de eventos ignorables se pueden registrar con `ignorar_evento`.

### Clases presenciales
Ilay y Morgan tienen clases presenciales. El precio ya incluye hora de traslado (60000 ARS = 3h × 20000).

### Política de cancelaciones
- Con anticipación (>24h): no se cobra, queda como crédito.
- Sin anticipación: se cobra igual.
- Por la profesora: no se cobra.

---

## Bot (WhatsApp)

### Flujo de un mensaje
1. Mensaje llega por WhatsApp vía Twilio webhook → `procesar_mensaje()`
2. Si hay un `acciones_pendientes` para ese número, se resuelve primero (sin llamar al intérprete)
3. Si no, se llama a `interpretar_mensaje()` → Claude Haiku devuelve JSON `{accion, datos}`
4. `ejecutar_accion()` ejecuta la lógica correspondiente

### Sistema de pendientes (`acciones_pendientes`)
Diccionario en memoria `{numero_telefono: datos_pendiente}`. Se usa para:
- Pedir confirmación antes de registrar pago
- Desambiguar nombre cuando hay varios alumnos parecidos
- Preguntar ausente vs cancelar cuando el alumno faltó

**Casos especiales que se procesan ANTES del bloque `isdigit`:**
- `esperando = 'ausente_o_cancelar'`: respuesta "1" o "2" (o texto) para decidir si marcar ausente o cancelar la clase

### Acciones implementadas en `interprete.py`
| Acción | Descripción |
|---|---|
| `registrar_pago` | Alumno o representante pagó |
| `registrar_clase` | Se dio clase con un alumno |
| `registrar_clases_multiple` | Se dieron clases con varios alumnos |
| `cancelar_clase` | El alumno avisa con anticipación que no viene |
| `marcar_ausente` | El alumno NO asistió a una clase que ya pasó |
| `desmarcar_ausente` | Quitar ausencia registrada por error (el alumno sí vino) |
| `quien_debe` | Ver quién no pagó este mes |
| `cuanto_gane` | Total cobrado en un período |
| `resumen_alumno` | Ver datos de un alumno |
| `alumno_nuevo` | Agregar alumno |
| `clases_del_mes` | Ver clases agendadas de un alumno |
| `que_tengo_hoy` | Clases del día |
| `cuanto_debe_alumno` | Cuánto cobrarle a un alumno |
| `reprogramar_clase` | Cambiar fecha/hora de una clase |
| `aclaracion_alumno` | Responde cuál alumno cuando hay ambigüedad |
| `ver_alumno` | Ver datos completos de un alumno |
| `actualizar_dato_alumno` | Cambiar un dato de un alumno |
| `borrar_alumno` | Dar de baja un alumno |
| `actualizar_promo` | Cambiar precios de un alumno |
| `borrar_pago` | Eliminar pago registrado por error |
| `sincronizar_calendario` | Sync manual con Google Calendar |
| `ignorar_evento` | Marcar evento de Calendar como no-clase |

### Búsqueda de alumnos (`buscar_o_sugerir_con_pendiente`)
Prioridad: exacto → alias → parcial (difflib). Si hay varios candidatos, pregunta cuál. Si hay un solo candidato con baja similitud, también pregunta.

**Importante:** "ilai" puede no matchear "Ilay" si hay otro alumno con mayor similitud en nombre o representante. La similitud se calcula como `max(sim_nombre, sim_representante)`.

### Historial de conversación
- Guardado en memoria (`historiales[numero]`), límite de 10 mensajes (`MAXIMO_MENSAJES_HISTORIAL`)
- Se limpia automáticamente si crece demasiado

---

## Dashboard

### Estructura
Flask Blueprint en `dashboard_routes.py`. Todo el HTML/CSS/JS está embebido en un string triple-quoted de Python. Esto tiene reglas estrictas de escritura JS (ver sección técnica abajo).

### Pestañas
- **Clases**: tabla filtrable (alumno, estado, pago, semana). Navegación por mes.
- **Cobros**: registro rápido de pagos. Tres vistas: por responsable, por semana, con checkboxes.
- **Pagos**: historial con botón borrar.
- **Deuda**: alumnos con clases sin pagar (agrupado por representante — pendiente mejorar).
- **Alumnos**: CRUD.
- **Gráficos**: barras anuales + líneas de ingresos.

### Sillita (marcar/desmarcar ausente)
- Solo aparece en clases con `estado = 'dada'`
- Opacidad baja (0.25) = presente. Opacidad llena (1.0) = ausente.
- Click hace toggle: llama a `POST /dashboard/api/marcar_ausente` con `{nombre_alumno, fecha}`
- El backend hace toggle real en la DB (0↔1) y devuelve `{ok, ausente}`
- Después del toggle recarga `cargarClases()` para mostrar estado actualizado
- El event listener está en `document.addEventListener('click', ...)` — delegación de eventos para capturar botones generados dinámicamente

### Auto-refresh
- Tabla de clases se recarga cada 30 segundos si esa pestaña está activa
- Así los cambios del bot (desde WhatsApp) aparecen en el dashboard solos

### Chat integrado
- Mismo bot que WhatsApp, accesible desde el panel derecho
- Cuando la respuesta contiene palabras como "registré", "pagó", "agende", recarga el dashboard automáticamente

---

## JavaScript en el dashboard — reglas importantes

El JS está dentro de un string triple-quoted Python. Esto implica:

- **Nunca usar `\'` dentro del string** — usar `\u0027` o reestructurar con función separada
- **Nunca function declarations anidadas** — usar `var fn = function() {}` en su lugar
- **Nunca strings con salto de línea literal** dentro de strings JS
- **Siempre usar rutas absolutas** en fetch: `/dashboard/api/...` (no `api/...`)
- **Event listeners por delegación**: los botones generados dinámicamente necesitan estar en el `document.addEventListener('click', ...)` central
- **Validar JS antes de deploy**: `node -e 'new vm.Script(fs.readFileSync(...))'`

---

## Google OAuth

- Token guardado en variable de entorno `GOOGLE_TOKEN_JSON` (nombre exacto, case-sensitive)
- Generado con scopes de Calendar + Sheets + Drive
- Si el scope en el código es más angosto que el del token → error de auth
- En `calendar_google.py` los scopes deben coincidir exactamente con los del token

---

## Railway y deploy

- Push a GitHub → Railway auto-deploya
- A veces cambios solo en `dashboard_routes.py` no triggean deploy → agregar comentario en `bot.py` para forzarlo
- DB SQLite en volumen montado en `/data`
- Variables de entorno críticas: `DB_PATH`, `GOOGLE_TOKEN_JSON`, `ANTHROPIC_API_KEY`, `TWILIO_*`

---

## Bugs conocidos y pendientes

### ✅ Resueltos
- **Sillita dashboard**: toggle real sin `confirm()`, URL correcta, una sola sillita siempre visible, auto-refresh cada 30s
- **Desmarcar ausente desde bot**: "ilay sí vino", "desmarcar ausente ilay", "quita la ausencia de ilay el 2"
- **marcar_ausente en intérprete**: antes se mapeaba a `cancelar_clase`, ahora es acción separada con distinción clara
- **Handler "1"/"2" para ausente_o_cancelar**: procesado antes del bloque `isdigit`
- **Borrar pago de a uno**: flujo con confirmación funciona correctamente
- **B5**: "jeff pagó 4 clases" ahora registra la cantidad (cantidad_clases en intérprete)
- **B11**: Pago del mes incluye clases ya dadas (query con estado agendada o dada)
- **B8**: Monto por clase según combo/suelta al cambiar cantidad; flechita step 1
- **F1**: Instrucción "T para todos" y "varios por coma" en mensaje de borrar pagos
- **B1**: Cobros 2–3 clases usan primer rango; aviso promo solo si monto no está en la lista

### 🐛 Bugs pendientes

_(ninguno)_

### ⚠️ Limitaciones conocidas

| ID | Descripción | Alternativa |
|---|---|---|
| F1 | Desde el bot (WhatsApp) solo se puede borrar **un pago a la vez**; "T" o "2 3" no se procesan. | Desde el dashboard podés borrar varios a la vez (checkboxes en la pestaña Pagos). |

**Causa técnica (F1):** El estado pendiente se guarda en DB con la clave `numero` (From de Twilio). Al responder "T" o "2 3", en la segunda request esa clave no coincide (Twilio puede enviar From con formato distinto entre mensajes), así que no se encuentra el pendiente y el mensaje cae en el intérprete → "No entendí bien". Se probó normalizar el número (quitar `whatsapp:`, canonizar a `+digits`); si en tu entorno From sigue variando, habría que buscar el pendiente por otro criterio (ej. última actividad por número sin importar formato) o unificar From del lado de Twilio.

### ✨ Features pendientes

| ID | Descripción |
|---|---|
| F3 | Formulario cobros: monto azul = mes actual, deuda anterior en rojo separada |

| F5 | Alumnos al día: aparecen al final en verde con botón de cobro disponible |
| F7 | Clases canceladas: mostrar en rojo en `"ver clases"`, no desaparecer |

---

## Decisiones de diseño confirmadas

- Google Calendar es fuente de verdad para clases — el bot NO crea eventos
- `registrar_pago()` devuelve `cursor.lastrowid` para poder vincular clases
- Fuzzy matching: similitud = `max(sim_nombre, sim_representante)` — evita falsos rechazos
- Fuzzy matching de representantes no pide confirmación
- Reset de historial de conversación después de resolver ambigüedad de nombres
- Pagos anteriores al campo `pago_id` no tienen clases vinculadas (datos históricos, no arreglar)
- Precio de clase suelta: siempre precio de 1 clase, aunque se cobren varias juntas
- Ausente: la clase se cobra igual. Cancelada: no se cobra.

---

## Cursor — reglas del proyecto (`.cursor/rules/asistente_ajedrez.mdc`)

Pegar esto en `.cursor/rules/asistente_ajedrez.mdc` para que Cursor entienda el proyecto automáticamente:

```markdown
# AsistenteAjedrez — Reglas del proyecto

## Stack
- Python 3 + Flask, SQLite (DB_PATH), Railway, GitHub auto-deploy
- JS embebido como string triple-quoted en dashboard_routes.py (>2000 líneas)
- Claude Haiku para NLP, Twilio para WhatsApp

## Convenciones de código
- Español para nombres de variables, funciones y comentarios
- Sin type hints
- Siempre cerrar conexiones SQLite con conn.close()
- Usar database.get_connection() para toda conexión a la DB

## Reglas críticas JS en dashboard_routes.py
- NUNCA function declarations anidadas → usar var fn = function() {}
- NUNCA \' dentro del string Python → usar \u0027
- SIEMPRE rutas absolutas en fetch: /dashboard/api/... (nunca api/...)
- Botones dinámicos DEBEN estar en document.addEventListener('click', ...)
- Antes de proponer cambios JS, verificar que no rompe el string Python

## Arquitectura del bot (bot.py)
- procesar_mensaje() maneja pendientes ANTES de llamar al intérprete
- Orden estricto en procesar_mensaje(): pendientes especiales → isdigit → else (intérprete)
- Casos especiales (ausente_o_cancelar, confirmar_borrado_multiple) van ANTES del bloque isdigit()
- buscar_o_sugerir_con_pendiente() para TODA búsqueda de alumnos
- Google Calendar es fuente de verdad — el bot NUNCA crea eventos en Calendar

## Principios de negocio
- Ausente (ausente=1): clase se cobra igual, estado queda 'dada'
- Cancelada: no se cobra, estado cambia
- Representante: un adulto paga por varios alumnos, precio combo se calcula sumando clases de todos
- Clase suelta: precio siempre de 1 clase aunque se cobren varias juntas
```

## Cómo arrancar una sesión en Cursor

Pegar esto al inicio del chat cuando el contexto sea importante:

```
Proyecto: bot WhatsApp + dashboard Flask para gestión de clases de ajedrez.
Stack: Python/Flask, SQLite en Railway, JS embebido en string triple-quoted Python.
Archivos clave: bot.py (lógica), interprete.py (NLP con Claude Haiku), dashboard_routes.py (UI), database.py, clases.py, pagos.py, alumnos.py.
Regla crítica: procesar_mensaje() en bot.py maneja pendientes especiales ANTES del bloque isdigit().
Regla crítica JS: nunca function declarations anidadas, siempre /dashboard/api/ en fetch.
Google Calendar es fuente de verdad — el bot nunca crea eventos.
```