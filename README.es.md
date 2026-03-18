## ♟️ AsistenteAjedrez
> Bot de WhatsApp + dashboard web para gestionar clases de ajedrez individuales

🇬🇧 [English version](README.en.md)

![Demo](docs/demo.png)

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![SQLite](https://img.shields.io/badge/SQLite-DB-lightgrey)
![Twilio](https://img.shields.io/badge/WhatsApp-Twilio-25D366)
![Claude](https://img.shields.io/badge/NLP-Claude%20Haiku-orange)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E)

### Demo
- Placeholder captura: `docs/demo.png`
- Sugeridas (agregalas cuando puedas): `docs/portal.png`, `docs/trainer.png`, `docs/dashboard.png`

### Cómo probar (rápido)
- Portal alumnos: `/login` → “Soy alumna / responsable” → Lichess/Google → `/portal/home`
- Entrenamiento: en el portal → “Entrar al entrenamiento” → `/trainer` → resolver ejercicios → “← Portal”
- Progreso: `/portal/entrenamiento`
- Dashboard docente: `/login` → “Soy profesora” → password → `/dashboard`

Checklist completa: ver [docs/TEST_PLAN.md](docs/TEST_PLAN.md)

### ¿Qué es?
AsistenteAjedrez automatiza la gestión del negocio de clases de ajedrez online: alumnos, pagos, calendario y recordatorios. La profesora escribe por WhatsApp en lenguaje natural («Lucas pagó 28 dólares», «di clase con Henry hoy») y el sistema registra todo; un dashboard web completa la vista con listados, gráficos y sincronización con Google Calendar.

### El problema que resuelve
Soy Andrea, profesora de ajedrez online. Tengo alumnos en distintos países, monedas y horarios, y antes llevaba todo en planillas: quién pagó, cuántas clases debe, qué precio tiene cada familia y cuándo vino cada alumno. Ese sistema manual era frágil, lento y muy fácil de romper. AsistenteAjedrez automatiza esta gestión para que pueda concentrarme en enseñar, no en perseguir deudas ni actualizar Excel.

### Funcionalidades
- ✅ Bot de WhatsApp que entiende mensajes en lenguaje natural (pagos, clases, consultas de deuda)
- ✅ Registro automático de pagos asociados a clases del mes (USD, GBP, ARS; Wise, PayPal, transferencia)
- ✅ Precios promocionales por volumen (tiered pricing) y paquetes de clases
- ✅ Representantes: un padre/madre paga por varios hijos con precio combinado
- ✅ Sincronización con Google Calendar como fuente de verdad (agendada → dada / cancelada)
- ✅ Dashboard web: alumnos, pagos, clases, gráficos de ingresos, temas claro/oscuro/navy
- ✅ Chat embebido en el dashboard para usar el bot desde el navegador
- ✅ Portal de alumnos (Lichess/Google): ver clases del mes, puzzle diario, recordatorios por mail
- ✅ Ausencias (se cobra) vs cancelaciones (no se cobra, queda crédito)
- ✅ Historial de pagos con opción de borrar

### Stack tecnológico
| Capa           | Tecnología              | Uso                          |
|----------------|-------------------------|------------------------------|
| Backend        | Python + Flask          | API, webhook bot, dashboard   |
| Base de datos  | SQLite                  | Una DB por instancia/profe   |
| WhatsApp       | Twilio Messaging API    | Recepción y envío de mensajes|
| NLP            | Claude API (Haiku)      | Interpretar mensajes en texto|
| Calendario     | Google Calendar API     | Fuente de verdad de clases   |
| Deploy         | Railway                 | Auto-deploy desde GitHub     |
| Tareas         | APScheduler             | Sync y recordatorios por mail|

### Arquitectura (flujo)
```
WhatsApp → Twilio → Flask (bot.py)
                        ↓
                 interprete.py → Claude API → {acción, datos}
                        ↓
                 clases.py / pagos.py / alumnos.py / promociones.py
                        ↓
                 SQLite + calendar_google.py (sync con Google Calendar)
                        ↓
                 Dashboard (dashboard_routes.py) + Portal alumnos (portal_routes.py) + Trainer (/trainer)
```

Más detalle: ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

### Variables de entorno
| Variable                  | Requerida | Descripción                                      |
|--------------------------|-----------|--------------------------------------------------|
| DB_PATH                  | ✅        | Ruta al archivo SQLite                           |
| SECRET_KEY               | ✅        | Clave secreta de Flask                           |
| DASHBOARD_PASSWORD       | ✅        | Contraseña del dashboard                         |
| TWILIO_ACCOUNT_SID       | ✅        | SID de cuenta Twilio                             |
| TWILIO_AUTH_TOKEN        | ✅        | Token de autenticación Twilio                    |
| TWILIO_WHATSAPP_NUMBER   | ✅        | Número WhatsApp (ej. whatsapp:+549...)          |
| ANTHROPIC_API_KEY        | ✅        | API key de Anthropic (Claude)                    |
| GOOGLE_CREDENTIALS       | ✅        | JSON OAuth de Google (string)                    |
| GOOGLE_CALENDAR_ID       | ✅        | ID del calendario (ej. primary)                  |
| RESEND_API_KEY           | ❌        | API key para enviar mails de recordatorios       |
| RESEND_FROM              | ❌        | Remitente verificado (ej. notificaciones@...)    |
| DOLAR_BLU_ARS            | ❌        | Tipo de cambio ARS/USD para gráficos            |
| TASA_GBP_USD             | ❌        | Tipo de cambio GBP/USD                           |
| RAILWAY_PUBLIC_DOMAIN    | ❌        | Dominio público en Railway (URLs absolutas)     |

### Deploy en Railway (resumen)
1. Conectar repo GitHub a Railway (auto-deploy al push).
2. Configurar variables de entorno (DB_PATH, SECRET_KEY, DASHBOARD_PASSWORD, credenciales Google, Twilio, Claude).
3. Asegurar volumen para SQLite (DB_PATH apuntando al volumen).
4. Probar `/login`, `/portal/home`, `/trainer` y `/dashboard`.

### Setup local
```bash
git clone https://github.com/tu-usuario/AsistenteAjedrez.git
cd AsistenteAjedrez
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Configurá las variables de entorno (ver tabla anterior)
python -c "from database import crear_tablas; crear_tablas()"
FLASK_APP=bot.py FLASK_ENV=development flask run
```
Dashboard: `http://localhost:5000/dashboard`. Para probar WhatsApp desde tu máquina, exponé la ruta del webhook con ngrok.

### Estado del proyecto
- **En producción** con alumnos reales.
- **Desarrollo activo**: mejoras de UX, portal de alumnos y más idiomas.

### Próximos pasos
- Portal de alumnos más completo (historial, comprobantes descargables).
- Panel para configurar promociones y precios sin tocar código.
- Soporte a más canales (ej. Telegram).
- Reportes mensuales automáticos por mail.

### Autora
**Andrea** — Profesora de ajedrez online (Argentina, USA, UK). AsistenteAjedrez nació de la necesidad de dejar atrás las planillas y tener un sistema que acompañe el crecimiento de la escuela: claridad en cobros, trazabilidad y saber quién está al día en todo momento.

---
*Proyecto en producción — bot + dashboard para gestión de clases de ajedrez.*
