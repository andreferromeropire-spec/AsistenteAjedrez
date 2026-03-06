Ver henrys · PY
Copy

from database import get_connection

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT id, nombre, representante FROM alumnos WHERE nombre LIKE '%henry%' OR nombre LIKE '%Henry%'")
henrys = cursor.fetchall()
for h in henrys:
    print(f"id={h['id']} | nombre='{h['nombre']}' | rep='{h['representante']}'")

conn.close()












