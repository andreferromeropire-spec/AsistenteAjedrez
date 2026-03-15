## Onboarding piloto — AsistenteAjedrez

Guía para configurar una instancia nueva para un/a profe de ajedrez, con **DB propia** y, si querés, **bot de WhatsApp propio**, sin pedirles claves ni que hagan configuración técnica.

---

## Checklist rápido (para vos, por cada profe)

| Paso | Qué hacer | ✓ |
|------|-----------|---|
| 1 | Railway: nuevo servicio desde repo, nombre ej. `ajedrez-profe-maria` | |
| 2 | Env vars: copiar de tu instancia; cambiar `DB_PATH` (ej. `/data/chess_profe_maria.db`), `DASHBOARD_PASSWORD`, `SECRET_KEY` | |
| 3 | Esperar Running → abrir `https://<servicio>.railway.app/setup` → ver "Tablas creadas" | |
| 4 | Probar `https://<servicio>.railway.app/dashboard` con la contraseña | |
| 5 | (Opcional) Twilio: número nuevo → webhook `https://<servicio>.railway.app/webhook` | |
| 6 | Alumnos: **opción A** — cargar 2–3 desde el dashboard. **Opción B** — planilla Google Sheets; `GOOGLE_SHEET_ID` + `/sincronizar_alumnos` (ver **PLANILLA_ALUMNOS_PILOTO.md**) | |
| 7 | Calendar (opcional): si el profe usa **su** Google Calendar, ellos comparten su calendario con la cuenta de servicio y te pasan el ID; vos ponés `GOOGLE_SERVICE_ACCOUNT_JSON` + `GOOGLE_CALENDAR_ID` en su servicio (ver **CALENDAR_PILOTO.md**). Sin eso, podés crear clases de ejemplo por bot ("di clase con X hoy"). | |
| 8 | Enviar al profe: link del dashboard + contraseña + (si hay) número de WhatsApp + **instrucciones** (ver abajo) | |

---

## 0. Modelo del piloto

- **1 profe = 1 servicio en Railway = 1 DB = 1 número de WhatsApp.**
- Todo corre con **tus cuentas**:
  - Railway
  - Twilio (números de WhatsApp)
  - Google (Calendar + token `GOOGLE_TOKEN_JSON`)
  - Anthropic
- Cada profe:
  - Tiene su **propio dashboard** (URL distinta).
  - Opcionalmente, su **propio número de WhatsApp** (también bajo tu cuenta).
  - No configura nada técnico ni te da claves.

---

## 1. Preparar la “plantilla” base (una sola vez)

Antes de crear instancias nuevas, definir los valores base que vas a reutilizar:

- **Claves compartidas para todas las instancias**:
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_TOKEN_JSON`
  - `TWILIO_*`
  - Cualquier otra clave global que ya uses con Andrea.
- **Parámetros de referencia para ingresos en USD**:
  - `DOLAR_BLU_ARS` — cuántos pesos ARS = 1 USD (ej: `1200`).
  - `TASA_GBP_USD` — cuántos USD = 1 GBP (ej: `1.27`).

Idea: tener estos valores anotados en un lugar (nota local) para copiarlos rápido en cada servicio nuevo de Railway.

---

## 2. Checklist por cada profe X (Railway + DB + dashboard)

### 2.1 Crear servicio nuevo en Railway

1. Entrar a Railway con tu cuenta.
2. Crear **nuevo servicio** desde el repo de GitHub `AsistenteAjedrez`.
3. Nombrarlo, por ejemplo:
   - `ajedrez-profe-juan`
   - `ajedrez-profe-lucia`

### 2.2 Configurar variables de entorno para Profe X

En el servicio nuevo, en **Environment**:

1. **Copiar** todas las variables de la instancia que ya funciona (Andrea).
2. Ajustar las que deben ser distintas para esta profe:

- **Base de datos propia**
  - `DB_PATH`  
    - Ejemplo Andrea: `/data/chess_assistant.db`  
    - Profe Juan: `/data/chess_assistant_profe_juan.db`

- **Seguridad dashboard**
  - `DASHBOARD_PASSWORD`: una clave distinta por profe.  
    - Ej: `profeJuan2026`
  - `SECRET_KEY`: string aleatoria (puede ser algo simple para el piloto).

- **Ingresos en USD (si querés ajustarlos por instancia)**
  - `DOLAR_BLU_ARS` (ej: `1200`)
  - `TASA_GBP_USD` (ej: `1.27`)

El resto (`ANTHROPIC_API_KEY`, `GOOGLE_TOKEN_JSON`, `TWILIO_*`, etc.) se pueden mantener iguales entre instancias en este piloto.

### 2.3 Inicializar la base de datos

1. Esperar a que Railway marque el servicio como **Running**.
2. Visitar en el navegador:
   - `https://<servicio-profe-x>.railway.app/setup`
3. Confirmar que la página devuelva algo tipo:
   - `"Tablas creadas"`

Eso crea todas las tablas en la DB definida por `DB_PATH` de esa instancia.

4. Probar acceso al dashboard:
   - `https://<servicio-profe-x>.railway.app/dashboard`
   - Usar `DASHBOARD_PASSWORD` que configuraste.

En este punto, **Profe X ya tiene dashboard y DB propia, vacía**.

---

## 3. Conectar WhatsApp para Profe X (opcional pero ideal)

### 3.1 Crear/asignar número en Twilio

1. En tu cuenta de Twilio, comprar o asignar un número nuevo para el piloto (si todavía no lo hiciste).
2. En la configuración de ese número:
   - Webhook de mensajes entrantes (WhatsApp):  
     `https://<servicio-profe-x>.railway.app/webhook`
3. Guardar cambios.

### 3.2 Probar el bot de Profe X

1. Desde tu celular (o el de la profe), escribir al número nuevo:
   - `hola`
   - `quien debe este mes`
2. Verificar que el bot **responde algo** (aunque no haya datos todavía).

Si falla, revisar:

- Logs de Railway del servicio de esa profe.
- Que la URL del webhook de Twilio coincida exactamente con la URL pública de Railway.

---

## 4. Preparar datos mínimos para que la profe lo pruebe

La idea es que, cuando la profe entre, ya vea algo funcional sin tener que cargar todo desde cero.

### 4.1 Cargar algunos alumnos de ejemplo

En el dashboard de Profe X:

1. Ir a pestaña **Alumnos**.
2. Crear 2–3 alumnos típicos:
   - Nombre, representante
   - Moneda (Dólar / ARS$ / Libra Esterlina)
   - Modalidad (Mensual / Semanal)
   - Precio por hora o promo base
3. Opcional: definir promo (rangos de clases) para al menos un alumno, así se ve el combo en Cobros.

### 4.2 Crear clases de ejemplo

Opciones:

**A. Sólo con el bot (más simple)**

- Usar el chat integrado del dashboard o WhatsApp:
  - `"di clase con Juan hoy"`
  - `"clase con Ana el martes"`

**B. Con Google Calendar (más real)**

- Crear un calendario de Google para Profe X.
- Compartirlo con tu service account (el mismo que ya usás).
- Crear algunos eventos de clases (títulos compatibles con el sistema actual).
- En el dashboard:
  - Pestaña **Clases** → botón **Sincronizar** (mes actual).

Con unas pocas clases ya es suficiente para que vean:

- Clases por mes
- Cobros
- Deuda
- Gráficos (clases e ingresos)

---

## 5. Guion para mostrar el sistema a la profe

Cuando hagas la demo o la primera sesión con cada profe:

1. Enviarles el link de su dashboard:
   - `https://<servicio-profe-x>.railway.app/dashboard`
   - Pasarles la contraseña (`DASHBOARD_PASSWORD`).

2. Recorrer juntos (5–10 minutos):

- **Clases**: ver calendario de clases del mes.
- **Cobros**: mostrar cómo registrar un pago rápido.
- **Pagos**: historial y opción de borrar un pago.
- **Deuda**: quién debe este mes.
- **Gráficos**:
  - Clases por mes.
  - Ingresos mensuales en USD (Total y, si quieren, por moneda desde la leyenda).

3. Si también van a usar WhatsApp en el piloto:

- Darles el **número de su bot** (el de su instancia).
- Probar en vivo:
  - `"pago Juan 100 dolares wise"`
  - `"quien debe este mes"`

4. Pedir feedback explícito:

- ¿Qué parte les resultó más útil?
- ¿Qué parte les resultó confusa?
- ¿Qué les gustaría que haga que todavía no hace?

---

## 6. Qué enviar a cada profe

Cuando la instancia esté lista, mandales:

1. **Link del dashboard:** `https://<servicio-profe-x>.railway.app/dashboard`
2. **Contraseña:** la que definiste en `DASHBOARD_PASSWORD`
3. **Si tiene WhatsApp:** el número del bot y que le escriban "hola" para probar
4. **Instrucciones:** el archivo **INSTRUCCIONES_PARA_PILOTOS.md** de este repo (podés copiarlo en el mensaje, pasarlo como PDF, o enviarles el link si está en un lugar que puedan ver). Ahí está qué pueden probar y cómo darte feedback.

Así no tienen que configurar nada técnico y saben qué hacer desde el primer día.

---

## 7. Resumen de variables clave por instancia

- `DB_PATH` — Ruta al archivo SQLite para esa profe (dentro del volumen Railway).
- `DASHBOARD_PASSWORD` — Contraseña de acceso al dashboard de esa profe.
- `SECRET_KEY` — Clave de Flask para esa instancia (puede ser distinta por servicio).
- `DOLAR_BLU_ARS` — ARS por 1 USD (para gráficos en USD).
- `TASA_GBP_USD` — USD por 1 GBP (para gráficos en USD).

Compartidas entre todas las instancias (piloto):

- `ANTHROPIC_API_KEY`
- `GOOGLE_TOKEN_JSON`
- `TWILIO_*`
- Cualquier otra clave global que ya uses.

---

## Resumen

- **Para vos:** usar la checklist de la sección inicial y los pasos 2–5 de este doc.
- **Para ellos:** enviarles dashboard + contraseña + (opcional) WhatsApp + **INSTRUCCIONES_PARA_PILOTOS.md**.

