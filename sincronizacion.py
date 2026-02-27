from datetime import datetime, date
from calendar_google import obtener_eventos, buscar_alumno_en_evento
from database import get_connection
from clases import agendar_clase
from notificaciones import enviar_mensaje

# DETECTAR_CAMBIOS: Compara Google Calendar con la DB y devuelve las diferencias.
# Busca eventos nuevos, cancelados y modificados para el mes indicado.
def detectar_cambios(mes, anio):
    # 1. Definir rango del mes
    if mes == 12:
        proximo_mes, proximo_anio = 1, anio + 1
    else:
        proximo_mes, proximo_anio = mes + 1, anio

    fecha_inicio = date(anio, mes, 1)
    fecha_fin = date(proximo_anio, proximo_mes, 1)

    # 2. Traer eventos de Google Calendar
    eventos_calendar = obtener_eventos(fecha_inicio, fecha_fin)

    # Convertimos a dict por google_event_id para comparar fácil
    # {google_event_id: {titulo, fecha, hora}}
    calendar_por_id = {}
    for evento in eventos_calendar:
        google_id = evento.get('id')
        titulo = evento.get('summary', '')
        inicio = evento.get('start', {})
        fecha_str = inicio.get('dateTime', inicio.get('date', ''))

        if 'T' in fecha_str:
            fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            fecha = fecha_dt.date().isoformat()
            hora = fecha_dt.strftime('%H:%M')
        else:
            fecha = fecha_str
            hora = "00:00"

        calendar_por_id[google_id] = {
            "titulo": titulo,
            "fecha": fecha,
            "hora": hora
        }

    # 3. Traer clases de la DB que tienen google_event_id para ese mes
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, a.nombre as nombre_alumno
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE strftime('%m', c.fecha) = ?
        AND strftime('%Y', c.fecha) = ?
        AND c.google_event_id IS NOT NULL
        AND c.google_event_id NOT LIKE 'traslado_%'
        AND c.estado = 'agendada'
    """, (f"{mes:02d}", str(anio)))

    clases_db = cursor.fetchall()

    # Traer IDs que ya decidiste ignorar
    cursor.execute("SELECT google_event_id FROM eventos_ignorados")
    ids_ignorados = {row['google_event_id'] for row in cursor.fetchall()}
    
    conn.close()

    # Convertimos a dict por google_event_id
    db_por_id = {c['google_event_id']: c for c in clases_db}

    # 4. Comparar y clasificar diferencias
    nuevos = []       # En Calendar pero no en DB
    cancelados = []   # En DB pero no en Calendar
    modificados = []  # En ambos pero con fecha/hora distinta

    # Eventos nuevos o modificados
    for google_id, evento in calendar_por_id.items():
        if google_id in ids_ignorados:
            continue  # Ya decidiste ignorar este evento
        if google_id not in db_por_id:
            nuevos.append({
                "google_id": google_id,
                "titulo": evento["titulo"],
                "fecha": evento["fecha"],
                "hora": evento["hora"]
            })
        else:
            clase_db = db_por_id[google_id]
            if clase_db['fecha'] != evento['fecha'] or clase_db['hora'] != evento['hora']:
                modificados.append({
                    "google_id": google_id,
                    "titulo": evento["titulo"],
                    "clase_id": clase_db['id'],
                    "alumno": clase_db['nombre_alumno'],
                    "fecha_anterior": clase_db['fecha'],
                    "hora_anterior": clase_db['hora'],
                    "nueva_fecha": evento["fecha"],
                    "nueva_hora": evento["hora"]
                })

    # Eventos cancelados (estaban en DB pero desaparecieron de Calendar)
    for google_id, clase in db_por_id.items():
        if google_id not in calendar_por_id:
            cancelados.append({
                "google_id": google_id,
                "clase_id": clase['id'],
                "alumno": clase['nombre_alumno'],
                "fecha": clase['fecha'],
                "hora": clase['hora']
            })

    return {
        "nuevos": nuevos,
        "cancelados": cancelados,
        "modificados": modificados
    }


# PROCESAR_CAMBIOS: Actúa sobre las diferencias detectadas y arma los mensajes.
# Agrega clases nuevas, actualiza modificadas, marca canceladas.
# Devuelve lista de mensajes para enviarle a Andrea.
def procesar_cambios(cambios):
    mensajes = []
    conn = get_connection()
    cursor = conn.cursor()

    # 1. EVENTOS NUEVOS
    for evento in cambios["nuevos"]:
        alumno = buscar_alumno_en_evento(evento["titulo"])

        if alumno:
            # Alumno conocido → agregar clase automáticamente
            agendar_clase(
                alumno_id=alumno['id'],
                fecha=evento["fecha"],
                hora=evento["hora"],
                origen="google_calendar",
                google_event_id=evento["google_id"]
            )
            mensajes.append(
                f"📌 Clase nueva agregada: {alumno['nombre']} el {evento['fecha']} a las {evento['hora']}"
            )
        else:
            # Alumno desconocido → preguntarle a Andrea
            mensajes.append(
                f"❓ Evento nuevo en Calendar: \"{evento['titulo']}\" el {evento['fecha']} a las {evento['hora']}.\n"
                f"No lo reconozco. ¿Es un alumno nuevo o lo ignoro? "
                f"Respondé: 'alumno nuevo: [nombre], promo [rangos], paga en [moneda] por [método]' o 'ignorar: {evento['titulo']}'"
            )

    # 2. EVENTOS CANCELADOS
    for cancelado in cambios["cancelados"]:
        cursor.execute("""
            UPDATE clases SET estado = 'cancelada_por_profesora'
            WHERE id = ?
        """, (cancelado["clase_id"],))
        mensajes.append(
            f"🗑️ Clase cancelada (desapareció de Calendar): {cancelado['alumno']} "
            f"el {cancelado['fecha']} a las {cancelado['hora']}"
        )

    # 3. EVENTOS MODIFICADOS
    for modificado in cambios["modificados"]:
        cursor.execute("""
            UPDATE clases SET fecha = ?, hora = ?
            WHERE id = ?
        """, (modificado["nueva_fecha"], modificado["nueva_hora"], modificado["clase_id"]))
        mensajes.append(
            f"🔄 Clase reprogramada: {modificado['alumno']} "
            f"del {modificado['fecha_anterior']} {modificado['hora_anterior']} "
            f"→ {modificado['nueva_fecha']} {modificado['nueva_hora']}"
        )

    conn.commit()
    conn.close()
    return mensajes


# SINCRONIZACION_DIARIA: La función que llama el scheduler.
# Detecta cambios del mes actual y te avisa solo si hay algo nuevo.
# Si no hay cambios, silencio total.
def sincronizacion_diaria():
    hoy = date.today()
    cambios = detectar_cambios(hoy.month, hoy.year)

    total = len(cambios["nuevos"]) + len(cambios["cancelados"]) + len(cambios["modificados"])

    if total == 0:
        return  # Sin cambios, sin mensaje

    mensajes = procesar_cambios(cambios)

    texto = "📅 Sincronización con Calendar:\n\n"
    texto += "\n\n".join(mensajes)
    enviar_mensaje(texto)