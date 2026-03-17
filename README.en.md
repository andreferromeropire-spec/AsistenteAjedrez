## ♟️ AsistenteAjedrez
> WhatsApp bot + web dashboard for managing 1:1 chess lessons

🇪🇸 [Versión en español](README.es.md)

![Demo](docs/demo.png)

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![SQLite](https://img.shields.io/badge/SQLite-DB-lightgrey)
![Twilio](https://img.shields.io/badge/WhatsApp-Twilio-25D366)
![Claude](https://img.shields.io/badge/NLP-Claude%20Haiku-orange)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E)

### What is it?
AsistenteAjedrez automates the back office for an online chess teaching business: students, payments, scheduling and reminders. The teacher sends natural-language messages over WhatsApp («Lucas paid 28 dollars», «I taught Henry today») and the system records everything; a web dashboard provides lists, charts and sync with Google Calendar.

### The problem it solves
I'm Andrea, an online chess coach. I teach students in different countries, currencies and time zones. For years I tracked everything in spreadsheets: who paid, how many lessons they owe, which family has which price, and when each student attended. That manual setup was fragile, slow and easy to break. AsistenteAjedrez automates this back office so I can focus on teaching instead of chasing payments or fixing Excel formulas.

### Features
- ✅ WhatsApp bot that understands natural language (payments, lessons, debt queries)
- ✅ Automatic payment recording linked to monthly lessons (USD, GBP, ARS; Wise, PayPal, bank transfer)
- ✅ Tiered pricing and lesson packs
- ✅ Guardians: one parent pays for several kids with a combined rate
- ✅ Google Calendar sync as source of truth (scheduled → delivered / cancelled)
- ✅ Web dashboard: students, payments, lessons, revenue charts, light/dark/navy themes
- ✅ Embedded chat in the dashboard to use the bot from the browser
- ✅ Student portal (Lichess/Google): view month lessons, daily puzzle, email reminders
- ✅ Absences (billed) vs cancellations (not billed, credit applied)
- ✅ Payment history with delete option

### Tech stack
| Layer        | Technology           | Purpose                          |
|-------------|----------------------|----------------------------------|
| Backend     | Python + Flask       | API, bot webhook, dashboard       |
| Database    | SQLite               | One DB per instance/teacher      |
| WhatsApp    | Twilio Messaging API | Inbound/outbound messages       |
| NLP         | Claude API (Haiku)   | Parse natural language           |
| Calendar    | Google Calendar API  | Source of truth for lessons      |
| Deploy      | Railway              | Auto-deploy from GitHub          |
| Background  | APScheduler          | Sync and email reminders         |

### Architecture (flow)
```
WhatsApp → Twilio → Flask (bot.py)
                        ↓
                 interprete.py → Claude API → {action, data}
                        ↓
                 clases.py / pagos.py / alumnos.py / promociones.py
                        ↓
                 SQLite + calendar_google.py (sync with Google Calendar)
                        ↓
                 Dashboard (dashboard_routes.py) + Student portal (portal_routes.py)
```

### Environment variables
| Variable                  | Required | Description                                   |
|---------------------------|----------|-----------------------------------------------|
| DB_PATH                   | ✅       | Path to SQLite file                           |
| SECRET_KEY                | ✅       | Flask secret key                             |
| DASHBOARD_PASSWORD        | ✅       | Dashboard login password                      |
| TWILIO_ACCOUNT_SID        | ✅       | Twilio account SID                            |
| TWILIO_AUTH_TOKEN         | ✅       | Twilio auth token                             |
| TWILIO_WHATSAPP_NUMBER    | ✅       | WhatsApp number (e.g. whatsapp:+1234567890)  |
| ANTHROPIC_API_KEY         | ✅       | Anthropic API key (Claude)                    |
| GOOGLE_CREDENTIALS        | ✅       | Google OAuth JSON (string)                    |
| GOOGLE_CALENDAR_ID        | ✅       | Calendar ID (e.g. primary)                   |
| DOLAR_BLU_ARS             | ❌       | ARS/USD rate for charts                       |
| TASA_GBP_USD              | ❌       | GBP/USD rate                                  |
| RAILWAY_PUBLIC_DOMAIN     | ❌       | Railway public domain (absolute URLs)         |

### Local setup
```bash
git clone https://github.com/your-user/AsistenteAjedrez.git
cd AsistenteAjedrez
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Set environment variables (see table above)
python -c "from database import crear_tablas; crear_tablas()"
FLASK_APP=bot.py FLASK_ENV=development flask run
```
Dashboard: `http://localhost:5000/dashboard`. Use ngrok to expose the webhook when testing WhatsApp from your phone.

### Project status
- **In production** with real students and payments.
- **Active development**: UX improvements, student portal and multi-language support.

### Next steps
- Richer student portal (full history, downloadable receipts).
- Web UI to manage promotions and price tiers without code changes.
- Additional channels (e.g. Telegram).
- Automated monthly email reports for the teacher.

### Author
**Andrea** — Online chess coach (Argentina, USA, UK). AsistenteAjedrez was born from the need to move beyond spreadsheets and have a system that scales with the school: clear payment tracking, traceability and knowing who’s up to date at all times.

---
*Production project — bot + dashboard for chess lesson management.*
