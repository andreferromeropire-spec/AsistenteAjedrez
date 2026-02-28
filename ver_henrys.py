# ver_henrys.py
from database import get_connection
conn = get_connection()
alumnos = conn.execute("SELECT id, nombre FROM alumnos WHERE nombre LIKE '%Henry%'").fetchall()
for a in alumnos:
    print(f"ID: {a['id']} - Nombre: {a['nombre']}")
clases = conn.execute("""
    SELECT alumno_id, COUNT(*) as total FROM clases 
    WHERE strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
    AND estado = 'agendada'
    AND alumno_id IN (SELECT id FROM alumnos WHERE nombre LIKE '%Henry%')
    GROUP BY alumno_id
""").fetchall()
for c in clases:
    print(f"Alumno ID: {c['alumno_id']} - Clases: {c['total']}")
conn.close()