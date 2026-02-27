# limpiar_marzo.py
from database import get_connection
from calendar_google import sincronizar_mes

conn = get_connection()

# Borramos solo las clases SIN google_event_id de marzo
resultado = conn.execute("""
    DELETE FROM clases 
    WHERE strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
    AND (google_event_id IS NULL OR google_event_id = '')
""")

conn.commit()
conn.close()
print(f"Clases borradas: {resultado.rowcount}")

# Re-sincronizamos desde Calendar
print("Sincronizando desde Calendar...")
resultado_sync = sincronizar_mes(3, 2026)
print(f"Clases registradas: {resultado_sync['clases_registradas']}")
print(f"No identificadas: {len(resultado_sync['no_identificadas'])}")
for e in resultado_sync['no_identificadas']:
    print(f"  - {e}")