# ver_michael.py
from database import get_connection
conn = get_connection()
clases = conn.execute("""
    SELECT fecha, hora, estado, origen, google_event_id
    FROM clases 
    WHERE alumno_id = 4
    AND strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
    ORDER BY fecha ASC
""").fetchall()
for c in clases:
    print(f"{c['fecha']} {c['hora']} - {c['estado']} - {c['origen']} - {c['google_event_id']}")
conn.close()