# AsistenteAjedrez — Contexto del Proyecto

## Descripción
Bot de WhatsApp para gestionar clases de ajedrez. Permite registrar pagos, clases, cancelaciones, y sincronizar automáticamente con Google Calendar.

## Stack técnico
- Python + Flask + Twilio (WhatsApp)
- SQLite (base de datos local)
- Claude API Haiku (interprete de mensajes)
- Google Calendar API (fuente de verdad para clases)
- APScheduler (notificaciones automáticas)

## Arquitectura principal
**Google Calendar es la fuente de verdad para clases.** El bot no crea ni mueve eventos en Calendar. Las clases se sincronizan desde Calendar a la DB. Las cancelaciones se manejan desde el bot (regla 24hs).

## Base de datos

### Tablas
- **alumnos** — info fija de cada alumno (nombre, país, moneda, método de pago, modalidad, representante, alias, activo)
- **pagos** — cada pago registrado (alumno_id, fecha, monto, moneda, metodo, notas)
- **clases** — cada clase agendada/dada/cancelada (alumno_id, fecha, hora, estado, origen, google_event_id)
- **promociones** — rangos de precio por alumno (clases_desde, clases_hasta, precio_por_clase, moneda)
- **eventos_ignorados** — google_event_ids a ignorar en la sync (pendiente de implementar)

### Estados de clases
- `agendada` — clase programada
- `dada` — clase realizada
- `cancelada_con_anticipacion` — canceló a tiempo, queda como crédito
- `cancelada_sin_anticipacion` — canceló tarde, se cobra igual
- `cancelada_por_profesora` — no se cobra ni acredita

## Archivos principales

### bot.py
Webhook de Flask + lógica de acciones. Maneja historial de conversación por número de WhatsApp. Sistema de `acciones_pendientes` para resolver ambigüedad de nombres. Reset de historial después de resolver ambigüedad.

### interprete.py
Recibe mensajes en lenguaje natural y devuelve JSON con acción y datos usando Claude Haiku. Incluye historial de conversación para contexto.

### calendar_google.py
- `autenticar()` — conecta con Google Calendar
- `obtener_eventos(fecha_inicio, fecha_fin)` — trae eventos del calendario
- `buscar_alumno_en_evento(titulo)` — identifica alumno por título del evento con 3 pasadas: nombre completo → representante/alias → palabra suelta
- `sincronizar_mes(mes, anio)` — sincroniza un mes completo desde Calendar a DB

### sincronizacion.py
- `detectar_cambios(mes, anio)` — compara Calendar vs DB y devuelve nuevos/cancelados/modificados
- `procesar_cambios(cambios)` — procesa cambios y notifica
- `sincronizacion_diaria()` — sync automática del mes actual

### notificaciones.py
- `resumen_diario()` — clases del día a las 8am
- `recordatorio_pagos_mensuales()` — quién debe el día 1 a las 9am
- `resumen_cobros_mensuales()` — resumen de cobros del mes actual el día 1 a las 9am
- `alerta_paquetes()` — alumnos con 2 o menos clases restantes los lunes

### alumnos.py
CRUD de alumnos. Incluye `buscar_alumno_con_sugerencia()` con difflib para nombres aproximados y `buscar_alumno_por_representante()`.

### promociones.py
Lógica de precios escalonados. `resumen_cobro_alumno()` y `resumen_cobro_representante()` calculan el monto a cobrar dado un alumno/representante y un mes.

### pagos.py
Registro y consulta de pagos. `quien_debe_este_mes()` compara alumnos mensuales vs pagos del mes.

### clases.py
Agendar, cancelar (con regla 24hs), reprogramar clases. `alumnos_por_renovar_paquete()` detecta paquetes por vencer.

## Acciones del bot
1. `registrar_pago` — registrar un pago
2. `registrar_clase` — registrar clase con un alumno
3. `registrar_clases_multiple` — registrar clases con varios alumnos
4. `cancelar_clase` — cancelar próxima clase de un alumno
5. `quien_debe` — alumnos mensuales que no pagaron este mes
6. `cuanto_gane` — total cobrado en un mes
7. `resumen_alumno` — resumen de clases y pagos de un alumno
8. `alumno_nuevo` — agregar alumno con promo en un solo paso
9. `clases_del_mes` — clases agendadas de un alumno en un mes
10. `que_tengo_hoy` — clases agendadas para hoy
11. `cuanto_debe_alumno` — cuánto cobrarle a un alumno/representante
12. `aclaracion_alumno` — resolver ambigüedad cuando hay varios alumnos con el mismo nombre

## Alumnos actuales
| Nombre | Representante | Moneda | Método | Modalidad |
|--------|--------------|--------|--------|-----------|
| Grace | Charlie | Dólar | Wise | Online |
| Fiona | Charlie | Dólar | Wise | Online |
| Henry Chen | Stephen | Dólar | Wise | Online |
| Henry Cutler | Jeremy | Dólar | Wise | Online |
| Ximena | Lidia | Dólar | Wise | Online |
| Rafa | Lidia | Dólar | Wise | Online |
| Giuliana | Alison | Dólar | Wise | Online |
| John | — | Dólar | Wise | Online |
| Jeff | — | Dólar | Wise | Online |
| Michael | — | Dólar | PayPal | Online |
| Isabella | Roksana | Libra Esterlina | Wise | Online |
| Nouham (alias: noam) | — | Libra Esterlina | Wise | Online |
| Ruby | — | Libra Esterlina | Wise | Online |
| Kerem | Ozlam | Libra Esterlina | Wise | Online |
| Ilay | Karina | Pesos | Transferencia | Presencial domicilio (3h) |
| David y George | Morgan (Celia) | Pesos | Transferencia | Presencial domicilio (3h) |
| Lucas | — | Pesos | Transferencia | Presencial domicilio |
| Leila | Tameem | Dólar | Wise | Online |

## Horario semanal
- Lunes: Ilay 17:00, Henry Cutler 21:00
- Martes: Nouham 11:30, Michael 16:30, Ximena 19:00, Giuliana 20:30, Jeff 21:30
- Miércoles: Ruby 12:30, Kerem 14:00, Lucas 15:00, David y George 17:30
- Jueves: Isabella 15:00, Grace 17:30, Fiona 18:30, Rafa 20:30
- Viernes: Henry Chen 17:15, Leila 18:15
- Sábado: John 15:00

## Estado actual (27 febrero 2026)
- ✅ Bot funcionando en local con Twilio sandbox
- ✅ Sync con Google Calendar operativa para mes actual
- ✅ Resumen de cobros mensuales automático el día 1
- ✅ Agregar alumno nuevo con promo en un solo paso
- ✅ Identificación robusta de alumnos en Calendar (3 pasadas + alias)
- ✅ Manejo de ambigüedad de nombres con historial
- ⏳ Pendiente: salir del sandbox de Twilio
- ⏳ Pendiente: subir a la nube (Render o Railway)

## Tareas pendientes (post-producción)
- Créditos del mes anterior en resumen de cobros
- Duración de clase en horas (campo `duracion_horas` en tabla clases)
- Ignorar eventos de Calendar permanentemente (tabla eventos_ignorados)
- Comando "cargá el mes siguiente" desde el bot
- Push notifications de Google Calendar (cuando esté en la nube)
- Resumen de cobros con detalle clases dadas vs canceladas

## Decisiones de diseño importantes
- Google Calendar es la fuente de verdad, el bot no crea eventos
- Clases presenciales (Ilay, Morgan): precio ya incluye hora de traslado (60000 pesos = 3h × 20000)
- Eventos recurrentes infinitos en Calendar → sync solo mira mes actual para evitar cargar demasiado
- Alias de alumnos guardados en DB (columna `alias` en tabla alumnos)
- Reset de historial de conversación después de resolver ambigüedad de nombres

## Scripts de utilidad
- `cargar_clases.py` — carga clases recurrentes de un mes manualmente
- `cargar_promociones.py` — carga promos de todos los alumnos
- `test_bot.py` — prueba el bot en terminal sin WhatsApp
- `test_sincronizacion.py` — prueba la detección de cambios de Calendar
- `database.py` — crear tablas (correr una vez al inicio)