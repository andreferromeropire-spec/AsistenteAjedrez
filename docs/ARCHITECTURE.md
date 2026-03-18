# Arquitectura — AsistenteAjedrez

## Vista general
AsistenteAjedrez es un **bot de WhatsApp + dashboard + portal de alumnos** para gestionar clases individuales de ajedrez.

- **Profesora (dashboard):** gestiona alumnos, clases, pagos, deuda y progreso del trainer.
- **Alumno/representante (portal):** consulta estado, ve clases del mes, entrena patrones y configura recordatorios por mail.
- **Fuente de verdad de agenda:** Google Calendar (sin crear eventos desde el bot).

---

## Flujo 1 — WhatsApp (Twilio) → Bot → DB
```
Alumno/Padre → WhatsApp → Twilio Webhook → Flask (bot.py)
                                    ↓
                           interprete.py (Claude Haiku)
                                    ↓
                       acciones (clases/pagos/alumnos/promos)
                                    ↓
                              SQLite (DB_PATH)
```

---

## Flujo 2 — Portal alumnos
```
/login (selección rol)
   ├─ Alumno: OAuth Lichess/Google → /portal/home
   │      ├─ /trainer (entrenamiento) → /trainer/api/...
   │      └─ /portal/entrenamiento (progreso)
   └─ Profe: password → /dashboard
```

---

## Flujo 3 — Trainer (patrones)
```
/trainer (UI) → /trainer/api/session/start → selecciona puzzles CSV
             → /trainer/api/puzzle/<i>      → FEN + vulnerable pieces
             → /trainer/api/result          → correct/missed/feedback
             → /trainer/api/session/summary → stats de sesión
```

Persistencia:
- Trainer DB local (sessions/results) en `trainer/database.py` (SQLite).
- Progreso agregado por alumno en `progreso_entrenamiento` (DB global).

---

## Flujo 4 — Recordatorios por mail (scheduler)
```
APScheduler (bot.py, cada 15 min)
   → notificaciones_portal.enviar_recordatorios_pendientes()
   → query clases próximas 24h + recordatorios activos
   → envío mail (Resend) + dedupe en recordatorios_enviados
```

---

## Endpoints principales (resumen)

### Acceso
- `GET /login` — login unificado (alumno/responsable vs profe)
- `POST /login` — login profe (password dashboard)

### Portal alumnos
- `GET /portal/home` — resumen de clases + accesos a trainer/progreso
- `GET /portal/entrenamiento` — progreso agregado del trainer por alumno
- `GET /portal/api/recordatorios` — listar recordatorios
- `POST /portal/api/recordatorios` — crear recordatorio
- `DELETE /portal/api/recordatorios/<id>` — borrar recordatorio
- `GET /portal/api/puzzle_diario` — proxy JSON del puzzle diario (evita CORS)

### Trainer
- `GET /trainer` — UI del trainer (requiere sesión portal)
- `GET /trainer/api/session/start`
- `GET /trainer/api/puzzle/<index>`
- `POST /trainer/api/result`
- `GET /trainer/api/session/summary/<session_id>`

### Dashboard docente
- `GET /dashboard` — UI principal
- `GET /dashboard/api/entrenamiento_resumen` — overview por alumno (tabla de entrenamiento)

---

## Datos y tablas clave
- `alumnos` — alumnos y representantes
- `clases` — clases agendadas/dadas/canceladas + ausente/pago_id
- `pagos` — pagos registrados
- `portal_accesos` — mapping Lichess → alumno(s)
- `recordatorios` + `recordatorios_enviados` — recordatorios de portal (mail) + dedupe
- `progreso_entrenamiento` — progreso agregado del trainer por alumno

