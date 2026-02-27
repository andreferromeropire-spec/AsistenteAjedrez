from calendar_google import sincronizar_mes

print("--- Iniciando Sincronización de Marzo 2026 ---")
resultado = sincronizar_mes(3, 2026)

print(f"\n✅ Proceso terminado:")
print(f"• Clases registradas con éxito: {resultado['clases_registradas']}")
print(f"• Clases que no pude identificar: {len(resultado['no_identificadas'])}")

if resultado['no_identificadas']:
    print("\n⚠️ Los siguientes eventos en Calendar no coinciden con ningún alumno:")
    for evento in resultado['no_identificadas']:
        print(f"  - {evento}")