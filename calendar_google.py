import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.oauth2 import service_account as google_service_account
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, date, timedelta
from database import get_connection, get_config, set_config
from clases import agendar_clase, cancelar_clase
from alumnos import obtener_todos_los_alumnos


class GoogleAuthRequired(Exception):
    """Se lanza cuando no hay token válido ni refresh_token para renovar (requiere flujo OAuth web)."""
    pass

# Permisos que necesitamos: solo lectura del calendario
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]
SCOPES_CALENDAR_ONLY = ['https://www.googleapis.com/auth/calendar.readonly']

# AUTENTICAR: Conecta con Google Calendar.
# - Si GOOGLE_SERVICE_ACCOUNT_JSON y GOOGLE_CALENDAR_ID están seteados → usa cuenta de servicio.
# - Si no → token OAuth: primero DB (configuracion), luego GOOGLE_TOKEN, luego token.json.
#   Si no hay token válido y hay refresh_token, renueva y guarda en DB.
#   Si no hay token válido ni refresh_token, lanza GoogleAuthRequired (flujo web en dashboard).
def autenticar():
    creds = None

    # Opción piloto: cuenta de servicio + calendario del profe
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json and os.environ.get("GOOGLE_CALENDAR_ID"):
        try:
            info = json.loads(sa_json)
            creds = google_service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES_CALENDAR_ONLY
            )
        except Exception:
            creds = None
    if creds is not None:
        return build('calendar', 'v3', credentials=creds)

    # Token de usuario: primero archivo (GOOGLE_TOKEN_FILE), luego DB, luego env, luego token.json
    token_json = None
    token_file = os.environ.get('GOOGLE_TOKEN_FILE')
    if token_file and os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                token_json = f.read()
            if token_json:
                print('autenticar: token desde GOOGLE_TOKEN_FILE')
        except Exception as e:
            print('autenticar: error leyendo GOOGLE_TOKEN_FILE:', e)
    if not token_json:
        token_json = get_config('google_token') or os.environ.get("GOOGLE_TOKEN")
        if token_json:
            print('autenticar: token desde', 'DB' if get_config('google_token') else 'GOOGLE_TOKEN env')
    if token_json:
        try:
            info = json.loads(token_json)
            if not info.get('refresh_token') or not info.get('client_id') or not info.get('client_secret'):
                print('autenticar: token sin refresh_token/client_id/client_secret, ignorando')
                creds = None
            else:
                creds = Credentials.from_authorized_user_info(info, SCOPES)
        except Exception as e:
            print('autenticar: error creando Credentials:', type(e).__name__, str(e))
            creds = None
    if not creds and os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception:
            creds = None

    if not creds:
        print('autenticar: GoogleAuthRequired (no token valido o creds no creadas)')
        raise GoogleAuthRequired("No hay token de Google; reautorizar desde el dashboard.")

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                set_config('google_token', creds.to_json())
            except (RefreshError, Exception) as e:
                if "invalid_grant" in str(e).lower() or "expired" in str(e).lower() or "revoked" in str(e).lower():
                    raise GoogleAuthRequired("Token expirado o revocado; reautorizar desde el dashboard.")
                raise
        else:
            raise GoogleAuthRequired("Token expirado sin refresh; reautorizar desde el dashboard.")

    return build('calendar', 'v3', credentials=creds)


def crear_flow_google(redirect_uri, state=None):
    """Crea un Flow OAuth para flujo web usando GOOGLE_CREDENTIALS (cliente tipo Aplicación web).
    state: opcional, para el callback (mismo state que en authorization_url)."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS no definido")
    client_config = json.loads(creds_json)
    kwargs = {"redirect_uri": redirect_uri}
    if state is not None:
        kwargs["state"] = state
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        **kwargs
    )

# OBTENER_EVENTOS: Trae todos los eventos del calendario
# entre dos fechas. Si GOOGLE_CALENDAR_ID está definido (piloto), usa ese; si no, "primary".
def obtener_eventos(fecha_inicio, fecha_fin):
    servicio = autenticar()
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID") or "primary"

    eventos = servicio.events().list(
        calendarId=calendar_id,
        timeMin=fecha_inicio.isoformat() + 'T00:00:00Z',
        timeMax=fecha_fin.isoformat() + 'T23:59:59Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return eventos.get('items', [])

# BUSCAR_ALUMNO_EN_EVENTO: Intenta identificar qué alumno
# corresponde a un evento del calendario por el título.
#
# La lógica tiene 4 pasadas, de más precisa a menos precisa:
# 1. Nombre completo del alumno en el título (ej: "Henry Chen" en "Chess Henry Chen")
# 2. Apellido del representante o alias completo
# 3. Todas las palabras del nombre están en el título (match parcial seguro)
# 4. Al menos una palabra larga está en el título (fallback, solo si no hay ambigüedad)
def buscar_alumno_en_evento(titulo):
    # Ignorar todo lo que venga después de " and " o " y " (suele ser el nombre de Andrea)
    if " and " in titulo.lower():
        titulo = titulo.lower().split(" and ")[0]
    elif " y " in titulo:
        titulo = titulo.split(" y ")[0]

    alumnos_activos = obtener_todos_los_alumnos()
    titulo_min = titulo.lower()

    # PASADA 1: nombre completo exacto del alumno
    # "Henry Chen" → solo matchea si "henry chen" está en el título
    for alumno in alumnos_activos:
        nombre = alumno['nombre'].lower().strip()
        if nombre in titulo_min:
            return alumno

    # PASADA 2: alias o apellido del representante completo
    for alumno in alumnos_activos:
        rep_valor = alumno['representante'] or ""
        representante = "" if rep_valor.strip() == "-" else rep_valor.lower().strip()
        alias = (alumno['alias'] or "").lower().strip()

        if alias and len(alias) >= 3 and alias in titulo_min:
            return alumno
        if representante and len(representante) >= 3 and representante in titulo_min:
            return alumno

    # PASADA 3: todas las palabras del nombre están en el título
    # Más seguro que buscar palabra suelta — exige que estén TODAS
    # Ej: ["henry", "chen"] → ambas deben aparecer en el título
    for alumno in alumnos_activos:
        palabras = alumno['nombre'].lower().strip().split()
        palabras_largas = [p for p in palabras if len(p) > 3]
        if palabras_largas and all(p in titulo_min for p in palabras_largas):
            return alumno

    # PASADA 4: al menos una palabra larga, pero solo si hay un único candidato
    # Evita que "henry" matchee ambos Henrys
    candidatos = []
    for alumno in alumnos_activos:
        nombre = alumno['nombre'].lower().strip()
        if any(palabra in titulo_min for palabra in nombre.split() if len(palabra) > 3):
            candidatos.append(alumno)
    if len(candidatos) == 1:
        return candidatos[0]

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