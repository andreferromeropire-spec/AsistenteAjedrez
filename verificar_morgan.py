from database import conectar_db

db = conectar_db()
# Buscamos cuántas clases totales hay para el ID 8 (Morgan/Niños)
total = db.execute('SELECT COUNT(*) FROM clases WHERE alumno_id = 8').fetchone()[0]
# Buscamos específicamente las que dicen traslado
traslados = db.execute('SELECT COUNT(*) FROM clases WHERE alumno_id = 8 AND notas LIKE "%traslado%"').fetchone()[0]

print(f"--- Datos en la DB para Morgan ---")
print(f"Total de registros: {total}")
print(f"De los cuales son traslados: {traslados}")
print(f"Clases 'normales': {total - traslados}")