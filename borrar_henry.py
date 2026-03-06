from database import get_connection
conn = get_connection()
r = conn.execute("DELETE FROM clases WHERE alumno_id=4 AND strftime('%m',fecha)='03' AND strftime('%Y',fecha)='2026'")
conn.commit()
print('Borradas:', r.rowcount)
conn.close()