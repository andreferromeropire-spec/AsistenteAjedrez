# fix_henry_cutler.py
from database import get_connection
conn = get_connection()
conn.execute("UPDATE alumnos SET nombre = 'Henry Cutler' WHERE id = 16")
conn.commit()
conn.close()
print("Listo")