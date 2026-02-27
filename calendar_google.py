import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, date, timedelta
from database import get_connection
from clases import agendar_clase, cancelar_clase
from alumnos import obtener_todos_los_alumnos

# Permisos que necesitamos: solo lectura del calendario
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# AUTENTICAR: Conecta con Google Calendar.
# La primera vez abre el navegador para que autorices.
# Después guarda el token en token.json para no pedir permiso de nuevo.
def autenticar():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)

# OBTENER_EVENTOS: Trae todos los eventos de tu calendario
# entre dos fechas específicas
def obtener_eventos(fecha_inicio, fecha_fin):
    servicio = autenticar()
    
    eventos = servicio.events().list(
        calendarId='primary',
        timeMin=fecha_inicio.isoformat() + 'T00:00:00Z',
        timeMax=fecha_fin.isoformat() + 'T23:59:59Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return eventos.get('items', [])

# BUSCAR_ALUMNO_EN_EVENTO: Intenta identificar qué alumno
# corresponde a un evento del calendario por el título
def buscar_alumno_en_evento(titulo):
    from alumnos import obtener_todos_los_alumnos
    alumnos_activos = obtener_todos_los_alumnos()
    titulo_min = titulo.lower()

    for alumno in alumnos_activos:
        # Extraemos nombres y limpiamos posibles espacios extras
        nombre = alumno['nombre'].lower().strip()
        representante = (alumno['representante'] or "").lower().strip()
        
        # 1. ¿El nombre del alumno está en el título? (Ej: "George" en "Morgan (George y David)")
        if nombre in titulo_min:
            return alumno
            
        # 2. ¿El nombre del representante está en el título? (Ej: "Morgan" en "Morgan Kids")
        if representante and representante in titulo_min:
            return alumno
            
        # 3. Caso especial para "Lucia de Elizalde" si en la DB solo dice "Lucia"
        # Esto busca si alguna palabra del nombre del alumno está en el título
        if any(palabra in titulo_min for palabra in nombre.split() if len(palabra) > 2):
            return alumno

    return None


# SINCRONIZAR_MES: Lee tu Google Calendar y registra
# todas las clases del mes en la base de datos
def sincronizar_mes(mes, anio):
    from datetime import datetime, date
    from clases import agendar_clase
    
    # 1. Definir el rango del mes
    if mes == 12:
        proximo_mes, proximo_anio = 1, anio + 1
    else:
        proximo_mes, proximo_anio = mes + 1, anio
        
    fecha_inicio = date(anio, mes, 1)
    fecha_fin = date(proximo_anio, proximo_mes, 1)
    
    # 2. Obtener eventos de Google Calendar
    eventos = obtener_eventos(fecha_inicio, fecha_fin)
    clases_encontradas = 0
    no_identificadas = []

    for evento in eventos:
        titulo = evento.get('summary', '')
        inicio = evento.get('start', {})
        fecha_str = inicio.get('dateTime', inicio.get('date', ''))
        google_event_id = evento.get('id')
        
        # Procesar fecha y hora
        if 'T' in fecha_str:
            fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            fecha = fecha_dt.date().isoformat()
            hora = fecha_dt.strftime('%H:%M')
        else:
            fecha = fecha_str
            hora = "00:00"

        # 3. Identificar al alumno (Objeto sqlite3.Row)
        alumno = buscar_alumno_en_evento(titulo)
        
        if alumno:
            # En sqlite3.Row se accede con corchetes, no con .get()
            id_alumno = alumno['id']
            
            # 4. Agendar la clase principal
            agendar_clase(id_alumno, fecha, hora, 'google_calendar', google_event_id)

            # 5. Lógica de TRASLADO AUTOMÁTICO
            # Acceso directo por nombre de columna
            modalidad_valor = alumno['modalidad'] if alumno['modalidad'] else ""
            modalidad = modalidad_valor.lower()
            
            if "domicilio" in modalidad or "presencial" in modalidad:
                id_traslado = f"traslado_{google_event_id}_{id_alumno}"
                agendar_clase(id_alumno, fecha, hora, 'google_calendar', id_traslado)
            
            clases_encontradas += 1
        else:
            no_identificadas.append(titulo)

    return {
        "clases_registradas": clases_encontradas,
        "no_identificadas": no_identificadas
    }