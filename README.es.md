# AsistenteAjedrez — Bot de WhatsApp + dashboard para clases de ajedrez individuales

![Demo](docs/demo.png)

---

## Problema que resuelve

Soy Andrea, profesora de ajedrez online. Tengo alumnos en distintos países, monedas y horarios, y antes llevaba todo en planillas: quién pagó, cuántas clases debe, qué precio tiene cada familia y cuándo vino cada alumno.  
Ese sistema manual era frágil, lento y muy fácil de romper. AsistenteAjedrez automatiza esta gestión para que pueda concentrarme en enseñar, no en perseguir deudas ni actualizar Excel.

---

## Funcionalidades principales

- **Bot de WhatsApp inteligente**  
  Entiende mensajes en lenguaje natural, por ejemplo:
  - "Lucas pagó 28 dólares"
  - "Di clase con Henry hoy"
  - "¿Quién debe este mes?"
  - "Cuánto gané en marzo en GBP"

- **Registro automático de pagos**  
  - Asocia pagos a las clases del mes según el alumno o representante.  
  - Soporta múltiples monedas: USD, GBP, ARS.  
  - Admite métodos como Wise, PayPal y transferencia bancaria.

- **Precios promocionales por volumen (tiered pricing)**  
  - Calcula el precio por clase según la cantidad total de clases en el mes.  
  - Soporta paquetes (ej. 10 clases) y modalidad mensual vs clase suelta.

- **Gestión de representantes**  
  - Un padre/madre puede pagar por varios hijos.  
  - El sistema suma todas las clases de la familia para aplicar el precio combinado correcto.

- **Sincronización con Google Calendar**  
  - Google Calendar es la *fuente de verdad* para las clases.  
  - Importa automáticamente las clases agendadas y actualiza estados (agendada, dada, cancelada).

- **Dashboard web para la profesora**  
  - Lista de alumnos con estado de pagos y deuda.  
  - Registro manual de clases y pagos cuando hace falta.  
  - Gráficos de ingresos por moneda y por período.  
  - Tema claro / oscuro / navy.  
  - Chat embebido para usar el bot directamente desde el navegador.

- **Ausencias vs cancelaciones**  
  - Ausente (no vino a una clase dada): se cobra igual.  
  - Cancelada con anticipación: no se cobra y queda como crédito.

- **Historial de pagos y clases**  
  - Historial navegable con la opción de borrar pagos puntuales.  
  - Relación clara entre clases y pagos asociados.

---

## Arquitectura / Stack

**Backend**

- Python 3 + Flask (API + vistas HTML embebidas)
- Integración con Claude API (modelo `claude-haiku`) para NLP
- Integración con Twilio Messaging API para WhatsApp
- Integración con Google Calendar API

**Datos**

- SQLite (un archivo por instancia de profesora)
- Migraciones y creación de tablas gestionadas por `database.py`

**Infraestructura**

- Hosting en Railway
- Control de versiones con Git y GitHub

**Archivos principales**

- `bot.py` — servidor Flask + lógica principal del bot de WhatsApp
- `interprete.py` — integración con Claude API y mapeo a acciones internas
- `dashboard_routes.py` — rutas y UI del dashboard web (HTML/CSS/JS embebido)
- `portal_routes.py` — portal de alumnos (login con Lichess/Google, recordatorios, puzzle diario)
- `clases.py` — funciones para gestionar clases y estados
- `pagos.py` — registro y consulta de pagos
- `alumnos.py` — CRUD de alumnos y búsqueda inteligente
- `promociones.py` — lógica de precios por volumen y combos
- `calendar_google.py` — wrapper de Google Calendar
- `sincronizacion.py` — sincronización periódica con el calendario
- `notificaciones.py` — tareas programadas (sync y recordatorios)
- `database.py` — conexión SQLite y creación/mantenimiento de tablas

---

## Cómo funciona (flujo simplificado)

1. **Mensaje entrante**  
   Un padre o alumno envía un mensaje por WhatsApp. Twilio lo reenvía al webhook de Flask (`bot.py`).

2. **Interpretación del mensaje**  
   `interprete.py` llama a Claude (modelo Haiku) con el texto y recibe una estructura JSON con `{acción, datos}`.

3. **Ejecución de la acción**  
   `bot.py` decide qué hacer: registrar un pago, registrar una clase, consultar deuda, etc.  
   Llama a las funciones especializadas en `clases.py`, `pagos.py`, `alumnos.py`, `promociones.py`.

4. **Consistencia con Calendar**  
   `sincronizacion.py` y `calendar_google.py` sincronizan con Google Calendar para:
   - Crear/actualizar el estado de clases en la base de datos.
   - Marcar clases dadas o canceladas según los eventos del calendario.

5. **Dashboard y portal**  
   - El dashboard (`dashboard_routes.py`) consume la misma base de datos para mostrar alumnos, clases, pagos y gráficos.  
   - El portal de alumnos (`portal_routes.py`) permite a familias consultar su situación, ver clases del mes, puzzle diario y configurar recordatorios por mail.

6. **Notificaciones y tareas automáticas**  
   `notificaciones.py` y tareas programadas (APScheduler) ejecutan sincronizaciones y envían recordatorios sin intervención manual.

---

## Instalación y configuración local

Requisitos previos:

- Python 3.10+
- SQLite3
- Cuenta de Twilio con un número de WhatsApp de prueba o productivo
- Proyecto en Google Cloud con Calendar API habilitada
- Cuenta en Anthropic para usar Claude API
- Cuenta en Railway (opcional para deploy remoto)

**1. Clonar el repositorio**

```bash
git clone https://github.com/tu-usuario/AsistenteAjedrez.git
cd AsistenteAjedrez
```

**2. Crear y activar un entorno virtual**

```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
```

**3. Instalar dependencias**

```bash
pip install -r requirements.txt
```

**4. Configurar variables de entorno**

Crear un archivo `.env` (o exportarlas en tu shell) con al menos:

```bash
export DB_PATH=asistente_ajedrez.db
export SECRET_KEY=un_secret_flask_seguro
export DASHBOARD_PASSWORD=tu_password_dashboard

export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_WHATSAPP_NUMBER=whatsapp:+123456789

export ANTHROPIC_API_KEY=...

export GOOGLE_CREDENTIALS='{"installed": {...}}'  # JSON OAuth de Google
export GOOGLE_CALENDAR_ID=primary  # o el ID específico de calendario
```

**5. Inicializar la base de datos**

```bash
python -c "from database import crear_tablas; crear_tablas()"
```

**6. Ejecutar el servidor local**

```bash
FLASK_APP=bot.py FLASK_ENV=development flask run
```

- El dashboard quedará disponible en `http://localhost:5000/dashboard`.
- El webhook de Twilio debe apuntar a `/bot` (o la ruta configurada en `bot.py`), usando ngrok o similar si querés probar WhatsApp desde tu máquina.

---

## Variables de entorno necesarias

| Nombre                    | Descripción                                                                 | Requerida |
|---------------------------|-----------------------------------------------------------------------------|-----------|
| `DB_PATH`                 | Ruta al archivo SQLite de la instancia                                     | Sí        |
| `SECRET_KEY`              | Clave secreta de Flask para sesiones                                       | Sí        |
| `DASHBOARD_PASSWORD`      | Contraseña para acceder al dashboard web                                   | Sí        |
| `TWILIO_ACCOUNT_SID`      | SID de cuenta Twilio                                                       | Sí        |
| `TWILIO_AUTH_TOKEN`       | Token de autenticación Twilio                                              | Sí        |
| `TWILIO_WHATSAPP_NUMBER`  | Número de WhatsApp Twilio (formato `whatsapp:+...`)                        | Sí        |
| `ANTHROPIC_API_KEY`       | API key de Anthropic para Claude                                          | Sí        |
| `GOOGLE_CREDENTIALS`      | JSON OAuth de Google (como string)                                         | Sí        |
| `GOOGLE_CALENDAR_ID`      | ID del calendario que se usa como fuente de verdad                         | Sí        |
| `DOLAR_BLU_ARS`           | Tipo de cambio de referencia ARS/USD                                      | No        |
| `TASA_GBP_USD`            | Tipo de cambio GBP/USD para gráficos                                       | No        |
| `RAILWAY_PUBLIC_DOMAIN`   | Dominio en Railway (para URLs absolutas en producción)                    | No        |

---

## Estado del proyecto

- **En producción** con alumnos reales.
- **En desarrollo activo** para mejoras de UX, portal de alumnos y soporte a más idiomas.

---

## Próximas funcionalidades

- Portal de alumnos más rico: histórico completo, descarga de comprobantes.
- Panel para que la profesora configure promociones y precios sin tocar código.
- Soporte de más canales de mensaje (ej. Telegram) reutilizando la misma lógica.
- Reportes automáticos mensuales por mail para la profesora.

---

## Sobre la autora

Andrea es profesora de ajedrez con alumnos en Argentina, Estados Unidos y Reino Unido. Este proyecto nació de una necesidad real: dejar atrás las planillas manuales y tener un sistema que acompañe el crecimiento de su escuela de ajedrez. El código se construyó con foco en la claridad, la trazabilidad de los cobros y la tranquilidad de saber quién debe y quién está al día, en todo momento.
