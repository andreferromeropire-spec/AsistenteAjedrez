# verificar_test_alumno.py
from database import get_connection
conn = get_connection()

alumno = conn.execute("SELECT * FROM alumnos WHERE nombre = 'Test Alumno'").fetchone()
print(f"Alumno: {dict(alumno)}")

promos = conn.execute("SELECT * FROM promociones WHERE alumno_id = ?", (alumno['id'],)).fetchall()
for p in promos:
    print(f"Promo: {dict(p)}")

conn.close()