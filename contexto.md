# AsistenteAjedrez - Contexto del Proyecto

## Qué es
Bot de WhatsApp para gestionar el negocio de clases de ajedrez (y español) de Andrea.
Interpreta mensajes en lenguaje natural usando Claude API y ejecuta acciones sobre una base de datos SQLite.

## Stack
- Python + Flask
- SQLite (chess_assistant.db)
- Twilio (WhatsApp sandbox)
- Claude API Haiku (interprete.py)
- APScheduler (mensajes automáticos)
- ngrok (exponer servidor local)
- Google Calendar API (conectada y funcionando)

## Archivos y su función
- `database.py` — conexión y creación de tablas
- `alumnos.py` — CRUD de alumnos, búsqueda con sugerencia fuzzy y por representante
- `pagos.py` — registro y consulta de pagos
- `clases.py` — registro de clases, cancelaciones, contadores
- `promociones.py` — precios escalonados por alumno
- `interprete.py` — interpreta mensajes con Claude API, incluye historial de conversación
- `notificaciones.py` — mensajes proactivos automáticos via scheduler
- `bot.py` — webhook Flask principal, maneja ambigüedad de nombres con acciones_pendientes
- `calendar_google.py` — integración Google Calendar, sincronización y detección de alumnos por título
- `sincronizacion.py` — sincronización inteligente: detecta cambios entre Calendar y DB
- `cargar_clases.py` — script para cargar clases manualmente por mes (reemplazado por sync)

## Variables de entorno (.env)
- ANTHROPIC_API_KEY
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- MI_NUMERO=whatsapp:+549...

## Decisiones de arquitectura importantes
- **Google Calendar es la fuente de verdad** para clases. El bot no crea ni mueve eventos en Calendar.
- **Cancelaciones** siempre desde el bot (tienen lógica de negocio: regla 24hs).
- **Reprogramaciones** siempre desde Calendar. La sync las detecta automáticamente.
- **Historial de conversación** se resetea después de resolver una ambigüedad de nombres para evitar que Haiku se confunda.
- **cargar_clases.py** ya no se usa. La carga inicial del mes se hace con `sincronizar_mes()` desde Calendar.

## Estado actual
### Funciona hoy:
- Registrar pagos por WhatsApp en lenguaje natural
- Registrar clases (una o múltiples)
- Ver quién debe este mes
- Calcular cuánto cobrarle a cada alumno con su promo
- Resumen de alumno por mes
- Ver clases del día
- Cancelar clases con regla de 24hs
- Agregar alumno nuevo
- Mensajes automáticos: resumen diario 8am, recordatorio pagos día 1, alerta paquetes lunes
- Google Calendar conectado y sincronizando
- Búsqueda fuzzy de alumnos (tolera errores de tipeo)
- Manejo de ambigüedad de nombres (dos Henry → pregunta cuál)
- `sincronizacion.py` detecta cambios: nuevos, cancelados, modificados
- Scheduler configurado para sync 8:30am y 8pm (pendiente de probar end-to-end)

### Bugs resueltos hoy:
- Bug 2 — "No tenía acción pendiente" → historial se resetea después de resolver ambigüedad
- Bug 1 — Primer mensaje no se entiende → resuelto como efecto secundario del Bug 2

### Pendiente (próxima sesión):
1. Fix: Ruby se identifica como Michael en `buscar_alumno_en_evento` (split por " y " no funciona bien)
2. Fix: Kerem, David y George de abril se detectan como nuevos en cada sync (IDs ya están en DB)
3. Conversación para eventos desconocidos: responder "ignorar" guarda el google_event_id, responder "alumno nuevo" pide datos faltantes
4. Agregar alumno nuevo con promo incluida en un solo paso desde el bot
5. Probar sync end-to-end con scheduler corriendo

## Reglas de negocio importantes
- Cancelaciones: 24hs de anticipación, si no se cobra igual
- Promos: aplican solo si pagan el mes adelantado, sino precio más alto
- Representantes: Lidia paga por Ximena+Rafa, Charlie paga por Grace+Fiona, Morgan paga por David+George (David y George)
- Domicilio: +1 hora de traslado (Ilay, David y George, Lucas)
- Paquetes de 10: Henry Cluter y John
- Alison es la mamá/representante de Giuliana

## Alumnos y nombres en DB (actualizado)
- Henry Chen (id 2) — representante: Stephen, viernes 17:15
- Henry Cluter (id 16) — representante: Jeremy, lunes 21:00 (antes llamado "Henry (Girl)")
- Giuliana (id 6) — representante: Alison
- David y George (id 8) — representante: Morgan

## Títulos en Google Calendar (ejemplos)
- "Chess Lesson - Ruby Morrow y Andrea Romero" → Ruby (split por " y ", toma lo de antes)
- "Chess ingles ilay" → Ilay
- "Chess Henry" → Henry Cluter (lunes) o Henry Chen (viernes)
- "Chess Lesson - Noam y Andrea Romero" → Nouham
- "Chess Michael" → Michael
- "Andrea y Lucia de Elizalde" → ignorar (psicóloga de Andrea)
- "Morgan (George y David)" → David y George

## Horarios fijos semanales (marzo 2026 cargado desde Calendar)
- Lunes: Henry Cluter 21:00
- Martes: Nouham 11:30, Michael 16:30, Ximena 19:00, Giuliana 20:30, Jeff 21:30
- Miércoles: Ruby 12:30, Kerem 14:00, Lucas 15:00, David y George 17:30
- Jueves: Isabella 15:30, Grace 17:30, Fiona 18:30, Rafa 20:30
- Viernes: Henry Chen 17:15, Leila 18:15
- Sábado: John 15:00
- Lunes especial: Ilay 17:00 (domicilio)

## Próximas tareas (mediano plazo)
- Twilio producción (salir del sandbox)
- Servidor en la nube (Render o Railway)
- Push notifications de Google Calendar (cuando esté en la nube)
- Bot manda mail de bienvenida a alumnos nuevos automáticamente
- Resumen de cobros a fin de mes con detalle de clases dadas vs canceladas 