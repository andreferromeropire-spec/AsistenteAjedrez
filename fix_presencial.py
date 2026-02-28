# fix_precios_presencial.py
from database import get_connection
conn = get_connection()

# Ilay (id 15) - 3 horas
conn.execute("UPDATE promociones SET precio_por_clase = 60000 WHERE alumno_id = 15")

# David y George / Morgan (id 8) - 3 horas  
conn.execute("UPDATE promociones SET precio_por_clase = 60000 WHERE alumno_id = 8")

conn.commit()
conn.close()
print("Listo")