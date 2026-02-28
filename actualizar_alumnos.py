# actualizar_alumnos.py
from database import get_connection

conn = get_connection()

conn.execute("UPDATE alumnos SET representante = 'Alison' WHERE nombre = 'Giuliana'")
conn.execute("UPDATE alumnos SET nombre = 'Henry Chen' WHERE nombre = 'Henry'")
conn.execute("UPDATE alumnos SET nombre = 'Henry Cluter' WHERE nombre = 'Henry (Girl)'")

conn.commit()
conn.close()
print("Listo - alumnos actualizados")