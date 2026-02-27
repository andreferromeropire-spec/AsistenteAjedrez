# verificar_abril.py
from database import get_connection
conn = get_connection()
clases = conn.execute("""
    SELECT c.*, a.nombre 
    FROM clases c
    JOIN alumnos a ON c.alumno_id = a.id
    WHERE fecha = '2026-04-01'
""").fetchall()
for c in clases:
    print(f"{c['nombre']} - {c['hora']} - {c['google_event_id']}")
conn.close()