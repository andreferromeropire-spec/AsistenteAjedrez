from promociones import resumen_cobro_alumno, clases_agendadas_mes
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from datetime import date
import os

from interprete import interpretar_mensaje
from notificaciones import configurar_scheduler
from alumnos import buscar_alumno_por_nombre, agregar_alumno
from pagos import registrar_pago, quien_debe_este_mes, total_cobrado_en_mes, historial_de_pagos_alumno
from clases import agendar_clase, cancelar_clase, resumen_clases_alumno_mes

load_dotenv()
app = Flask(__name__)

# Guarda el historial de conversación por número de WhatsApp.
# La clave es el número de teléfono, el valor es una lista de mensajes.
# Se borra cuando se reinicia el servidor, lo cual está bien para nuestro uso.
historiales = {}
MAXIMO_MENSAJES_HISTORIAL = 10  # Guardamos los últimos 10 intercambios

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
    
    elif accion == "registrar_clases_multiple":
        nombres = datos.get("nombres_alumnos", [])
        fecha = datos.get("fecha", date.today().isoformat())
        resultados = []
        for nombre in nombres:
            alumnos = buscar_alumno_por_nombre(nombre)
            if not alumnos:
                resultados.append(f"❌ No encontré a {nombre}")
            else:
                alumno = alumnos[0]
                agendar_clase(
                    alumno_id=alumno["id"],
                    fecha=fecha,
                    hora=datos.get("hora"),
                    origen="manual"
                )
                resultados.append(f"✅ {alumno['nombre']}")
        
        return f"Clases registradas el {fecha}:\n" + "\n".join(resultados)

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
    
    elif accion == "resumen_alumno":
        alumnos = buscar_alumno_por_nombre(datos.get("nombre_alumno", ""))
        if not alumnos:
            return "No encontré ningún alumno con ese nombre."
        alumno = alumnos[0]
        hoy = date.today()
        resumen = resumen_clases_alumno_mes(alumno["id"], hoy.month, hoy.year)
        historial = historial_de_pagos_alumno(alumno["id"])
        pago_este_mes = any(
            p["fecha"].startswith(f"{hoy.year}-{hoy.month:02d}") 
            for p in historial
        )
        respuesta = f"📊 Resumen de {alumno['nombre']} ({hoy.month}/{hoy.year}):\n"
        respuesta += f"• Clases a cobrar: {resumen['a_cobrar']}\n"
        respuesta += f"• Clases dadas: {resumen['dadas']}\n"
        respuesta += f"• Crédito próximo mes: {resumen['credito_para_siguiente_mes']}\n"
        respuesta += f"• Pagó este mes: {'✅ Sí' if pago_este_mes else '❌ No'}"
        return respuesta

    elif accion == "que_tengo_hoy":
        from clases import proximas_clases_alumno
        from alumnos import obtener_todos_los_alumnos
        hoy = date.today().isoformat()
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, a.nombre 
            FROM clases c
            JOIN alumnos a ON c.alumno_id = a.id
            WHERE c.fecha = ? AND c.estado = 'agendada'
            ORDER BY c.hora ASC
        """, (hoy,))
        clases_hoy = cursor.fetchall()
        conn.close()
        if not clases_hoy:
            return f"No tenés clases agendadas para hoy."
        respuesta = f"📅 Clases de hoy ({hoy}):\n"
        for clase in clases_hoy:
            hora = f"a las {clase['hora']}" if clase['hora'] else "sin hora especificada"
            respuesta += f"• {clase['nombre']} {hora}\n"
        return respuesta
    
    
    elif accion == "cuanto_debe_alumno":
        from promociones import resumen_cobro_representante
        nombre = datos.get("nombre_alumno", "")
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)

        # Primero busca como alumno directo
        alumnos = buscar_alumno_por_nombre(nombre)
        
        if alumnos:
            alumno = alumnos[0]
            # Si tiene representante, calcula por representante
            if alumno['representante'] and alumno['representante'] != '-':
                resumen = resumen_cobro_representante(alumno['representante'], mes, anio)
                if resumen:
                    detalle = "\n".join([f"  • {d}" for d in resumen['alumnos']])
                    return (
                        f"💰 Cobro para {resumen['representante']} ({mes}/{anio}):\n"
                        f"{detalle}\n"
                        f"• Total clases: {resumen['total_clases']}\n"
                        f"• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n"
                        f"• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}"
                    )
            # Si no tiene representante, calcula solo para ese alumno
            resumen = resumen_cobro_alumno(alumno['id'], mes, anio)
            if resumen['monto_total'] is None:
                return f"{alumno['nombre']} no tiene promoción cargada todavía."
            return (
                f"💰 Cobro de {resumen['alumno']} ({mes}/{anio}):\n"
                f"• Clases agendadas: {resumen['clases_agendadas']}\n"
                f"• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n"
                f"• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}"
            )

        # Si no encontró como alumno, busca como representante
        resumen = resumen_cobro_representante(nombre, mes, anio)
        if resumen:
            detalle = "\n".join([f"  • {d}" for d in resumen['alumnos']])
            return (
                f"💰 Cobro para {resumen['representante']} ({mes}/{anio}):\n"
                f"{detalle}\n"
                f"• Total clases: {resumen['total_clases']}\n"
                f"• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n"
                f"• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}"
            )

        return "No encontré ningún alumno ni representante con ese nombre."

    elif accion == "clases_del_mes":
        alumnos = buscar_alumno_por_nombre(datos.get("nombre_alumno", ""))
        if not alumnos:
            return "No encontré ningún alumno con ese nombre."
        alumno = alumnos[0]
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)
    
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fecha, hora, estado FROM clases
            WHERE alumno_id = ?
            AND strftime('%m', fecha) = ?
            AND strftime('%Y', fecha) = ?
            AND estado = 'agendada'
            ORDER BY fecha ASC
        """, (alumno["id"], f"{mes:02d}", str(anio)))
        clases = cursor.fetchall()
        conn.close()
    
        if not clases:
            return f"{alumno['nombre']} no tiene clases agendadas en {mes}/{anio}."
    
        respuesta = f"📅 Clases de {alumno['nombre']} en {mes}/{anio}:\n"
        for clase in clases:
            hora = f" a las {clase['hora']}" if clase['hora'] else ""
            respuesta += f"• {clase['fecha']}{hora}\n"
        respuesta += f"\nTotal: {len(clases)} clases"
        return respuesta

    elif accion == "no_entiendo":
        return "No entendí bien. Podés decirme cosas como:\n• 'pagó Lucas 20000 pesos'\n• 'di clase con Henry'\n• 'quién debe este mes'\n• '¿cuánto gané en febrero?'"
    
    else:
        return "No entendí esa acción."

# WEBHOOK: Este es el endpoint que Twilio llama cuando recibís un WhatsApp.
@app.route("/webhook", methods=["POST"])
def webhook():
    mensaje_entrante = request.form.get("Body", "").strip()
    numero = request.form.get("From", "desconocido")  # Número de WhatsApp del que escribe
    respuesta_texto = ""

    # Recupera el historial de este número, o arranca uno nuevo
    if numero not in historiales:
        historiales[numero] = []
    historial = historiales[numero]

    try:
        interpretado = interpretar_mensaje(mensaje_entrante, historial)
        accion = interpretado.get("accion", "no_entiendo")
        datos = interpretado.get("datos", {})
        respuesta_texto = ejecutar_accion(accion, datos)
    except Exception as e:
        respuesta_texto = f"Ocurrió un error: {str(e)}"

    # Agrega el mensaje de Andrea y la respuesta del bot al historial
    historial.append({"role": "user", "content": mensaje_entrante})
    historial.append({"role": "assistant", "content": respuesta_texto})

    # Recorta el historial para no crecer infinitamente
    # Multiplicamos por 2 porque cada intercambio tiene 2 mensajes (user + assistant)
    if len(historial) > MAXIMO_MENSAJES_HISTORIAL * 2:
        historiales[numero] = historial[-(MAXIMO_MENSAJES_HISTORIAL * 2):]

    respuesta = MessagingResponse()
    respuesta.message(respuesta_texto)
    return str(respuesta)

if __name__ == "__main__":
    scheduler = configurar_scheduler()
    app.run(debug=True, port=5000)