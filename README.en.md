# AsistenteAjedrez — WhatsApp bot + web dashboard for 1:1 chess lessons

![Demo](docs/demo.png)

---

## The problem it solves

I'm Andrea, an online chess coach. I teach students in different countries, currencies and time zones. For years I tracked everything in spreadsheets: who paid, how many lessons they owe, which family has which price, and when each student attended.  
That manual setup was fragile, slow and easy to break. AsistenteAjedrez automates this back office so I can focus on teaching instead of chasing payments or fixing Excel formulas.

---

## Key features

- **WhatsApp bot that understands natural language**  
  Examples of messages it can handle:
  - "Lucas paid 28 dollars"
  - "I taught Henry today"
  - "Who still owes this month?"
  - "How much did I make in March in GBP?"

- **Automatic payment recording**  
  - Links payments to the right student (or parent) and their lessons for the month.  
  - Supports multiple currencies: USD, GBP, ARS.  
  - Works with Wise, PayPal and bank transfers.

- **Tiered pricing and lesson packs**  
  - Calculates per-lesson price based on total lessons in the period.  
  - Supports monthly plans, single lessons and 10-lesson packs.

- **Family / guardian management**  
  - One parent can pay for several kids.  
  - The system aggregates all their lessons to apply the correct combined rate.

- **Google Calendar sync**  
  - Google Calendar is the *source of truth* for lesson scheduling.  
  - Lessons are imported automatically and kept in sync (scheduled, delivered, cancelled).

- **Web dashboard for the teacher**  
  - Student list with payment and debt status.  
  - Manual registration of lessons and payments when needed.  
  - Revenue charts by currency and time period.  
  - Light / dark / navy themes.  
  - Embedded chat to talk to the bot directly from the browser.

- **Absences vs cancellations**  
  - No-show for an already scheduled lesson: still billed.  
  - Cancellations with enough notice: not billed and turned into credit.

- **Payment and lesson history**  
  - Browsable history with the ability to delete specific payments.  
  - Clear link between payments and the lessons they cover.

---

## Architecture / Tech stack

**Backend**

- Python 3 + Flask (API + server-rendered HTML with embedded JS)
- Claude API (`claude-haiku`) for natural language understanding
- Twilio Messaging API for WhatsApp
- Google Calendar API for scheduling

**Data**

- SQLite database (one file per teacher / instance)
- Table creation and migrations handled by `database.py`

**Infrastructure**

- Deployed on Railway
- Version control with Git and GitHub

**Main modules**

- `bot.py` — Flask server + core WhatsApp bot logic
- `interprete.py` — Claude API integration and intent-to-action mapping
- `dashboard_routes.py` — web dashboard routes and UI
- `portal_routes.py` — student portal (Lichess/Google login, reminders, daily puzzle)
- `clases.py` — lesson management and status updates
- `pagos.py` — payment recording and queries
- `alumnos.py` — student CRUD and search
- `promociones.py` — tiered pricing and combined discounts
- `calendar_google.py` — Google Calendar wrapper
- `sincronizacion.py` — scheduled calendar synchronization
- `notificaciones.py` — background tasks and reminders
- `database.py` — SQLite connection and schema management

---

## How it works (high-level flow)

1. **Incoming message**  
   A parent or student sends a WhatsApp message. Twilio forwards it to the Flask webhook defined in `bot.py`.

2. **Natural language understanding**  
   `interprete.py` calls Claude (Haiku) with the message and receives structured JSON describing the intent: `{action, data}`.

3. **Business logic execution**  
   `bot.py` routes the action to the right handler: register payment, register lesson, compute debt, etc.  
   It uses helper modules like `clases.py`, `pagos.py`, `alumnos.py`, and `promociones.py`.

4. **Calendar consistency**  
   `sincronizacion.py` and `calendar_google.py` talk to Google Calendar to:
   - Import or update lessons into the local database.  
   - Mark lessons as delivered or cancelled based on calendar events.

5. **Teacher dashboard & student portal**  
   - The dashboard (`dashboard_routes.py`) reads from the same database to show students, lessons, payments and charts.  
   - The student portal (`portal_routes.py`) lets families check their status, see current month lessons, a daily Lichess puzzle, and configure email reminders.

6. **Background jobs and notifications**  
   `notificaciones.py` and APScheduler run scheduled tasks (sync windows, reminders) without manual intervention.

---

## Local setup

Prerequisites:

- Python 3.10+
- SQLite3
- Twilio account with a WhatsApp-enabled number
- Google Cloud project with Calendar API enabled
- Anthropic account for Claude API
- Railway account (optional but recommended for production)

**1. Clone the repository**

```bash
git clone https://github.com/your-user/AsistenteAjedrez.git
cd AsistenteAjedrez
```

**2. Create and activate a virtualenv**

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Create a `.env` file or export variables in your shell:

```bash
export DB_PATH=asistente_ajedrez.db
export SECRET_KEY=some_secure_flask_secret
export DASHBOARD_PASSWORD=your_dashboard_password

export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_WHATSAPP_NUMBER=whatsapp:+123456789

export ANTHROPIC_API_KEY=...

export GOOGLE_CREDENTIALS='{"installed": {...}}'
export GOOGLE_CALENDAR_ID=primary
```

**5. Initialize the database**

```bash
python -c "from database import crear_tablas; crear_tablas()"
```

**6. Run the development server**

```bash
FLASK_APP=bot.py FLASK_ENV=development flask run
```

- Dashboard: `http://localhost:5000/dashboard`
- Twilio webhook: configure it to point to the bot endpoint (e.g. `/bot`) using ngrok or a similar tunnel to test from your phone.

---

## Required environment variables

| Name                     | Description                                                          | Required |
|--------------------------|----------------------------------------------------------------------|----------|
| `DB_PATH`                | Path to the SQLite database file                                     | Yes      |
| `SECRET_KEY`             | Flask secret key for sessions                                        | Yes      |
| `DASHBOARD_PASSWORD`     | Password to access the dashboard                                     | Yes      |
| `TWILIO_ACCOUNT_SID`     | Twilio account SID                                                   | Yes      |
| `TWILIO_AUTH_TOKEN`      | Twilio auth token                                                    | Yes      |
| `TWILIO_WHATSAPP_NUMBER` | WhatsApp-enabled Twilio number (`whatsapp:+...`)                     | Yes      |
| `ANTHROPIC_API_KEY`      | Anthropic API key for Claude                                         | Yes      |
| `GOOGLE_CREDENTIALS`     | Google OAuth JSON (as a string)                                      | Yes      |
| `GOOGLE_CALENDAR_ID`     | ID of the calendar used as the scheduling source of truth           | Yes      |
| `DOLAR_BLU_ARS`          | Reference FX rate ARS/USD (for reporting)                            | No       |
| `TASA_GBP_USD`           | FX rate GBP/USD (for reporting)                                      | No       |
| `RAILWAY_PUBLIC_DOMAIN`  | Railway public domain (for absolute URLs in production, if needed)  | No       |

---

## Project status

- **In production** and used with real students and payments.
- **Actively developed**: UX improvements, richer student portal and multi-language support are ongoing.

---

## Roadmap / Next steps

- Richer student portal: full history, downloadable receipts, better mobile UX.
- Web UI to manage promotions and price tiers without code changes.
- Additional messaging channels (e.g. Telegram) using the same core logic.
- Automated monthly email reports for the teacher with key metrics.

---

## About the author

Andrea is an online chess coach working with students in Argentina, the US and the UK. AsistenteAjedrez was born from her real-world need to scale beyond spreadsheets and keep finances and scheduling under control. The project is built with a focus on clarity, reliability and peace of mind: knowing exactly who owes what, and which lessons have been delivered, at a glance.
