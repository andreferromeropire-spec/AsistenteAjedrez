# borrar_michael_abril.py
from database import get_connection
conn = get_connection()
conn.execute("""
    DELETE FROM clases 
    WHERE alumno_id = 4 
    AND fecha = '2026-04-01' 
    AND hora = '12:30'
""")
conn.commit()
conn.close()
print("Listo")