# corregir_ruby_abril.py
from database import get_connection
conn = get_connection()
conn.execute("""
    UPDATE clases SET alumno_id = 18
    WHERE fecha = '2026-04-01' 
    AND hora = '12:30'
    AND google_event_id = '1u71deerso6gn9s53rn29eue9h_20260401T153000Z'
""")
conn.commit()
conn.close()
print("Listo - clase de Ruby corregida")