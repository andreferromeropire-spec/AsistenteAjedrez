from difflib import get_close_matches
import sqlite3
from database import get_connection

# Devuelve la lista completa de alumnos activos
def obtener_todos_los_alumnos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alumnos WHERE activo = 1")
    alumnos = cursor.fetchall()
    conn.close()
    return alumnos

# Busca alumnos por nombre, funciona con nombre parcial
# Por ejemplo "Mar" encuentra "María" y "Marco"
def buscar_alumno_por_nombre(nombre):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM alumnos WHERE nombre LIKE ? AND activo = 1",
        (f"%{nombre}%",)
    )
    alumnos = cursor.fetchall()
    conn.close()
    return alumnos

# Busca un alumno específico por su ID numérico
def obtener_alumno_por_id(alumno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alumnos WHERE id = ?", (alumno_id,))
    alumno = cursor.fetchone()
    conn.close()
    return alumno

# Modifica cualquier campo de un alumno existente
# campo puede ser: "precio", "modalidad", "whatsapp", etc.
def actualizar_alumno(alumno_id, campo, nuevo_valor):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE alumnos SET {campo} = ? WHERE id = ?",
        (nuevo_valor, alumno_id)
    )
    conn.commit()
    conn.close()
    print(f"Alumno {alumno_id} actualizado: {campo} = {nuevo_valor}")

# Agrega un alumno nuevo a la base de datos
def agregar_alumno(nombre, representante=None, pais=None, idioma=None,
                   contacto_preferido=None, mail=None, whatsapp=None,
                   horas_semanales=None, dia_habitual=None, precio=None,
                   moneda=None, metodo_pago=None, modalidad=None,
                   notas_recordatorio=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alumnos 
        (nombre, representante, pais, idioma, contacto_preferido, mail,
         whatsapp, horas_semanales, dia_habitual, precio, moneda,
         metodo_pago, modalidad, notas_recordatorio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (nombre, representante, pais, idioma, contacto_preferido, mail,
          whatsapp, horas_semanales, dia_habitual, precio, moneda,
          metodo_pago, modalidad, notas_recordatorio))
    conn.commit()
    conn.close()
    print(f"Alumno {nombre} agregado correctamente.")

    from difflib import get_close_matches

def buscar_alumno_con_sugerencia(nombre):
    # Primero intenta la búsqueda normal
    resultado = buscar_alumno_por_nombre(nombre)
    if resultado:
        return resultado, None  # Encontró, no hay sugerencia
    
    # Si no encontró, busca nombres parecidos
    todos = obtener_todos_los_alumnos()
    nombres = [a['nombre'] for a in todos]
    sugerencias = get_close_matches(nombre, nombres, n=3, cutoff=0.5)
    
    if sugerencias:
        # Busca el alumno que mejor coincide
        mejor = buscar_alumno_por_nombre(sugerencias[0])
        return mejor, sugerencias  # Devuelve el alumno y las sugerencias
    
    return [], None  # No encontró nada

def buscar_alumno_con_sugerencia(nombre):
    # Primero intenta la búsqueda normal por nombre
    resultado = buscar_alumno_por_nombre(nombre)
    if resultado:
        return resultado, None

    # Si no encontró, busca por representante
    resultado = buscar_alumno_por_representante(nombre)
    if resultado:
        return resultado, None

    # Si tampoco, busca nombres parecidos
    todos = obtener_todos_los_alumnos()
    nombres = [a['nombre'] for a in todos]
    sugerencias = get_close_matches(nombre, nombres, n=3, cutoff=0.5)

    if sugerencias:
        mejor = buscar_alumno_por_nombre(sugerencias[0])
        return mejor, sugerencias

    return [], None

def buscar_alumno_por_representante(nombre_representante):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM alumnos WHERE representante LIKE ? AND activo = 1",
        (f"%{nombre_representante}%",)
    )
    alumnos = cursor.fetchall()
    conn.close()
    return alumnos