from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from datetime import date
import os

from interprete import interpretar_mensaje
from alumnos import buscar_alumno_por_nombre, agregar_alumno
from pagos import registrar_pago, quien_debe_este_mes, total_cobrado_en_mes
from clases import agendar_clase, cancelar_clase, resumen_clases_alumno_mes

load_dotenv()
app = Flask(__name__)

# EJECUTAR_ACCION: Recibe la acción interpretada y llama a la función correcta.
# Es el puente entre lo que Claude entendió y lo que el sistema hace.
def ejecutar_accion(accion, datos):
    
    if accion == "registrar_pago":
        # Primero busca el alumno por nombre
        alumnos = buscar_alumno_por_nombre(datos.get("nombre_alumno", ""))
        if not alumnos:
            return f"No encontré ningún alumno con ese nombre. ¿Lo escribiste bien?"
        alumno = alumnos[0]
        registrar_pago(
            alumno_id=alumno["id"],
            monto=datos.get("monto"),
            moneda=datos.get("moneda"),
            metodo=datos.get("metodo"),
            notas=datos.get("notas")
        )
        return f"✅ Registré el pago de {alumno['nombre']}: {datos.get('monto')} {datos.get('moneda')} por {datos.get('metodo')}."

    elif accion == "registrar_clase":
        alumnos = buscar_alumno_por_nombre(datos.get("nombre_alumno", ""))
        if not alumnos:
            return f"No encontré ningún alumno con ese nombre."
        alumno = alumnos[0]
        fecha = datos.get("fecha", date.today().isoformat())
        agendar_clase(
            alumno_id=alumno["id"],
            fecha=fecha,
            hora=datos.get("hora"),
            origen="manual"
        )
        return f"✅ Registré clase con {alumno['nombre']} el {fecha}."

    elif accion == "quien_debe":
        deudores = quien_debe_este_mes()
        if not deudores:
            return "🎉 Todos los alumnos mensuales pagaron este mes."
        lista = "\n".join([f"• {a['nombre']} ({a['pais']})" for a in deudores])
        return f"Los siguientes alumnos no pagaron este mes:\n{lista}"

    elif accion == "cuanto_gane":
        mes = datos.get("mes", date.today().month)
        anio = datos.get("anio", date.today().year)
        totales = total_cobrado_en_mes(mes, anio)
        if not totales:
            return f"No encontré pagos registrados para ese mes."
        respuesta = f"💰 Total cobrado en {mes}/{anio}:\n"
        respuesta += "\n".join([f"• {moneda}: {total}" for moneda, total in totales.items()])
        return respuesta

    elif accion == "cancelar_clase":
        alumnos = buscar_alumno_por_nombre(datos.get("nombre_alumno", ""))
        if not alumnos:
            return f"No encontré ningún alumno con ese nombre."
        alumno = alumnos[0]
        # Busca la clase más próxima del alumno para cancelar
        from clases import proximas_clases_alumno
        proximas = proximas_clases_alumno(alumno["id"])
        if not proximas:
            return f"No encontré clases agendadas para {alumno['nombre']}."
        clase = proximas[0]
        resultado = cancelar_clase(clase["id"], cancelada_por=datos.get("cancelada_por", "alumno"))
        mensajes = {
            "cancelada_con_anticipacion": f"✅ Clase de {alumno['nombre']} cancelada. Avisó a tiempo, queda como crédito.",
            "cancelada_sin_anticipacion": f"⚠️ Clase de {alumno['nombre']} cancelada. No avisó a tiempo, se cobra igual.",
            "cancelada_por_profesora": f"✅ Clase de {alumno['nombre']} cancelada por vos. No se cobra."
        }
        return mensajes.get(resultado, "Clase cancelada.")

    elif accion == "alumno_nuevo":
        agregar_alumno(
            nombre=datos.get("nombre"),
            pais=datos.get("pais"),
            moneda=datos.get("moneda"),
            metodo_pago=datos.get("metodo_pago"),
            modalidad=datos.get("modalidad"),
            precio=datos.get("precio"),
            whatsapp=datos.get("whatsapp"),
            mail=datos.get("mail")
        )
        return f"✅ Alumno {datos.get('nombre')} agregado correctamente."

    elif accion == "no_entiendo":
        return "No entendí bien. Podés decirme cosas como:\n• 'pagó Lucas 20000 pesos'\n• 'di clase con Henry'\n• 'quién debe este mes'\n• '¿cuánto gané en febrero?'"

    else:
        return "No entendí esa acción."

# WEBHOOK: Este es el endpoint que Twilio llama cuando recibís un WhatsApp.
@app.route("/webhook", methods=["POST"])
def webhook():
    mensaje_entrante = request.form.get("Body", "").strip()
    respuesta_texto = ""

    try:
        interpretado = interpretar_mensaje(mensaje_entrante)
        accion = interpretado.get("accion", "no_entiendo")
        datos = interpretado.get("datos", {})
        respuesta_texto = ejecutar_accion(accion, datos)
    except Exception as e:
        respuesta_texto = f"Ocurrió un error: {str(e)}"

    respuesta = MessagingResponse()
    respuesta.message(respuesta_texto)
    return str(respuesta)

if __name__ == "__main__":
    app.run(debug=True, port=5000)