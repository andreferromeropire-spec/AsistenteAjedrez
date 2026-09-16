# Diario de aprendizaje ("Learning Journal") — plan de implementación

Nombre técnico elegido: **no se renombra nada existente**. `lecciones` (ya construida hoy 2026-09-16) sigue siendo la entidad "mini-lección". Este documento agrega: conceptos globales reutilizables, patrones de pensamiento, progreso por alumno, y una experiencia de portal rediseñada. Internamente esto se llama "biblioteca pedagógica" en el código (`conceptos_biblioteca.py`), consistente con el nombre que ya usa `lichess_puzzles.py`.

## 0. Resumen para quien no lea todo el documento

- **Se reutiliza casi todo lo que ya existe**: `lecciones`, `alumno_lecciones`, `extraer_leccion.py`, `cargar_leccion_a_posiciones.py`, `lichess_puzzles.py`, el patrón borrador→aprobado, el patrón de tarjetas+edición del dashboard, y el widget de tablero drag-and-drop que ya usa el puzzle del día del portal.
- **Se agregan 6 tablas nuevas** (conceptos, patrones, y sus tablas de vínculo/progreso) + 1 columna nueva (`lecciones.clase_id`).
- **No se toca Position Check** (ya resuelve otra necesidad: análisis abierto de una posición, no vinculado a conceptos).
- **El trainer táctico se extiende con un parámetro nuevo** (`themes`), no se duplica.
- **Cero llamadas a la IA por visita del alumno** — todo el trabajo de IA pasa una sola vez, cuando la profesora genera/aprueba una lección.

---

## 1. Análisis de la arquitectura existente

### 1.1 Lo que ya existe y se reutiliza tal cual

| Pieza | Archivo | Rol en el plan nuevo |
|---|---|---|
| Extracción con IA de una clase | `extraer_leccion.py` (`extraer_desde_texto`) | Se **extiende** el prompt (no se reescribe) para pedir 2 campos nuevos: `reto_practico` y `patrones_pensamiento_detectados`. Los campos actuales (`conceptos`, `errores_y_correcciones`, `temas_tag`, `partida_analizada`) no cambian de forma. |
| Guardado + idempotencia | `cargar_leccion_a_posiciones.py` (`cargar_desde_dict`) | Se agrega un paso más: después de guardar la lección, vincula/crea conceptos y patrones (`conceptos_biblioteca.py`, nuevo). |
| Puzzles de Lichess por tema | `lichess_puzzles.py` (`sugerir_puzzles`, `MAPEO_TEMAS_A_LICHESS`) | Se generaliza para poder llamarse también con los `lichess_themes` de un **concepto** (no solo de `temas_tag` de una lección). Es la única fuente de "qué puzzle mostrar" — ni el trainer ni el portal duplican esta lógica. |
| Filtro de puzzles por Lichess Themes | `trainer/puzzle_loader.py` (`filter_puzzles`) | Ya soporta `themes` — **no se toca**. Solo se conecta un parámetro nuevo en `trainer_routes.py` que hoy no lo usa. |
| Patrón borrador → aprobado | `lecciones` (`estado`), endpoints `/dashboard/api/lecciones/*` | Se repite igual para `conceptos` y `patrones_pensamiento` — mismo estado, mismos verbos (generar/aprobar/descartar/editar). |
| Tarjetas + formulario de edición del dashboard | `dashboard_routes.py` (`_leccionCardHtml`, `_leccionEditFormHtml`, `_escHtml`) | Se clona el mismo patrón (HTML armado en JS, texto línea-por-línea para listas) para conceptos/patrones — no se introduce un framework nuevo. |
| Tablero interactivo (arrastrar una jugada sobre un FEN) | `portal_routes.py` (widget "Puzzle del día", `Chessboard(...)`, `onDrop`/`onSnapEnd`, chessboard.js/chess.js ya cargados globalmente en `PORTAL_HTML`) | Es el único tablero interactivo que existe hoy (Position Check usa una imagen estática; el trainer tiene su propio tablero pero para *otro* ejercicio — marcar piezas colgadas, no resolver la táctica). Se extrae su patrón a una función reusable para la nueva vista "Practicar concepto". |
| Auth del portal | `session["portal_alumno_ids"]`, `portal_login_required` | Sin cambios. Todo endpoint nuevo del portal lo respeta igual que `lecciones_routes.py` ya hace. |
| Auth del dashboard | `session["dashboard_logged_in"]`, `@login_required` | Sin cambios. |

### 1.2 Lo que NO existe y hay que construir

- Conceptos y patrones de pensamiento como **objetos globales reutilizables** (hoy `lecciones.conceptos`/`errores_y_correcciones` son JSON embebido por lección, sin normalizar ni deduplicar entre lecciones).
- Progreso del alumno por concepto/patrón (hoy `alumno_lecciones` solo trackea si abrió la lección, no qué aprendió de ella).
- Vínculo `lecciones.clase_id` → `clases.id` (hoy `lecciones.origen` es texto libre; no hay FK. Confirmado: una `clase` siempre tiene un solo `alumno_id`, nunca grupal).
- Página de detalle de lección con la estructura pedagógica pedida (hoy `lecciones_routes.py` muestra resumen/conceptos/errores como texto plano).
- "Mis conceptos" en el portal (no existe).
- Vista de práctica por concepto (no existe; se construye reutilizando el widget de tablero del puzzle diario).
- Parámetro `themes` en `trainer/api/session/start` (la función que lo consume ya existe, solo falta conectarlo).
- Historial pedagógico por alumno en el dashboard (no existe).

### 1.3 Decisión de diseño clave: A/B/C separados (como pediste)

- **A) Concepto global** (`conceptos`): contenido pedagógico reutilizable, escrito/aprobado una vez, se usa para todos los alumnos.
- **B) Aprendizaje del alumno** (`alumno_conceptos`): la relación de un alumno puntual con ese concepto (cuántas veces, cuándo, qué tan afianzado).
- **C) Clase/lección** (`lecciones` + `leccion_conceptos`): la instancia concreta donde ese concepto apareció, con la redacción específica que usó la profesora ese día (`leccion_conceptos.nota` guarda el `explicacion_dada` de esa clase puntual — la explicación canónica del concepto vive aparte, en `conceptos.explicacion_pedagogica`, y no se pisan entre sí).

Mismo patrón para patrones de pensamiento (`patrones_pensamiento` / `alumno_patrones` / `leccion_patrones`).

---

## 2. Modelo de datos

### 2.1 Tablas nuevas (`database.py`, mismo estilo `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` en `try/except`)

```sql
CREATE TABLE IF NOT EXISTS conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    descripcion_corta TEXT,
    explicacion_pedagogica TEXT,
    ejemplo TEXT,
    fen_ejemplo TEXT,
    errores_frecuentes TEXT,      -- JSON: ["...", "..."]
    lichess_themes TEXT,          -- coma-separado, para sugerir_puzzles()
    nivel TEXT,                   -- principiante | intermedio | avanzado | null
    estado TEXT DEFAULT 'borrador',  -- borrador | aprobado
    creado TEXT
);

CREATE TABLE IF NOT EXISTS patrones_pensamiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    ejemplo TEXT,
    estado TEXT DEFAULT 'borrador',
    creado TEXT
);

CREATE TABLE IF NOT EXISTS leccion_conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    leccion_id INTEGER NOT NULL,
    concepto_id INTEGER NOT NULL,
    nota TEXT,                    -- explicacion_dada tal como salió en ESA clase
    confianza TEXT,                -- confirmado | inferido
    FOREIGN KEY (leccion_id) REFERENCES lecciones(id),
    FOREIGN KEY (concepto_id) REFERENCES conceptos(id),
    UNIQUE(leccion_id, concepto_id)
);

CREATE TABLE IF NOT EXISTS leccion_patrones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    leccion_id INTEGER NOT NULL,
    patron_id INTEGER NOT NULL,
    nota TEXT,
    confianza TEXT,
    FOREIGN KEY (leccion_id) REFERENCES lecciones(id),
    FOREIGN KEY (patron_id) REFERENCES patrones_pensamiento(id),
    UNIQUE(leccion_id, patron_id)
);

CREATE TABLE IF NOT EXISTS alumno_conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    concepto_id INTEGER NOT NULL,
    veces_trabajado INTEGER DEFAULT 0,
    primera_leccion_id INTEGER,
    primera_vez_en TEXT,
    ultima_leccion_id INTEGER,
    ultima_vez_en TEXT,
    estado_dominio TEXT DEFAULT 'necesita_trabajo',  -- necesita_trabajo | en_practica | dominado
    actualizado TEXT,
    FOREIGN KEY (alumno_id) REFERENCES alumnos(id),
    FOREIGN KEY (concepto_id) REFERENCES conceptos(id),
    UNIQUE(alumno_id, concepto_id)
);

CREATE TABLE IF NOT EXISTS alumno_patrones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    patron_id INTEGER NOT NULL,
    veces_visto INTEGER DEFAULT 0,
    primera_leccion_id INTEGER,
    primera_vez_en TEXT,
    ultima_leccion_id INTEGER,
    ultima_vez_en TEXT,
    actualizado TEXT,
    FOREIGN KEY (alumno_id) REFERENCES alumnos(id),
    FOREIGN KEY (patron_id) REFERENCES patrones_pensamiento(id),
    UNIQUE(alumno_id, patron_id)
);
```

Y columnas nuevas en `lecciones`, todas nullable, sin tocar filas existentes (mismo `ALTER TABLE` en `try/except` ya usado hoy para `estado`/`puzzles_sugeridos`):
```sql
ALTER TABLE lecciones ADD COLUMN clase_id INTEGER REFERENCES clases(id);
ALTER TABLE lecciones ADD COLUMN reto_practico TEXT;
ALTER TABLE lecciones ADD COLUMN patrones_pensamiento TEXT;  -- JSON crudo de esta clase puntual, mismo rol que ya cumplen `conceptos`/`errores_y_correcciones`
```
(Corrección tras la primera revisión de este plan: la versión inicial solo agregaba `clase_id` y se olvidaba de dónde queda el dato *crudo* de `reto_practico`/patrones antes de la normalización en tablas — sin estas dos columnas, `_leccionEditFormHtml` no tendría de dónde leer/editar el reto y los patrones de esa clase puntual, igual que hoy lee `conceptos`/`errores_y_correcciones` desde la fila de `lecciones`.)

**Campos que la propuesta original sugería y NO se incluyen** (para no inventar de más): `preguntas_reflexion` en conceptos (se puede agregar después si hace falta; hoy nada la consume), `tags` separado de `lichess_themes` (sería redundante — `lichess_themes` ya cumple ese rol de forma accionable), un timestamp de "actualizado" en `conceptos`/`patrones_pensamiento` (alcanza con `creado`, igual que `lecciones` hoy).

**Migración**: igual que se hizo hoy con `lecciones.estado` — `ALTER TABLE` dentro de `try/except` en `crear_tablas()`, sin ningún `UPDATE` masivo (las tablas nuevas nacen vacías, no hay datos previos que migrar). Las 4 lecciones ya aprobadas **no** generan conceptos retroactivamente de forma automática (ver §1.2 y regla de "no migración masiva costosa" — hay un botón manual para eso, ver §7).

### 2.2 Por qué NO se propone `Lesson`/`Concept`/etc. como tablas nuevas con esos nombres
Ya existe `lecciones` cumpliendo el rol de "Lesson" con una biblioteca borrador→aprobado funcionando en producción desde hoy. Crear una tabla `Lesson` en paralelo duplicaría exactamente lo que la regla #26 pide evitar. Los nombres en español (`conceptos`, `patrones_pensamiento`) siguen la convención ya establecida en el resto del schema.

---

## 3. La IA — cambios en `extraer_leccion.py`

Cambio aditivo al JSON que ya devuelve el modelo (no se toca `conceptos`, `errores_y_correcciones`, `temas_tag`, `partida_analizada`):

```json
{
  "...(igual que hoy)...": "...",
  "reto_practico": "string corto o null — una acción concreta para la próxima partida",
  "patrones_pensamiento_detectados": [
    {"principio": "...", "contexto": "en qué momento de la clase se vio esto", "confianza": "confirmado" | "inferido"}
  ]
}
```

Se agrega también `"confianza": "confirmado" | "inferido"` a cada item de `conceptos` (ya existente), instruyendo en el prompt: **"confirmado" solo si el concepto se nombra o se trabaja explícitamente en el diálogo/resumen; "inferido" si lo dedujiste vos por contexto ajedrecístico sin que la clase lo mencione tal cual.** Esto es lo que la sección 24 pide (CONFIRMADO vs INFERIDO vs RECOMENDADO) — "recomendado" se resuelve aparte: son los puzzles sugeridos, que ya se presentan como sugerencia y nunca como hecho.

`patrones_pensamiento_detectados` es un campo **nuevo y separado** de `errores_y_correcciones.principio_general` (que sigue existiendo igual). La diferencia: un patrón puede reforzarse positivamente sin que haya un error de por medio (ej. "identificó bien la amenaza antes de mover"), mientras que `errores_y_correcciones` siempre parte de una equivocación real.

---

## 4. Matching y creación de conceptos/patrones — `conceptos_biblioteca.py` (nuevo módulo)

Ocurre **una sola vez, en el momento de guardar la lección** (dentro de `cargar_desde_dict`, después de `_cargar_leccion_biblioteca`) — sin llamada extra a la IA, usando coincidencia difusa determinística (`difflib`, ya usado en este proyecto para nombres de alumnos — mismo criterio, no una librería nueva):

```python
def _slugificar(nombre): ...  # minúsculas, sin acentos, guion_bajo

def _buscar_o_crear(conn, tabla, nombre, campos_nuevos):
    # 1. Slug exacto -> devuelve id existente.
    # 2. difflib.get_close_matches contra nombres existentes (cutoff 0.8) -> si matchea, devuelve id existente (NO pisa su contenido).
    # 3. Si no matchea nada -> INSERT nuevo con estado='borrador' y devuelve id nuevo.

def vincular_conceptos_y_patrones(conn, leccion_id, leccion_dict):
    # por cada concepto en leccion_dict['conceptos']:
    #   concepto_id = _buscar_o_crear(conn, 'conceptos', c['nombre'], {...})
    #   INSERT OR IGNORE INTO leccion_conceptos (leccion_id, concepto_id, nota, confianza)
    # idem para patrones_pensamiento_detectados -> patrones_pensamiento / leccion_patrones

def actualizar_progreso_alumno(conn, alumno_id, leccion_id):
    # por cada concepto/patron vinculado a esa leccion:
    #   UPSERT alumno_conceptos / alumno_patrones (veces_trabajado += 1, ultima_vez_en = ahora,
    #   primera_vez_en = ahora si no existía, recalcular estado_dominio)
```

Colisión de `slug` (dos lecciones seguidas proponiendo nombres levemente distintos que no llegan al cutoff de similitud pero slugifican igual): el `INSERT` va en `try/except IntegrityError` → si falla por `UNIQUE`, se vuelve a buscar por slug y se usa ese id existente en vez de fallar. No hace falta sufijo numérico ni intervención manual.

**Lógica de `estado_dominio` (simple y explicable, no arbitraria):**
- `veces_trabajado == 1` → 🔴 `necesita_trabajo` (recién visto una vez)
- `veces_trabajado` 2–3 → 🟡 `en_practica`
- `veces_trabajado >= 4` → 🟢 `dominado`

Es un proxy por **repetición/exposición**, no por resultado de ejercicios (todavía no hay un lazo que conecte "resolvió mal este puzzle" con "este concepto" — ver §9, fuera de alcance de esta fase). Se documenta así de manera explícita para que quede claro que es una primera aproximación razonable, no una medición de dominio real todavía.

`actualizar_progreso_alumno` se llama en los dos lugares donde hoy se crea una fila en `alumno_lecciones`:
- `bot.py` → branch `asignar_leccion`
- `dashboard_routes.py` → `api_alumno_lecciones_crear`

---

## 5. Backend — endpoints nuevos

### Dashboard (`dashboard_routes.py`, todos `@login_required`, mismo patrón que `/dashboard/api/lecciones/*`)

| Endpoint | Qué hace |
|---|---|
| `GET /dashboard/api/conceptos?estado=` | Lista conceptos filtrable. |
| `PATCH /dashboard/api/conceptos/<id>` | Editar nombre/descripción/explicación/ejemplo/errores frecuentes/lichess_themes/nivel. |
| `POST /dashboard/api/conceptos/<id>/aprobar` | `estado='aprobado'`. |
| `DELETE /dashboard/api/conceptos/<id>` | Solo si `estado='borrador'`. |
| `GET/PATCH/POST/DELETE /dashboard/api/patrones/<id>...` | Mismo CRUD, tabla `patrones_pensamiento`. |
| `GET /dashboard/api/alumnos/<id>/historial_pedagogico` | `{lecciones: [...], conceptos: [con estado_dominio], patrones: [...]}` para la vista de historial por alumno. |
| `POST /dashboard/api/lecciones/<id>/generar_retroactivo` | (opt-in, ver §7) — para una lección vieja sin `leccion_conceptos`, corre el matching manualmente sobre su JSON ya guardado (sin volver a llamar a la IA). |

Los endpoints de conceptos/patrones comparten una función genérica parametrizada por nombre de tabla (para no duplicar el mismo CRUD 2 veces).

### Portal (`lecciones_routes.py` extendido + nuevo `conceptos_routes.py`)

| Endpoint | Qué hace |
|---|---|
| `GET /portal/lecciones/<id>` | Rediseñada (ver §6) — ahora también trae conceptos/patrones vinculados y `reto_practico`. |
| `GET /portal/conceptos` | "Mis conceptos": lista `alumno_conceptos` del alumno actual con 🟢🟡🔴. |
| `GET /portal/conceptos/<id>` | Detalle: explicación, ejemplo, primera vez, lecciones donde apareció, errores frecuentes, botón practicar. |
| `GET /portal/practicar/concepto/<id>` | Vista de práctica (ver §6) — reusa `lichess_puzzles.sugerir_puzzles()`. |

Todos con `@portal_login_required`, y **validan que el concepto tenga al menos una fila en `alumno_conceptos` para ese alumno** antes de mostrar el detalle personal (la ficha del concepto en sí — nombre/explicación — es pública dentro del portal una vez que el alumno lo trabajó; no se expone nada de otros alumnos, solo el contenido pedagógico reutilizable del concepto, igual que hoy pasa con las lecciones asignadas).

---

## 6. Frontend

### 6.1 Portal — detalle de lección (`/portal/lecciones/<id>`)

Estructura pedida, reutilizando el shell (`PORTAL_HTML`/`PORTAL_CSS`) y las clases CSS ya existentes (`card`, `next-class`, `practicar-row`, `eyebrow`):

```
HOY TRABAJASTE
  {tema_principal}

IDEA PRINCIPAL
  {resumen_clase}

LO QUE APRENDISTE                    (conceptos vía leccion_conceptos)
  ▸ Ataque a la descubierta   [click para expandir: explicacion_pedagogica + ejemplo]
  ▸ Atracción
  ...

TU FORMA DE PENSAR                   (patrones vía leccion_patrones)
  • No descartes una jugada antes de calcularla.
  ...

TU RETO
  {reto_practico}

[ PRACTICAR ]  → /portal/practicar/concepto/<id del primer concepto> (o selector si hay varios)
```

Los conceptos se muestran colapsados por default (título nomás) y expanden inline con JS al hacer click (mismo patrón `<details>`/toggle liviano, sin librería nueva) — cumple "progresivo: resumen → profundización → práctica" sin pantallas nuevas.

### 6.2 Portal — "Mis conceptos" (`/portal/conceptos`)

Lista con badge de color (🟢🟡🔴 = `estado_dominio`), buscador simple (filtro client-side sobre la lista ya cargada — el volumen por alumno es chico, no hace falta un índice de búsqueda server-side). Click → detalle con: explicación, ejemplo, "primera vez: {fecha}, en {tema_principal de la lección}", lista de lecciones donde apareció (link a cada una), errores frecuentes, botón "Volver a practicar".

### 6.3 Portal — práctica por concepto (`/portal/practicar/concepto/<id>`)

Se extrae el bloque de tablero interactivo que hoy vive inline en el puzzle del día (`portal_routes.py`, `Chessboard(...)` + `onDrop`/`onSnapEnd`) a una función reusable que recibe una lista de puzzles (`{fen, moves}`) en vez de un solo puzzle diario fijo. Esta vista pide `lichess_puzzles.sugerir_puzzles(concepto.lichess_themes, nivel_del_alumno, n=5)` y deja al alumno resolverlos uno tras otro (mismo mecanismo de arrastrar pieza + feedback correcto/incorrecto que ya funciona hoy, sin motor de ajedrez nuevo).

### 6.4 Portal — home (`/portal/home`)

Card nueva chica, mismo estilo visual que `.next-class` (icono + eyebrow + valor, ver CSS exacto relevado en el análisis):
```
TU APRENDIZAJE
Última clase: {tema_principal de la última lección asignada}
Tu foco: {reto_practico}
[ PRACTICAR ]
```
Fuente de datos: la fila más reciente de `alumno_lecciones` para ese alumno (ya existe la query, solo se ordena por `asignado_en DESC LIMIT 1` y se hace join con `lecciones`). Si el alumno no tiene ninguna lección asignada, la card no se muestra (no sobrecargar el home con un estado vacío).

### 6.5 Dashboard — pestaña "Lecciones" (extendida)

- Cada tarjeta de lección (borrador o aprobada) ahora muestra también los conceptos/patrones vinculados como chips, con link a editarlos.
- Nueva sub-sección "Conceptos" (dentro de la misma pestaña, no una pestaña nueva): borradores pendientes + biblioteca aprobada, mismo patrón tarjeta+editar que ya existe para lecciones (se clona el JS, no se reinventa).
- Nueva sub-sección "Patrones de pensamiento": igual.
- Nueva sub-sección "Historial de un alumno": selector de alumno → muestra sus lecciones, conceptos (con estado_dominio) y patrones. Cubre la sección 13 del pedido sin agregar una pestaña nueva al nav principal.

### 6.6 Trainer

`trainer_routes.py`, `GET /trainer/api/session/start`: agrega parámetro opcional `themes` (coma-separado), se pasa a `filter_puzzles(df, themes.split(',') if themes else None, elo_min, elo_max, n)` en vez del `None` hardcodeado de hoy. `trainer.js` lee un query param `?themes=` de la URL al arrancar sesión y lo reenvía — cambio chico y aislado, no toca el resto del flujo del scanner de piezas colgadas. Esto deja abierta la puerta a linkear desde un concepto a `/trainer?themes=fork,pin` como alternativa a la vista de práctica nueva del §6.3 — pero el mecanismo **principal** de "Practicar" para un concepto es §6.3, porque el trainer resuelve un ejercicio distinto (detectar piezas colgadas, no resolver la táctica) y su tabla de progreso está hardcodeada a `tipo_patrones='vulnerables'`.

---

## 7. Retroactividad (clases antiguas)

No se ejecuta ninguna migración masiva automática. Las 4 lecciones que ya existen (Opera Game, 08-09, 09-09, 09-12) **no** generan conceptos/patrones solas. Se agrega un botón manual "Generar conceptos" en la tarjeta de cada lección aprobada del dashboard (llama a `POST /dashboard/api/lecciones/<id>/generar_retroactivo`, que corre `vincular_conceptos_y_patrones` sobre el JSON ya guardado — cero llamadas a la IA, cero costo) para que Andrea decida cuáles quiere sumar a la biblioteca de conceptos y cuáles no.

---

## 8. Seguridad

- Todos los endpoints de portal nuevos exigen `portal_login_required` y filtran explícitamente por `alumno_id` de la sesión (igual que `lecciones_routes.py` ya hace) — un alumno no puede pedir `alumno_conceptos`/`alumno_patrones` de otro id.
- El contenido *global* de un concepto (`conceptos.explicacion_pedagogica`, etc.) no es sensible por alumno — es la misma biblioteca para todos, como ya es "Position Check"'s banco de `posiciones`. Lo que sí se protege es la *relación* (`alumno_conceptos`) y el detalle de qué lección/clase generó qué.
- Nada de esto expone prompts internos ni datos administrativos — la IA solo corre server-side en endpoints `@login_required` (dashboard) o el endpoint de producción sin auth ya existente `/cargar_leccion` (mismo riesgo aceptado que ya existe hoy, no se amplía superficie).

## 9. Fuera de alcance (a propósito, para no inflar esto)

- Medir dominio real por resultado de ejercicios (correcto/incorrecto en un puzzle específico ligado a un concepto) — hoy `estado_dominio` es por repetición/exposición. Conectar resultados de práctica reales es una iteración futura, requiere que la vista de práctica (§6.3) guarde resultados por concepto, no solo por sesión.
- Traer de Lichess qué puzzles resolvió el alumno fuera de la plataforma (ya identificado como pendiente aparte en `contexto.md`, necesita scope OAuth `puzzle:read`).
- Búsqueda server-side indexada — el volumen por alumno es chico, alcanza con filtro client-side.
- Editar el contenido de un concepto ya *usado* de forma que afecte retroactivamente el histórico de un alumno de forma no evidente — se permite editar el concepto (afecta a futuro y a la ficha), no se versiona el contenido histórico.

## 10. Fases de implementación

1. **Datos + IA + matching** — schema nuevo, prompt extendido, `conceptos_biblioteca.py`, hooks en `cargar_desde_dict` y en los dos puntos de asignación.
2. **Dashboard** — CRUD de conceptos/patrones, chips en tarjetas de lección, historial por alumno, botón de generación retroactiva.
3. **Portal** — detalle de lección rediseñado, "Mis conceptos", vista de práctica, widget de home.
4. **Trainer** — parámetro `themes`.
5. **Tests** — ver `docs/TEST_PLAN.md` existente como referencia de estilo; casos nuevos listados en `docs/learning-journal-implementation.md` al terminar.

## 11. Verificación end-to-end (criterio de éxito, retomado del pedido)

Local, con el server levantado y un test_client autenticado (mismo método que se usó hoy para el fix del bug de escaping): generar una lección de prueba → confirmar conceptos/patrones creados como borrador → aprobar lección y conceptos → asignar a un alumno de prueba → confirmar `alumno_conceptos`/`alumno_patrones` actualizados → abrir `/portal/lecciones/<id>`, `/portal/conceptos`, `/portal/conceptos/<id>`, `/portal/practicar/concepto/<id>`, `/portal/home` → confirmar que un segundo alumno sin esa asignación no puede ver nada de eso. Recién después de validar todo en local, deploy a producción.
