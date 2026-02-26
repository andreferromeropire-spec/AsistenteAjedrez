from database import get_connection
from datetime import date, datetime, timedelta

# Primero necesitamos agregar la tabla de clases a la base de datos.
# La llamamos desde database.py pero la definimos acá para mantener
# todo lo relacionado a clases en el mismo archivo.

def agendar_clase(alumno_id, fecha, hora=None, origen="manual", google_event_id=None, notas=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clases (alumno_id, fecha, hora, estado, origen, google_event_id, notas)
        VALUES (?, ?, ?, 'agendada', ?, ?, ?)
    """, (alumno_id, fecha, hora, origen, google_event_id, notas))
    conn.commit()
    conn.close()
    print(f"Clase agendada para alumno {alumno_id} el {fecha}")

# Marca una clase como dada.
def marcar_clase_dada(clase_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE clases SET estado = 'dada' WHERE id = ?
    """, (clase_id,))
    conn.commit()
    conn.close()
    print(f"Clase {clase_id} marcada como dada.")

# Cancela una clase aplicando la regla de las 24hs.
# Devuelve el estado final para que el bot pueda avisar el resultado.
def cancelar_clase(clase_id, cancelada_por="alumno"):
    conn = get_connection()
    cursor = conn.cursor()

    # Primero busca la clase para saber su fecha
    cursor.execute("SELECT * FROM clases WHERE id = ?", (clase_id,))
    clase = cursor.fetchone()

    if not clase:
        conn.close()
        return "no_encontrada"

    # Si la canceló el alumno, aplica la regla de 24hs
    if cancelada_por == "alumno":
        fecha_clase = datetime.fromisoformat(f"{clase['fecha']} {clase['hora'] or '00:00'}")
        ahora = datetime.now()
        diferencia = fecha_clase - ahora

        if diferencia < timedelta(hours=24):
            # Canceló tarde, se cobra igual
            estado_final = "cancelada_sin_anticipacion"
        else:
            # Canceló a tiempo, queda como crédito
            estado_final = "cancelada_con_anticipacion"
    else:
        # La canceló la profesora, no se cobra ni acredita
        estado_final = "cancelada_por_profesora"

    cursor.execute("""
        UPDATE clases 
        SET estado = ?, cancelada_por = ?, fecha_cancelacion = ?
        WHERE id = ?
    """, (estado_final, cancelada_por, date.today().isoformat(), clase_id))

    conn.commit()
    conn.close()
    return estado_final

# Reprograma una clase a nueva fecha y hora
def reprogramar_clase(clase_id, nueva_fecha, nueva_hora=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE clases 
        SET fecha = ?, hora = ?, estado = 'agendada'
        WHERE id = ?
    """, (nueva_fecha, nueva_hora, clase_id))
    conn.commit()
    conn.close()
    print(f"Clase {clase_id} reprogramada para {nueva_fecha}")

# Devuelve el resumen del mes para un alumno:
# cuántas clases agendadas, dadas, y el balance
def resumen_clases_alumno_mes(alumno_id, mes, anio):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT estado, COUNT(*) as cantidad
        FROM clases
        WHERE alumno_id = ?
        AND strftime('%m', fecha) = ?
        AND strftime('%Y', fecha) = ?
        GROUP BY estado
    """, (alumno_id, f"{mes:02d}", str(anio)))

    resultados = cursor.fetchall()
    conn.close()

    # Convierte a diccionario para fácil acceso
    resumen = {row['estado']: row['cantidad'] for row in resultados}

    # Calcula el balance: clases a cobrar vs dadas
    a_cobrar = resumen.get('agendada', 0) + resumen.get('cancelada_sin_anticipacion', 0)
    dadas = resumen.get('dada', 0)
    credito = resumen.get('cancelada_con_anticipacion', 0)

    return {
        "detalle": resumen,
        "a_cobrar": a_cobrar,
        "dadas": dadas,
        "credito_para_siguiente_mes": credito
    }

# Lista todas las clases agendadas de un alumno (las próximas)
def proximas_clases_alumno(alumno_id):
    conn = get_connection()
    cursor = conn.cursor()
    hoy = date.today().isoformat()
    cursor.execute("""
        SELECT * FROM clases
        WHERE alumno_id = ?
        AND fecha >= ?
        AND estado = 'agendada'
        ORDER BY fecha ASC
    """, (alumno_id, hoy))
    clases = cursor.fetchall()
    conn.close()
    return clases

# Devuelve cuántas clases quedan en el paquete activo de un alumno.
# Cuenta las clases agendadas que todavía no se dieron.
def clases_restantes_paquete(alumno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as restantes
        FROM clases
        WHERE alumno_id = ?
        AND estado = 'agendada'
    """, (alumno_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado['restantes']

# Revisa todos los alumnos con paquete de 10 y devuelve
# los que tienen 2 o menos clases restantes.
# Esto es lo que el bot va a usar para avisarte.
def alumnos_por_renovar_paquete():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Busca alumnos con modalidad de paquete de 10
    cursor.execute("""
        SELECT * FROM alumnos 
        WHERE modalidad = 'Cada 10 clases' AND activo = 1
    """)
    alumnos = cursor.fetchall()
    conn.close()
    
    por_renovar = []
    for alumno in alumnos:
        restantes = clases_restantes_paquete(alumno['id'])
        if restantes <= 2:
            por_renovar.append({
                "alumno": alumno['nombre'],
                "id": alumno['id'],
                "clases_restantes": restantes
            })
    
    return por_renovar