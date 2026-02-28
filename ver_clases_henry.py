# ver_clases_henry.py
from database import get_connection
conn = get_connection()
clases = conn.execute("""
    SELECT alumno_id, fecha, hora FROM clases 
    WHERE alumno_id IN (2, 16)
    AND strftime('%m', fecha) = '03'
    ORDER BY fecha ASC
""").fetchall()
for c in clases:
    print(f"ID: {c['alumno_id']} - {c['fecha']} {c['hora']}")
conn.close()