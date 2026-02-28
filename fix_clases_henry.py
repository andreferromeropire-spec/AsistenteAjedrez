# fix_clases_henry.py
from database import get_connection
from calendar_google import sincronizar_mes

conn = get_connection()
conn.execute("""
    DELETE FROM clases 
    WHERE alumno_id IN (2, 16)
    AND strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
""")
conn.commit()
conn.close()
print("Clases de Henry borradas")

print("Re-sincronizando...")
resultado = sincronizar_mes(3, 2026)
print(f"Clases registradas: {resultado['clases_registradas']}")