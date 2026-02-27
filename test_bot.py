from bot import ejecutar_accion, acciones_pendientes
from interprete import interpretar_mensaje

NUMERO_TEST = "whatsapp:+test"
historial = []

print("🤖 Bot de prueba local. Escribí 'salir' para terminar.\n")

while True:
    mensaje = input("Vos: ").strip()
    if mensaje.lower() == "salir":
        break

    # Misma lógica que el webhook
    if NUMERO_TEST in acciones_pendientes and mensaje.isdigit():
        accion = "aclaracion_alumno"
        datos = {"numero_opcion": int(mensaje)}
    else:
        interpretado = interpretar_mensaje(mensaje, historial)
        accion = interpretado.get("accion", "no_entiendo")
        datos = interpretado.get("datos", {})

    respuesta = ejecutar_accion(accion, datos, NUMERO_TEST)
    print(f"\nBot: {respuesta}\n")

    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": respuesta})