from sincronizacion import detectar_cambios, procesar_cambios

cambios = detectar_cambios(3, 2026)

print(f"Nuevos: {len(cambios['nuevos'])}")
print(f"Cancelados: {len(cambios['cancelados'])}")
print(f"Modificados: {len(cambios['modificados'])}")

for n in cambios['nuevos']:
    print(f"  NUEVO: {n['titulo']} - {n['fecha']} {n['hora']}")
for c in cambios['cancelados']:
    print(f"  CANCELADO: {c['alumno']} - {c['fecha']}")
for m in cambios['modificados']:
    print(f"  MODIFICADO: {m['alumno']} {m['fecha_anterior']} → {m['nueva_fecha']}")

# Procesar los cambios
print("\n--- Procesando cambios ---")
mensajes = procesar_cambios(cambios)
for msg in mensajes:
    print(msg)