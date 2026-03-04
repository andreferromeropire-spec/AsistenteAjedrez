import gspread
from google.oauth2.service_account import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from database import get_connection, crear_tablas
from promociones import agregar_promo
import re
import os

# SCOPES: permisos que necesitamos para leer Sheets y Calendar
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

SHEET_ID = "1LpfRUAPy-05h7IpRuZdR9iWqs_joW5xASJUQXt2GPX4"

def autenticar_sheets():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import json

    SCOPES_COMPLETOS = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly'
    ]

    creds = None

    # Intentar leer token desde variable de entorno o archivo
    token_data = os.environ.get("GOOGLE_TOKEN")
    if token_data:
        creds = Credentials.from_authorized_user_info(json.loads(token_data), SCOPES_COMPLETOS)
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES_COMPLETOS)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Solo funciona localmente
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds_data = os.environ.get("GOOGLE_CREDENTIALS")
            if creds_data:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    f.write(creds_data)
                    temp_path = f.name
                flow = InstalledAppFlow.from_client_secrets_file(temp_path, SCOPES_COMPLETOS)
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES_COMPLETOS)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    cliente = gspread.authorize(creds)
    return cliente

def parsear_moneda(simbolo):
    """Convierte símbolo del Sheet al nombre interno de la DB"""
    simbolo = str(simbolo).strip()
    if simbolo == "$":
        return "Dólar"
    elif simbolo in ["£", "GBP"]:
        return "Libra Esterlina"
    elif simbolo in ["ARS", "$AR"]:
        return "Pesos"
    return simbolo

def parsear_promos(texto_promo, moneda):
    """
    Convierte texto como:
    '1 clase: $28/h
     4-5 clases: $26/h
     6-10 clases: $25/h'
    en lista de rangos: [(1,1,28), (4,5,26), (6,10,25)]
    """
    rangos = []
    if not texto_promo or str(texto_promo).strip() == "":
        return rangos
    
    lineas = str(texto_promo).strip().split("\n")
    for linea in lineas:
        linea = linea.strip().strip('"')
        if not linea:
            continue
        
        # Extraer números: rango de clases y precio
        numeros = re.findall(r'\d+(?:\.\d+)?', linea.replace(",", "").replace(".", ""))
        numeros = re.findall(r'\d+', linea)
        
        if len(numeros) == 2:
            # "1 clase: $28/h" → desde=1, hasta=1, precio=28
            desde = int(numeros[0])
            hasta = int(numeros[0])
            precio = int(numeros[1])
            rangos.append((desde, hasta, precio))
        elif len(numeros) == 3:
            # "4-5 clases: $26/h" → desde=4, hasta=5, precio=26
            desde = int(numeros[0])
            hasta = int(numeros[1])
            precio = int(numeros[2])
            rangos.append((desde, hasta, precio))
    
    return rangos

def sincronizar_alumnos_desde_sheets():
    crear_tablas()
    cliente = autenticar_sheets()
    sheet = cliente.open_by_key(SHEET_ID).sheet1
    filas = sheet.get_all_values()
    
    # Fila 5 (índice 4) es el encabezado
    encabezado = filas[4]
    datos = filas[5:]  # Desde fila 6 en adelante
    
    conn = get_connection()
    cursor = conn.cursor()
    
    alumnos_cargados = 0
    errores = []

    for fila in datos:
        if len(fila) < 3 or not fila[2].strip():
            continue  # Fila vacía o sin nombre
        
        representante = fila[1].strip() if fila[1].strip() not in ["", "-"] else None
        nombre        = fila[2].strip()
        pais          = fila[3].strip() or None
        idioma        = fila[4].strip() or None
        contacto      = fila[5].strip() or None
        mail          = fila[6].strip() or None
        whatsapp      = fila[7].strip() or None
        promo_texto   = fila[8].strip() if len(fila) > 8 else ""
        moneda_sym    = fila[9].strip() if len(fila) > 9 else ""
        metodo_pago   = fila[10].strip() if len(fila) > 10 else None
        modalidad     = fila[11].strip() if len(fila) > 11 else None
        recordatorio  = fila[12].strip() if len(fila) > 12 else None

        moneda = parsear_moneda(moneda_sym)

        try:
            # Si el alumno ya existe, actualizarlo. Si no, crearlo.
            cursor.execute("SELECT id FROM alumnos WHERE nombre = ?", (nombre,))
            existente = cursor.fetchone()
            
            if existente:
                alumno_id = existente['id']
                cursor.execute("""
                    UPDATE alumnos SET representante=?, pais=?, idioma=?,
                    contacto_preferido=?, mail=?, whatsapp=?, moneda=?,
                    metodo_pago=?, modalidad=?, notas_recordatorio=?
                    WHERE id=?
                """, (representante, pais, idioma, contacto, mail, whatsapp,
                      moneda, metodo_pago, modalidad, recordatorio, alumno_id))
                # Borrar promos viejas para recargar
                cursor.execute("DELETE FROM promociones WHERE alumno_id=?", (alumno_id,))
            else:
                cursor.execute("""
                    INSERT INTO alumnos (nombre, representante, pais, idioma,
                    contacto_preferido, mail, whatsapp, moneda, metodo_pago,
                    modalidad, notas_recordatorio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nombre, representante, pais, idioma, contacto, mail,
                      whatsapp, moneda, metodo_pago, modalidad, recordatorio))
                alumno_id = cursor.lastrowid

            conn.commit()

            # Cargar promociones
            rangos = parsear_promos(promo_texto, moneda)
            for desde, hasta, precio in rangos:
                agregar_promo(alumno_id, desde, hasta, precio, moneda)

            print(f"✓ {nombre} ({len(rangos)} rangos de promo)")
            alumnos_cargados += 1

        except Exception as e:
            print(f"✗ Error con {nombre}: {e}")
            errores.append(nombre)

    conn.close()
    print(f"\nListo: {alumnos_cargados} alumnos cargados, {len(errores)} errores")
    if errores:
        print("Fallaron:", errores)

if __name__ == "__main__":
    sincronizar_alumnos_desde_sheets()