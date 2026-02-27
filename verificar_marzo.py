from database import get_connection

conn = get_connection()

resultado = conn.execute("""
    SELECT COUNT(*) as total FROM clases 
    WHERE strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
    AND (google_event_id IS NULL OR google_event_id = '')
""").fetchone()

print(f"Clases sin google_event_id en marzo: {resultado['total']}")

total = conn.execute("""
    SELECT COUNT(*) as total FROM clases 
    WHERE strftime('%m', fecha) = '03'
    AND strftime('%Y', fecha) = '2026'
""").fetchone()

print(f"Total clases en marzo: {total['total']}")

conn.close()