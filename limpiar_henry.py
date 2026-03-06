# limpiar_henry.py
# Borra todas las clases de Henry Chen en marzo 2026
# para que la sincronización las reasigne correctamente

from database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Ver qué ID tiene Henry Chen
cursor.execute("SELECT id, nombre FROM alumnos WHERE nombre LIKE '%Henry Chen%'")
henry_chen = cursor.fetchone()
print(f"Henry Chen: id={henry_chen['id']}, nombre={henry_chen['nombre']}")

# Contar clases a borrar
cursor.execute("""
    SELECT COUNT(*) as total FROM clases
    WHERE alumno_id = ?
    AND strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
""", (henry_chen['id'],))
total = cursor.fetchone()['total']
print(f"Clases a borrar: {total}")

# Borrar
cursor.execute("""
    DELETE FROM clases
    WHERE alumno_id = ?
    AND strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
""", (henry_chen['id'],))

conn.commit()
print(f"✅ Listo — {cursor.rowcount} clases de Henry Chen borradas.")
conn.close()
