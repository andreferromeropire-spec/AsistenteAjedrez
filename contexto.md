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
| Python | **3.11+** en local y Railway; en **f-strings** no usar barra invertida dentro de `{...}` (en 3.11 falla; en 3.12 se relajó) — calcular antes en una variable y concatenar o interpolar sin `\` en la expresión. |

**Archivos principales:**
- `bot.py` — lógica principal del bot, routing de acciones, `procesar_mensaje()`
- `interprete.py` — llama a Claude Haiku para parsear mensajes en JSON de acción+datos
- `dashboard_routes.py` — Flask Blueprint con todas las rutas del dashboard + HTML/CSS/JS embebido en un string triple-quoted
- `portal_routes.py` — Flask Blueprint del portal de alumnos (login con Lichess/Google, vista `/portal/home`, APIs de recordatorios de mail y puzzle diario)
- `database.py` — `get_connection()`, `crear_tablas()`
- `clases.py` — `agendar_clase()`, `cancelar_clase()`, `resumen_clases_alumno_mes()`
- `pagos.py` — `registrar_pago()`
- `alumnos.py` — búsqueda y gestión de alumnos
- `promociones.py` — lógica de precios por volumen
- `sincronizacion.py` — sync con Google Calendar
- `notificaciones.py` — APScheduler para sync matutina (8:30) y nocturna (20:00)
- `calendar_google.py` — wrapper de Google Calendar API
- `demo_routes.py` — Blueprint Flask con rutas **`/demo/*`**: login simulado, dashboard/portal/trainer con banner DEMO, intercept de APIs del dashboard, reemplazos de enlaces (`/demo/login`, `/demo/trainer`, etc.)
- `demo_data.py` — datos ficticios (`DEMO_ALUMNOS`, `DEMO_PORTAL_RESUMEN`, etc.) para la demo
- `CONTEXTO_DEMO.md` — arquitectura y decisiones de la demo pública (detalle)

**Scripts de utilidad (no corren en producción):**
- `sincronizar_sheets.py` — importa alumnos desde Google Sheets (ID de planilla por env `GOOGLE_SHEET_ID`)

---

## Demo pública (`/demo/*`)

Vitrina sin login real ni escritura en la DB principal. El blueprint se registra en **`bot.py`**.

| Ruta | Rol |
|------|-----|
| **`/demo/login`** | Mismo HTML que **`LOGIN_HTML`** (`/login`): banner demo; Lichess/Google → **`/demo/portal`**; formulario profesora (cualquier contraseña) → **`/demo/dashboard`** vía JS (`preventDefault`). |
| **`/demo/dashboard`** | Reutiliza `DASHBOARD_HTML`; script en `<head>` que define **`DEMO_DATA`** (JSON desde Python) y un intercept de `fetch`/`XHR` para APIs GET del dashboard; chat POST sigue simulado; datos de `demo_data.py` + lista fija de clases demo. |
| **`/demo/portal`** | `PORTAL_HTML` + contenido home con resumen ficticio; enlaces internos reescritos a rutas `/demo/...`. |
| **`/demo/trainer`** | `trainer.html` + banner; salida del trainer apunta al flujo demo. |

**`DEMO_BANNER_SNIPPET`** (en `demo_routes.py`): pill DEMO, enlaces entre demos y al portfolio, toggles de tema e idioma (`data-es` / `data-en`), estados vacíos informativos en pestañas del dashboard que no cargan en demo, toast e intercept de **POST/PUT/DELETE** para acciones sin backend (con excepción del chat del dashboard demo). El JS del intercept **no** usa formato `%` de Python en el cuerpo: los datos van en **`DEMO_DATA`** y se concatena el script.

**Helpers de HTML:** `aplicar_enlaces_demo_login_logout`, `aplicar_rutas_navegacion_demo`, `aplicar_todas_las_rutas_demo` — reemplazan `Salir`, `/login`, `/trainer`, `/portal/...` por equivalentes **`/demo/...`** donde corresponde.

Documentación ampliada: **`CONTEXTO_DEMO.md`**.

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

**portal_accesos**
```
id, alumno_id, lichess_username, tipo_acceso, notas
```
- Relaciona usuarios externos (Lichess username o mail de Google) con uno o más alumnos para acceso al portal.

**portal_sessions**
```
id, alumno_id, lichess_username, created_at, last_seen
```
- Sesiones del portal de alumnos (auditoría básica de accesos recientes).

**recordatorios**
```
id, alumno_id, minutos_antes, alcance, canal, mail_destino, clase_id, activo, creado
```
- Configuración de recordatorios que pueden crear los alumnos desde el portal (hoy solo canal `mail`).

**recordatorios_enviados**
```
id, recordatorio_id, clase_id, enviado_en
```
- Log de envíos efectivamente disparados (evita reenviar varias veces el mismo recordatorio).

**posiciones**
```
id, fen, origen, dificultad, temas, creado
```
- Banco de posiciones para Position Check. `origen` guarda de dónde salió (`seed`, o `transcript: <partida/tema>` si vino de una lección).

**lecciones**
```
id, tema_principal, resumen_clase, nivel_alumno_estimado, conceptos (JSON),
errores_y_correcciones (JSON), temas_tag, origen, creado, estado, puzzles_sugeridos (JSON)
```
- Biblioteca de contenido pedagógico generado por IA a partir de clases reales. `estado`: `'borrador'` (default, recién generada, no asignable) | `'aprobada'` (Andrea la revisó, ya se puede asignar). `puzzles_sugeridos`: lista de puzzles reales de Lichess `[{puzzle_id, fen, moves, rating, themes, lichess_url}]`. Ver sección **Biblioteca de lecciones** más abajo.

**alumno_lecciones**
```
id, alumno_id, leccion_id, motivo, asignado_en, revisada_en
```
- Asignación de una lección de la biblioteca a un alumno puntual. `revisada_en` se completa solo cuando el alumno abre la lección en el portal (queda como su "historial").

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
- Google Calendar es la **fuente de verdad** para las clases. El bot NO crea ni cancela eventos en Calendar.
- **Cancelaciones:** solo desde Google Calendar. El bot no cancela clases; si el usuario pide cancelar, responde que debe eliminar el evento en Calendar y que la sincronización lo tomará automáticamente.
- Sync matutina (8:30): sincroniza calendario, marca clases pasadas como `dada`.
- Sync nocturna (20:00): marca clases de HOY como `dada`, envía resumen por WhatsApp.
- Al cancelar clase ya dada (desde Calendar + sync): desvincula `pago_id` (queda como crédito).
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
| `asignar_leccion` | Asignarle a un alumno una lección **aprobada** de la biblioteca (busca por tema/tag, desambigua si hay varias) |

### Búsqueda de alumnos (`buscar_o_sugerir_con_pendiente`)
Prioridad: exacto → alias → parcial (difflib). Si hay varios candidatos, pregunta cuál. Si hay un solo candidato con baja similitud, también pregunta.

**Importante:** "ilai" puede no matchear "Ilay" si hay otro alumno con mayor similitud en nombre o representante. La similitud se calcula como `max(sim_nombre, sim_representante)`.

### Historial de conversación
- Guardado en memoria (`historiales[numero]`), límite de 10 mensajes (`MAXIMO_MENSAJES_HISTORIAL`)
- Se limpia automáticamente si crece demasiado

---

## Biblioteca de lecciones (IA + puzzles de Lichess + aprobación)

Reemplaza el flujo manual de "correr un script sobre un archivo de transcript" por uno donde Andrea pega texto y revisa antes de publicar. Todo entra como **borrador** primero — ningún camino de entrada auto-publica.

### Generar una lección
- `extraer_leccion.py` expone `extraer_desde_texto(texto_crudo, es_resumen=False)`, además del uso por CLI (`extraer(ruta_transcript)`, que sigue andando sobre un archivo para uso manual/backfill).
  - `es_resumen=False`: intenta parsear el formato de closed captions de Zoom (`[Hablante] HH:MM:SS`); si el texto no matchea ese formato, lo trata como diálogo plano igual.
  - `es_resumen=True`: asume que es un resumen escrito por Andrea (no un transcript turno a turno) — el prompt le aclara al modelo que no invente momentos socráticos ni errores palabra por palabra si el resumen no los da.
- Extrae: `tema_principal`, `resumen_clase`, `nivel_alumno_estimado`, `conceptos`, `errores_y_correcciones`, `temas_tag`, y (si la clase analizó una partida continua) `partida_analizada` con jugadas y posiciones clave.

### Puzzles de Lichess sugeridos
- `lichess_puzzles.py` — `sugerir_puzzles(temas_tag, nivel_alumno_estimado, n=5)`. Reutiliza `trainer/puzzle_loader.py` (CSV de ~50k puzzles reales de Lichess, ya usado por el entrenador táctico) — no hay una segunda copia de la base ni de la lógica de filtrado.
- `MAPEO_TEMAS_A_LICHESS`: traduce los `temas_tag` en español (inventados por el prompt de extracción) al vocabulario fijo de "Themes" de Lichess (~60 valores: `pin`, `fork`, `discoveredAttack`, `mateIn2`, etc.). Patrones con nombre coloquial que Lichess no tiene taggeado (ej. "kiss of death") **no tienen match exacto posible** — el mapeo cae en el tema más parecido disponible, es una aproximación, no una búsqueda por patrón geométrico sobre el FEN.
- Rango de elo según `nivel_alumno_estimado` (mismos rangos que usa el entrenador: principiante 0-800, intermedio 800-1400, avanzado 1400+).

### Guardado, idempotencia y estado
- `cargar_leccion_a_posiciones.py` → `cargar_desde_dict(leccion)` es el punto único de guardado, usado tanto por el endpoint de producción `/cargar_leccion` (recibe el JSON de `extraer_leccion.py`, sin auth, pensado para llamarse desde el propio Railway) como por el nuevo endpoint del dashboard. **Idempotente**: no duplica posiciones (`fen` + `origen`) ni lecciones (`origen` + `resumen_clase`) si se re-envía el mismo contenido.
- Si las jugadas de la partida no se pueden reproducir (SAN inválido, típico cuando la clase parte de una posición de puzzle y no del inicio), la carga de posiciones falla en silencio pero la lección **igual** se guarda en la biblioteca — son pasos independientes a propósito.
- Toda lección nueva entra con `estado='borrador'` (default de la columna) sin importar el camino de entrada. Se vuelve asignable recién con `estado='aprobada'`.

### Endpoints del dashboard (`dashboard_routes.py`, todos `@login_required`)
| Endpoint | Qué hace |
|---|---|
| `POST /dashboard/api/lecciones/generar` | `{texto, es_resumen}` → extrae + sugiere puzzles + guarda como borrador. 502 si el modelo no devuelve contenido útil (no se guarda basura). |
| `GET /dashboard/api/lecciones?estado=borrador\|aprobada` | Lista filtrable por estado. |
| `POST /dashboard/api/lecciones/<id>/aprobar` | Pasa a `estado='aprobada'`. |
| `DELETE /dashboard/api/lecciones/<id>` | Solo si sigue en `borrador` (no se puede descartar algo ya aprobado/asignado desde acá). |
| `GET/POST /dashboard/api/alumno_lecciones` | Asignar una lección aprobada a un alumno (rechaza si `estado != 'aprobada'` o si ya tiene esa misma lección asignada sin revisar). |
| `PATCH /dashboard/api/lecciones/<id>` | Editar tema, resumen, tags, conceptos y errores/correcciones — de un borrador o de algo ya aprobado/asignado, sin restricción de estado. |

### Ver y editar (dashboard)
La "Biblioteca de lecciones" y los "Borradores pendientes" se muestran como tarjetas con el contenido completo (no solo tema/tags como al principio). Cada tarjeta tiene botón **Editar**, que la reemplaza por un formulario:
- Tema, resumen y tags: campos de texto normales.
- Conceptos y errores/correcciones: textareas de una línea por ítem, formato `Nombre :: Explicación` y `Error :: Corrección :: Principio general` respectivamente (parseado server-side en `_parsear_lineas_dobles_puntos`, `dashboard_routes.py`) — se eligió texto plano línea-por-línea en vez de una UI de filas dinámicas para no complicar el JS embebido en el string de Python.
- Todo el contenido que viene de la IA/DB se escapa antes de insertarse en el HTML (`_escHtml` en el JS del dashboard) — antes se insertaba crudo.

### Portal del alumno (`lecciones_routes.py`)
- `/portal/lecciones` (lista de lo asignado) y `/portal/lecciones/<id>` (detalle: resumen, conceptos, errores/correcciones, puzzles sugeridos como links directos a `lichess.org/training/<id>`). Valida que la lección esté asignada a ese alumno antes de mostrarla. Marca `revisada_en` la primera vez que la abre — eso es lo que queda como su "historial".

### Pendiente: mail de resumen de clase
Andrea quiere que además le llegue un mail al alumno con el resumen de la clase. La app ya manda mail con **Resend** (`notificaciones_portal.py`, hoy solo para recordatorios de clase — env vars `RESEND_API_KEY` y `RESEND_FROM`). Para la parte nueva:
- Dominio a usar: **`quietcenterchess.com`**, ya comprado por Andrea, pero **el DNS está en IONOS** (nameservers `ui-dns.*`), no en Cloudflare — no se puede configurar por API desde acá (no hay credenciales de IONOS en esta máquina, solo de Cloudflare).
- El dominio raíz ya tiene MX + SPF de IONOS (mail existente) — para no pisarlo, conviene verificar en Resend un **subdominio** (ej. `notificaciones.quietcenterchess.com`), no el dominio pelado.
- Falta: Andrea agrega el dominio/subdominio en Resend, copia los registros DNS que Resend le pide, y los carga en el panel de IONOS. Recién ahí se puede armar el envío del resumen (probablemente un endpoint nuevo o un hook en `api_lecciones_generar`/`aprobar` que dispare el mail al alumno asignado).

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
- **Lecciones**: generar lecciones con IA, revisar/aprobar borradores, asignarlas a alumnos. Ver sección **Biblioteca de lecciones**.
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

- **Para pasar un string entre comillas simples dentro de un `onclick="fn(...)"`, escribí `\\'` en el Python (doble barra)** — un solo `\'` es una barra de escape que Python interpreta como comilla simple literal (la elimina), dejando `''` en el JS servido → "Unexpected string" al parsear (mismo tipo de bug que `\n` vs `\\n`, ver más abajo). Ojo: `\u0027` tiene el mismo problema (Python también interpreta `\u`), así que tampoco sirve escrito tal cual. Verificado funcionando con `\\'` en `_itemCardHtml`/`_itemEditFormHtml` de la pestaña Lecciones.
- **Nunca function declarations anidadas** — usar `var fn = function() {}` en su lugar
- **Nunca strings con salto de línea literal** dentro de strings JS
- **Siempre usar rutas absolutas** en fetch: `/dashboard/api/...` (no `api/...`)
- **Event listeners por delegación**: los botones generados dinámicamente necesitan estar en el `document.addEventListener('click', ...)` central
- **Nunca escribir `\n`, `\t`, etc. sueltos dentro de este string** — `DASHBOARD_HTML`/`PORTAL_HTML` no son raw strings, así que Python los convierte a su carácter real antes de que el navegador vea el JS. Siempre `\\n`, `\\t` (doble barra) para que el navegador reciba la secuencia de escape.
- **Validar JS antes de deploy — usar el JS ya renderizado, no el archivo fuente**: `node -e 'new vm.Script(fs.readFileSync("dashboard_routes.py"))'` sobre el `.py` da falsos negativos (no agarra bugs de `\n`/`\'` sin escapar, porque corre sobre texto *antes* de que Python lo interprete) **y falsos positivos** (código ya arreglado con `\\n`/`\\'` se ve "roto" en el fuente crudo, porque ahí todavía son dos barras). El chequeo confiable es extraer el HTML ya servido y validar *eso*:
  ```python
  import bot
  c = bot.app.test_client()
  with c.session_transaction() as sess: sess['dashboard_logged_in'] = True
  html = c.get('/dashboard').data.decode()
  # extraer el <script> grande (no el que carga Chart.js por src) y correr
  # new vm.Script(js) con node sobre ESE texto, o mejor: levantar el server
  # de verdad (PORT=5050 python bot.py) y mirar la consola del navegador —
  # eso además agarra errores de runtime que un parser no ve.
  ```

---

## Google: OAuth y piloto (Calendar por profe)

- **Instancia Andrea:** token de usuario en **`GOOGLE_TOKEN_JSON`** (nombre exacto en env según despliegue). Scopes: Calendar + Sheets + Drive. Calendario `primary`.
- **Instancias piloto (otros profes):** opcionalmente usan **su** Calendar sin dar contraseña:
  - Variables: `GOOGLE_SERVICE_ACCOUNT_JSON` (JSON de la cuenta de servicio) + `GOOGLE_CALENDAR_ID` (ID del calendario del profe).
  - El profe comparte su calendario con el email de la cuenta de servicio (permiso "Ver todos los detalles"). Ver **CALENDAR_PILOTO.md**.
- Si ambas están seteadas, `calendar_google.py` usa cuenta de servicio y ese calendario; si no, usa token de usuario y `primary`.

---

## Railway y deploy

- Push a GitHub → Railway auto-deploya
- A veces cambios solo en `dashboard_routes.py` no triggean deploy → agregar comentario en `bot.py` para forzarlo
- DB SQLite en volumen montado en `/data`
- Variables de entorno críticas: `DB_PATH`, `GOOGLE_TOKEN_JSON` (u otras vars de Google según instancia), `ANTHROPIC_API_KEY`, `TWILIO_*`, `DASHBOARD_PASSWORD`, `SECRET_KEY`, `RESEND_API_KEY` + `RESEND_FROM` (mail de recordatorios y, a futuro, resumen de clase — ver **Biblioteca de lecciones**)
- Gráfico ingresos en USD: `DOLAR_BLU_ARS`, `TASA_GBP_USD`. Opcional por instancia: `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CALENDAR_ID` (ver sección Piloto).

---

## Piloto: varios profes (multi-instancia)

- **Modelo:** 1 profe = 1 servicio en Railway = 1 DB = 1 link de dashboard (y opcionalmente 1 número de WhatsApp). No hay usuarios ni login: quien tiene el link + contraseña entra a ese dashboard.
- **Docs:** `ONBOARDING_PILOTO.md` (checklist por profe), `INSTRUCCIONES_PARA_PILOTOS.md` (qué enviar a los colegas), `PLANILLA_ALUMNOS_PILOTO.md` (importación masiva desde Sheets), `CALENDAR_PILOTO.md` (cada profe con su Google Calendar sin compartir contraseña).
- **Por cada servicio:** `DB_PATH` distinto (ej. `/data/chess_profe_maria.db`), `DASHBOARD_PASSWORD` distinta. Opcional: `GOOGLE_SHEET_ID` para importar alumnos desde su planilla; `GOOGLE_SERVICE_ACCOUNT_JSON` + `GOOGLE_CALENDAR_ID` para leer su Calendar (ellos comparten el calendario con el email de la cuenta de servicio).
- **Endpoints útiles:** `/setup` (crear tablas), `/sincronizar_alumnos` (import desde Sheet si `GOOGLE_SHEET_ID` está definido), `/sincronizar_calendario` (sync Calendar), `/reactivar_clase?alumno=Nombre` (reactivar una clase cancelada en la DB, ej. desde Railway).

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
- **Duplicados en `cargar_desde_dict`**: re-cargar el mismo JSON de lección duplicaba posiciones exactas — ahora chequea `(fen, origen)` y `(origen, resumen_clase)` antes de insertar.
- **Dashboard colgado en "Cargando..."/"—" en todas las pestañas**: `.join('\n')` en `_leccionEditFormHtml` (JS del dashboard) — como `DASHBOARD_HTML` es un string triple-quoted normal de Python (no raw), esa `\n` se convertía en salto de línea real *antes* de llegar al navegador, dejando un newline sin escapar dentro de un string JS de comillas simples → `SyntaxError` al parsear, que aborta *todo* el script y por eso ningún `fetch` de `/dashboard/api/*` llegaba a dispararse. Arreglado a `\\n` (doble barra, como ya hace el resto del archivo — ver `texto.split('\\n')` en el chat del dashboard). **Al escribir JS dentro de estos strings de Python, cualquier secuencia de escape pensada para el navegador (`\n`, `\t`, etc.) necesita la barra doblada.** La validación estática con `node -e "new vm.Script(...)"` (mencionada más arriba en este doc) NO detecta este bug porque se corre sobre el texto fuente de Python, antes de que Python interprete el `\n` — hay que probarlo sirviendo la página de verdad (levantar el server y mirar la consola del navegador, o extraer el HTML ya renderizado y validar eso).
- **Mismo bug, segunda variante**: `\'` (una sola barra) en un `onclick="fn('...')"` — Python interpreta `\'` como comilla simple literal y la elimina, dejando `''` (dos comillas seguidas sin operador) en el JS → "Unexpected string" al parsear. Encontrado al agregar los botones de conceptos/patrones (`_itemCardHtml`), que pasan `tipo` (un string) como argumento — los botones de lecciones nunca habían tenido este problema porque solo pasaban `l.id` (un número, sin comillas). Arreglado a `\\'` (doble barra). Regla ya sumada más arriba en "JavaScript en el dashboard".

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
| F8 | Mail de resumen de clase al alumno (ver sección **Biblioteca de lecciones → Pendiente: mail de resumen de clase**) — falta que Andrea configure el subdominio de `quietcenterchess.com` en Resend/IONOS. |
| F9 | Traer de Lichess qué puzzles resolvió/falló cada alumno (requiere pedir scope OAuth `puzzle:read` en el login del portal) — evaluado, no iniciado. |

---

## Decisiones de diseño confirmadas

- Google Calendar es fuente de verdad para clases — el bot NO crea ni cancela eventos; las cancelaciones se hacen desde Calendar
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
- Python 3.11+ + Flask, SQLite (DB_PATH), Railway, GitHub auto-deploy
- JS embebido como string triple-quoted en dashboard_routes.py (>2000 líneas)
- Claude Haiku para NLP, Twilio para WhatsApp
- Demo pública: `demo_routes.py` (`/demo/login`, `/demo/dashboard`, `/demo/portal`, `/demo/trainer`) — ver `CONTEXTO_DEMO.md`

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
Demo pública: /demo/* (demo_routes.py + CONTEXTO_DEMO.md).
```