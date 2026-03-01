from bot import ejecutar_accion, acciones_pendientes
from interprete import interpretar_mensaje

NUMERO_TEST = "whatsapp:+test"
historial = []

print("🤖 Bot de prueba local. Escribí 'salir' para terminar.\n")

while True:
    mensaje = input("Vos: ").strip()
    if mensaje.lower() == "salir":
        break

    if NUMERO_TEST in acciones_pendientes and mensaje.isdigit():
        pendiente = acciones_pendientes[NUMERO_TEST]
        if pendiente.get("accion") == "confirmar_borrado":
            accion = "confirmar_borrado"
            datos = {"numero_opcion": int(mensaje)}
        else:
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

    if accion == "aclaracion_alumno" and NUMERO_TEST not in acciones_pendientes:
        historial = []