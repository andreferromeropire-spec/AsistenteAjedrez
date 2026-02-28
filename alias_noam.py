# alias_nouham.py
from database import get_connection
conn = get_connection()
conn.execute("UPDATE alumnos SET alias = 'noam' WHERE nombre = 'Nouham'")
conn.commit()
conn.close()
print("Listo")