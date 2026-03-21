# CONTEXTO_DEMO — AsistenteAjedrez

## 1. GOAL

La demo pública debe permitir mostrar el sistema sin login y sin tocar datos reales:

- **`/demo/dashboard`**: vista de profesora con el mismo diseño que `/dashboard`, mostrando métricas, tabla de clases, pestañas y secciones pobladas con datos ficticios.
- **`/demo/portal`**: vista de portal de alumno con el mismo layout que `/portal/home`, para un alumno demo (por ahora “Lucas M.”), sin OAuth ni base de datos.
- **`/demo/trainer`**: acceso directo al entrenador táctico `/trainer` sin requerir login de portal, reutilizando la lógica real del trainer pero en un contexto claramente marcado como demo.

Requisitos clave:
- Ninguna ruta `/demo/*` debe requerir sesión ni credenciales.
- Ninguna ruta `/demo/*` debe leer ni escribir en la base de datos principal.
- Toda la demo debe ser claramente identificable como **DEMO** (banner) y debe poder cambiar de tema (light/dark) y de idioma (ES/EN) sin romper el diseño.

---

## 2. CURRENT STATE

### 2.1 Qué funciona

- **Rutas demo registradas**:
  - `GET /demo/dashboard`:
    - Reutiliza `DASHBOARD_HTML` de `dashboard_routes.py` (mismo HTML/CSS/JS que el dashboard real).
    - Inyecta un banner de demo arriba del layout real.
    - Inyecta un script de intercept en `<head>` que:
      - Simula respuestas JSON para varias APIs (`/dashboard/api/resumen`, `/dashboard/api/clases`, `/dashboard/api/alumnos`, `/dashboard/api/pagos`, `/dashboard/api/deudores`, `/dashboard/api/recordatorios_alumnos`, `/dashboard/api/entrenamiento_resumen`, `/dashboard/api/ultima_sync`).
      - Usa datos derivados de `DEMO_ALUMNOS` y de una lista fija `demoClases`.
    - Métricas superiores (`Alumnos activos`, `Clases agendadas`, montos por moneda) se llenan con datos fake.
    - La tabla de clases deja de estar en “Cargando…” y muestra las `demoClases`.
  - `GET /demo/portal`:
    - Reutiliza `PORTAL_HTML` y `PORTAL_HOME_CONTENT` desde `portal_routes.py`.
    - Inyecta el banner de demo justo después de `<body>`.
    - Inyecta un `RESUMEN_JSON` fake a partir de `DEMO_PORTAL_RESUMEN` (alumno “Lucas M.”).
    - Algunos textos extra del portal tienen ahora `data-es` / `data-en` para que respondan al toggle de idioma.
  - `GET /demo/trainer`:
    - Renderiza `templates/trainer.html` (misma UI que `/trainer`).
    - Inyecta el banner de demo.
    - Reemplaza solo en este contexto el botón `#btn-exit-portal` para que diga “← Back to demo” y redirija a `/demo/dashboard`.
    - El resto de la lógica del trainer (puzzles, APIs `/trainer/api/...`, guardado local en trainer DB) se mantiene igual que en producción.

- **Banner demo**:
  - Definido en `DEMO_BANNER_SNIPPET` dentro de `demo_routes.py`.
  - Incluye:
    - Pill “DEMO” en verde oliva.
    - Texto “Esta es una demo en vivo con datos ficticios” / “This is a live demo with fictional data”.
    - Links a:
      - `/demo/dashboard`
      - `/demo/portal`
      - `/demo/trainer`
      - `https://andreferdev.com` (“← Volver al portfolio” / “← Back to portfolio”).
    - Toggle de tema (usa `localStorage['dashboard-theme']` y llama al `setTheme` real).
    - Toggle de idioma (usa `localStorage['demo_lang']` y cambia textos con `data-es` / `data-en`).
  - Se inyecta como HTML+CSS dentro de `<body>` (sticky, z-index alto) para las tres rutas demo.

### 2.2 Qué no está del todo resuelto

- `/demo/dashboard`:
  - El intercept de las APIs se ejecuta y rellena:
    - Métricas superiores (resumen).
    - Tabla de clases.
    - Algunas pestañas adicionales (por ejemplo “Portal”, “Entrenamiento”) reciben datos, pero no se ha validado exhaustivamente cada combinación de filtros/vistas.
  - Aún pueden quedar pestañas que sigan llamando endpoints no interceptados (p.ej. gráficos anuales o ingresos anuales, si se activan desde la UI).
- `/demo/portal`:
  - Solo hay un alumno demo (`Lucas M.`) y un `RESUMEN_JSON` simple.
  - Todavía no se inyectan todas las traducciones (`data-es` / `data-en`) para cada etiqueta o botón; hay textos que siguen solo en español.
- `/demo/trainer`:
  - Sigue usando las APIs reales `/trainer/api/...` y la DB local del trainer (no se han simulado endpoints de trainer).
  - No hay intercept ni fake data para `/trainer/api/*` en modo demo (por diseño actual).

### 2.3 Archivos nuevos / modificados para la demo

- **Nuevos**:
  - `demo_data.py`
  - `demo_routes.py`
  - `CONTEXTO_DEMO.md` (este archivo)

- **Modificado**:
  - `bot.py`:
    - Se agregó:
      - `from demo_routes import demo_bp`
      - `app.register_blueprint(demo_bp)`

### 2.4 Endpoints interceptados (URL exacta, desde los `console.log` del intercept)

Todos como **substrings** en `url.indexOf(...) !== -1`:

- `/dashboard/api/resumen`
- `/dashboard/api/clases`
- `/dashboard/api/alumnos`
- `/dashboard/api/pagos`
- `/dashboard/api/deudores`
- `/dashboard/api/recordatorios_alumnos`
- `/dashboard/api/entrenamiento_resumen`
- `/dashboard/api/ultima_sync`

---

## 3. ARCHITECTURE OF THE DEMO

### 3.1 `demo_routes.py` — flujo general

- Importa:
  - `DASHBOARD_HTML` desde `dashboard_routes.py`.
  - `PORTAL_HTML` + `PORTAL_HOME_CONTENT` desde `portal_routes.py`.
  - `DEMO_ALUMNOS`, `DEMO_INGRESOS`, `DEMO_PORTAL_RESUMEN` desde `demo_data.py`.
- Define:
  - `demo_bp = Blueprint("demo", __name__)`.
  - `DEMO_BANNER_SNIPPET` (HTML+CSS+JS para banner y toggle de idioma/tema).
  - `DEMO_DASHBOARD_INTERCEPT` (script completo con `<script>...</script>`).
  - `DEMO_DASHBOARD_INTERCEPT_JS` (versión del mismo script sin las etiquetas `<script>`).

#### `/demo/dashboard`

1. Construye `mes_options` igual que `/dashboard`:
   - Usa `date.today()` y el mismo listado de meses.
2. Genera el HTML base:
   - `html = DASHBOARD_HTML.replace("{MES_OPTIONS}", mes_options).replace("{AUTH_ERROR_BANNER}", "")`.
3. Inyecta el intercept **dentro de `<head>`**:
   - `html = html.replace("<head>", "<head><script>" + DEMO_DASHBOARD_INTERCEPT_JS + "</script>", 1)`.
   - Esto garantiza que el intercept se ejecute **antes** de cualquier otro script del dashboard.
4. Inyecta el banner demo después de `<body>`:
   - Si existe `<body>`:
     - `html = html.replace("<body>", "<body>" + DEMO_BANNER_SNIPPET, 1)`.
5. Construye datos fake en Python:
   - Calcula:
     - `total_alumnos`, `clases_agendadas`, `clases_canceladas`, y `pagos_json` a partir de `DEMO_ALUMNOS`.
   - Define una lista `demo_clases` (10 clases ficticias con nombres, países, monedas, estados).
6. Rellena los placeholders dentro del script:
   - `DEMO_DASHBOARD_INTERCEPT_JS` tiene placeholders `%(...)` para `total_alumnos`, `clases_agendadas`, etc.
   - Se genera `filled_js = DEMO_DASHBOARD_INTERCEPT_JS % {...}` y se reemplaza en el HTML.

#### `/demo/portal`

1. Usa `DEMO_PORTAL_RESUMEN` como `resumen` y `nombre`.
2. Construye el contenido como hace `portal_home()`:
   - `contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)`
   - `contenido = contenido.replace("{RESUMEN_JSON}", json.dumps(resumen))`
   - `contenido = contenido.replace("PORTAL_NOMBRE_JSON", json.dumps(nombre))`
3. Envuelve con `PORTAL_HTML`:
   - `html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)`
4. Inyecta el banner demo tras `<body>`:
   - Igual que en `/demo/dashboard`.
5. Añade algunos `data-es` / `data-en` por reemplazo de strings para:
   - Título de “Recordatorios”.
   - Título de “Entrenamiento de patrones”.
   - Botón de “Salir” del portal.

#### `/demo/trainer`

- Renderiza `trainer.html` con `render_template("trainer.html")`.
- Inserta el banner:
  - Sustituye `<body>` por `<body class="theme-dark">` y añade `DEMO_BANNER_SNIPPET` dentro del body (antes del contenido).
- Inserta un script pequeño para cambiar el botón:
  - Busca `#btn-exit-portal`, cambia texto a “← Back to demo” y el `onclick` para navegar a `/demo/dashboard`.

### 3.2 `DEMO_BANNER_SNIPPET`

- Declarado como string multilínea en la parte superior de `demo_routes.py`.
- Contiene:
  - CSS para `.demo-banner`, `.demo-badge`, `.demo-link`, toggles.
  - HTML del banner con:
    - Lado izquierdo: badge “DEMO” + texto `data-es` / `data-en`.
    - Lado derecho: nav links a rutas demo + link al portfolio.
    - Grupo de toggles:
      - Botón de tema con icono 🌙/☀️.
      - Controles ES/EN.
  - Script inline que:
    - Lee y escribe `localStorage['dashboard-theme']` y llama `window.setTheme` o cambia `data-theme` directamente.
    - Lee y escribe `localStorage['demo_lang']` y cambia todo elemento con `data-es` / `data-en`.

Se inyecta en todas las páginas demo justo después de `<body>`.

### 3.3 `DEMO_DASHBOARD_INTERCEPT` (y `DEMO_DASHBOARD_INTERCEPT_JS`)

- `DEMO_DASHBOARD_INTERCEPT`:
  - String que contiene `<script>(function(){...})();</script>`.
  - Dentro:
    - Construye en JS:
      - `demoResumen` (para `/dashboard/api/resumen`).
      - `demoClases` (para `/dashboard/api/clases`).
      - Derivados: `demoAlumnos`, `demoPagos`, `demoDeudores`, `demoRecordatorios`, `demoEntrenamientoResumen`, `demoUltimaSync`.
    - Define `makeJsonResponse(body)` que retorna:
      - `new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })`
      - o un objeto compatible con `.json()` en caso de no existir `Response`.
    - Intercepta:
      - **fetch**:
        - Loguea: `console.log('[DEMO] intercepted fetch:', url)`
        - Devuelve fake data para URLs que contengan cualquiera de los endpoints listados en la sección 2.4.
      - **XMLHttpRequest**:
        - Loguea: `console.log('[DEMO] intercepted XHR:', url)`
        - Simula `readyState = 4`, `status = 200`, `responseText = JSON.stringify(fakeData)`.
- `DEMO_DASHBOARD_INTERCEPT_JS`:
  - Versión de `DEMO_DASHBOARD_INTERCEPT` sin `<script>`/`</script>`.
  - Se inyecta en `<head>` como:
    - `<head><script>DEMO_DASHBOARD_INTERCEPT_JS</script>...</head>`
  - Luego, en `demo_dashboard()`, se reemplazan los placeholders `%(...)` por valores concretos de Python.

### 3.4 Datos fake (`demo_data.py`)

- `DEMO_ALUMNOS`, `DEMO_INGRESOS`, `DEMO_PORTAL_RESUMEN` viven en `demo_data.py`.
- Son usados por `demo_routes.py` para:
  - Calcular métricas de resumen del dashboard.
  - Alimentar el `RESUMEN_JSON` del portal demo.

---

## 4. KNOWN BUGS

### 4.1 Internal Server Error actual

- Contexto:
  - Hubo momentos donde `/demo/dashboard` o `/demo/portal` devolvieron “Internal Server Error” durante el desarrollo de la demo.
  - Causas probables:
    - Errores de formato en `DEMO_DASHBOARD_INTERCEPT_JS % {...}` (placeholders que no calzaban con el diccionario pasado).
    - Modificaciones simultáneas de `DEMO_DASHBOARD_INTERCEPT` sin actualizar `DEMO_DASHBOARD_INTERCEPT_JS`.
  - Último cambio importante antes de los ISE:
    - Movimiento del intercept a `<head>` y reemplazo de placeholders en `DEMO_DASHBOARD_INTERCEPT_JS`.
    - Añadido de múltiples estructuras JS (demoAlumnos, demoPagos, etc.) dentro del mismo bloque de script.

### 4.2 JSON parse error

- Error: `SyntaxError: JSON.parse: unexpected character at line 1 column 1`.
- Causa:
  - Inicialmente el intercept devolvía HTML en lugar de JSON válido, o un string incorrecto, para las llamadas de fetch/XHR.
- Solución parcial:
  - Estandarizar las respuestas del intercept a:
    - `new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })`
  - Asegurar que `JSON.stringify(...)` se llama siempre sobre estructuras de datos puras, sin mezclar texto HTML.
  - Al mover el intercept a `<head>`, se garantizó que **todas** las llamadas del dashboard real pasen primero por el intercept.

### 4.3 Tabs / secciones probablemente aún vacías

- Aunque los endpoints clave están interceptados, no se ha validado todo:
  - Pestañas que usan:
    - `/dashboard/api/grafico_anual`
    - `/dashboard/api/ingresos_anuales`
    - `/dashboard/api/clases_sin_pagar`
  - Si desde la UI se activan estas vistas (ej. pestaña de “Gráficos” o controles específicos), seguirán llamando al backend real y podrían fallar o devolver datos reales (no deseado en modo demo).

---

## 5. PENDING TASKS (prioridad)

1. **Revisar y corregir cualquier Internal Server Error residual**
   - Validar en logs qué excepción exacta se produce al cargar `/demo/dashboard` y `/demo/portal`.
   - Verificar que `DEMO_DASHBOARD_INTERCEPT_JS % {...}` no falla (todos los placeholders cubiertos).

2. **Agregar fake responses para endpoints restantes del dashboard**
   - Actualizar intercept para manejar también:
     - `/dashboard/api/grafico_anual`
     - `/dashboard/api/ingresos_anuales`
     - `/dashboard/api/clases_sin_pagar`
   - Usar `demoClases` y `DEMO_INGRESOS` como base para construir respuestas con la misma forma que en `dashboard_routes.py`.

3. **Pulir language toggle**
   - Listar textos que aún no cambian ES/EN en:
     - `/demo/dashboard`:
       - Nombres de pestañas (`Clases`, `Cobros`, `Pagos`, `Deuda`, `Alumnos`, `Portal`, `Entrenamiento`, `Graficos`).
       - Títulos de secciones dentro de cada tab.
       - Tooltips o textos de botones (ej. “Sincronizar”, “Registrar seleccionadas”).
     - `/demo/portal`:
       - Textos dentro de cards de “Entrenamiento de patrones”, “Recordatorios”, etc. que aún no tienen `data-es` / `data-en`.
   - Sin tocar `dashboard_routes.py` ni `portal_routes.py`, inyectar `data-es` / `data-en` vía `replace` en `demo_routes.py` para los textos más visibles.

4. **Mejoras visuales del banner**
   - Ajustar colores para que:
     - Use exactamente el mismo azul oscuro que el header del dashboard en el tema por defecto.
     - La pill “DEMO” use el mismo verde que la marca de `AndreFerDev`.
   - Asegurar que en tema light el banner se integre bien (sin romper contraste).

5. **Opcional**: interceptar también `/trainer/api/...` en contexto demo
   - Solo si se quiere una demo de trainer completamente offline y sin DB local.

---

## 6. FAKE DATA REFERENCE

### 6.1 `DEMO_ALUMNOS` (desde `demo_data.py`)

```python
DEMO_ALUMNOS = [
    {
        "id": 1,
        "nombre": "Lucas M.",
        "moneda": "USD",
        "precio_clase": 30,
        "clases_mes": 8,
        "pagado_mes": 210,
        "deuda_mes": 30,
        "pais": "AR",
    },
    {
        "id": 2,
        "nombre": "Grace K.",
        "moneda": "GBP",
        "precio_clase": 25,
        "clases_mes": 6,
        "pagado_mes": 150,
        "deuda_mes": 0,
        "pais": "UK",
    },
    {
        "id": 3,
        "nombre": "Henry S.",
        "moneda": "USD",
        "precio_clase": 28,
        "clases_mes": 5,
        "pagado_mes": 84,
        "deuda_mes": 56,
        "pais": "US",
    },
    {
        "id": 4,
        "nombre": "Emma R.",
        "moneda": "ARS",
        "precio_clase": 9000,
        "clases_mes": 4,
        "pagado_mes": 27000,
        "deuda_mes": 9000,
        "pais": "AR",
    },
]
```

### 6.2 `demo_clases` (definido en `demo_dashboard()` en `demo_routes.py`)

```python
demo_clases = [
    {
        "fecha": "2026-03-02",
        "hora": "18:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 1,
        "ausente": 0,
        "nombre": "Lucas M.",
        "pais": "AR",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-05",
        "hora": "19:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 2,
        "ausente": 0,
        "nombre": "Grace K.",
        "pais": "UK",
        "moneda": "GBP",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-06",
        "hora": "17:00",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Henry S.",
        "pais": "US",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-08",
        "hora": "18:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 3,
        "ausente": 0,
        "nombre": "Emma R.",
        "pais": "AR",
        "moneda": "ARS",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-09",
        "hora": "20:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Santiago P.",
        "pais": "CL",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-11",
        "hora": "19:00",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Ana L.",
        "pais": "MX",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-12",
        "hora": "18:00",
        "estado": "cancelada-profe",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Michael B.",
        "pais": "US",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-14",
        "hora": "16:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 4,
        "ausente": 0,
        "nombre": "Lucía G.",
        "pais": "ES",
        "moneda": "EUR",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-16",
        "hora": "18:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 1,
        "nombre": "Tom H.",
        "pais": "CA",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-18",
        "hora": "19:30",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Valentina R.",
        "pais": "AR",
        "moneda": "ARS",
        "modalidad": "online",
    },
]
```

Con este archivo, una nueva sesión de Cursor mañana debería poder:
- Ver rápidamente qué hace cada parte de la demo.
- Identificar qué endpoints ya están interceptados.
- Ver la forma exacta de los datos fake.
- Saber qué bugs y tareas pendientes atacar en qué orden. 
