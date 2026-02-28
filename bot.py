from promociones import calcular_monto, agregar_promo, resumen_cobro_alumno, clases_agendadas_mes
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from datetime import date
import os

from interprete import interpretar_mensaje
from notificaciones import configurar_scheduler
from alumnos import buscar_alumno_por_nombre, agregar_alumno, buscar_alumno_con_sugerencia
from pagos import registrar_pago, quien_debe_este_mes, total_cobrado_en_mes, historial_de_pagos_alumno
from clases import agendar_clase, cancelar_clase, resumen_clases_alumno_mes, reprogramar_clase

from database import crear_tablas
crear_tablas()

load_dotenv()
app = Flask(__name__)

historiales = {}
MAXIMO_MENSAJES_HISTORIAL = 10

# Cuando hay ambigüedad (ej: dos Henry), guardamos acá la acción pendiente
# y la lista de candidatos, esperando que el usuario aclare cuál quiso decir.
acciones_pendientes = {}


def buscar_o_sugerir_con_pendiente(nombre_buscado, numero, accion, datos):
    # Si ya viene con ID directo, búsqueda exacta sin ambigüedad
    if datos.get("alumno_id_directo"):
        from alumnos import obtener_alumno_por_id
        alumno = obtener_alumno_por_id(datos["alumno_id_directo"])
        return alumno, None
    

    alumnos, sugerencias = buscar_alumno_con_sugerencia(nombre_buscado)

    if not alumnos:
        return None, f"No encontré ningún alumno con el nombre '{nombre_buscado}'. ¿Lo escribiste bien?"

    if len(alumnos) > 1:
        acciones_pendientes[numero] = {
            "accion": accion,
            "datos": datos,
            "candidatos": [{k: a[k] for k in a.keys()} for a in alumnos]
        }
        lista = "\n".join([
            f"{i+1}. {a['nombre']} (representante: {a['representante'] or 'sin representante'})"
            for i, a in enumerate(alumnos)
        ])
        return None, f"Encontré más de un alumno con ese nombre:\n{lista}\n\n¿A cuál te referís? Respondé con el número o el nombre completo."

    alumno = alumnos[0]
    if sugerencias:
        return alumno, f"⚠️ No encontré '{nombre_buscado}', usé {alumno['nombre']}."
    return alumno, None


def ejecutar_accion(accion, datos, numero):

    if accion == "aclaracion_alumno": 
        if numero not in acciones_pendientes:
            return "No tenía ninguna acción pendiente. ¿Qué querés hacer?"

        pendiente = acciones_pendientes[numero]
        candidatos = pendiente["candidatos"]
        numero_opcion = datos.get("numero_opcion")
        nombre_aclaracion = datos.get("nombre_alumno", "")

        alumno_elegido = None
        if numero_opcion and 1 <= numero_opcion <= len(candidatos):
            alumno_elegido = candidatos[numero_opcion - 1]
        elif nombre_aclaracion:
            for c in candidatos:
                if nombre_aclaracion.lower() in c['nombre'].lower():
                    alumno_elegido = c
                    break

        if not alumno_elegido:
            lista = "\n".join([f"{i+1}. {c['nombre']}" for i, c in enumerate(candidatos)])
            return f"No entendí cuál elegiste. Los candidatos son:\n{lista}\n\nRespondé con el número."

        del acciones_pendientes[numero]

        nuevos_datos = pendiente["datos"].copy()
        # Usamos el nombre completo exacto para que no haya ambigüedad
        nuevos_datos["nombre_alumno"] = alumno_elegido["nombre"]
        # Guardamos el id para búsqueda directa
        nuevos_datos["alumno_id_directo"] = alumno_elegido["id"]
        return ejecutar_accion(pendiente["accion"], nuevos_datos, numero)

    elif accion == "registrar_pago":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        registrar_pago(alumno_id=alumno["id"], monto=datos.get("monto"), moneda=datos.get("moneda"), metodo=datos.get("metodo"), notas=datos.get("notas"))
        respuesta = f"✅ Registré el pago de {alumno['nombre']}: {datos.get('monto')} {datos.get('moneda')} por {datos.get('metodo')}."
        return (aviso + "\n" + respuesta) if aviso else respuesta

    elif accion == "registrar_clase":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        fecha = datos.get("fecha", date.today().isoformat())
        agendar_clase(alumno_id=alumno["id"], fecha=fecha, hora=datos.get("hora"), origen="manual")
        respuesta = f"✅ Registré clase con {alumno['nombre']} el {fecha}."
        return (aviso + "\n" + respuesta) if aviso else respuesta

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
                agendar_clase(alumno_id=alumno["id"], fecha=fecha, hora=datos.get("hora"), origen="manual")
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
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
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
        respuesta = mensajes.get(resultado, "Clase cancelada.")
        return (aviso + "\n" + respuesta) if aviso else respuesta

    elif accion == "reprogramar_clase":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        fecha_original = datos.get("fecha_original")
        nueva_fecha = datos.get("nueva_fecha")
        nueva_hora = datos.get("nueva_hora")
        if not fecha_original or not nueva_fecha:
            return "Necesito la fecha original y la nueva fecha para reprogramar."
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM clases
            WHERE alumno_id = ? AND fecha = ? AND estado = 'agendada'
        """, (alumno["id"], fecha_original))
        clase = cursor.fetchone()
        conn.close()
        if not clase:
            return f"No encontré una clase agendada de {alumno['nombre']} el {fecha_original}."
        reprogramar_clase(clase["id"], nueva_fecha, nueva_hora)
        respuesta = f"✅ Clase de {alumno['nombre']} reprogramada del {fecha_original} al {nueva_fecha}"
        if nueva_hora:
            respuesta += f" a las {nueva_hora}"
        respuesta += "."
        return (aviso + "\n" + respuesta) if aviso else respuesta
    
    elif accion == "alumno_nuevo":
        nuevo = agregar_alumno(
            nombre=datos.get("nombre"),
            pais=datos.get("pais"),
            moneda=datos.get("moneda"),
            metodo_pago=datos.get("metodo_pago"),
            modalidad=datos.get("modalidad"),
            representante=datos.get("representante")
        )
        # Cargar promo si viene en los datos
        from database import get_connection
        conn = get_connection()
        alumno = conn.execute(
            "SELECT id FROM alumnos WHERE nombre = ? ORDER BY id DESC LIMIT 1",
            (datos.get("nombre"),)
        ).fetchone()
        conn.close()
    
        promo = datos.get("promo", [])
        for rango in promo:
            agregar_promo(alumno["id"], rango["desde"], rango["hasta"], rango["precio"], datos.get("moneda"))
        
        return f"✅ Alumno {datos.get('nombre')} agregado con {len(promo)} rangos de promo."

    elif accion == "resumen_alumno":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        hoy = date.today()
        resumen = resumen_clases_alumno_mes(alumno["id"], hoy.month, hoy.year)
        historial_pagos = historial_de_pagos_alumno(alumno["id"])
        pago_este_mes = any(p["fecha"].startswith(f"{hoy.year}-{hoy.month:02d}") for p in historial_pagos)
        respuesta = f"📊 Resumen de {alumno['nombre']} ({hoy.month}/{hoy.year}):\n"
        respuesta += f"• Clases a cobrar: {resumen['a_cobrar']}\n"
        respuesta += f"• Clases dadas: {resumen['dadas']}\n"
        respuesta += f"• Crédito próximo mes: {resumen['credito_para_siguiente_mes']}\n"
        respuesta += f"• Pagó este mes: {'✅ Sí' if pago_este_mes else '❌ No'}"
        return (aviso + "\n" + respuesta) if aviso else respuesta

    elif accion == "que_tengo_hoy":
        hoy = date.today().isoformat()
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, a.nombre FROM clases c
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

    elif accion == "clases_del_mes":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fecha, hora FROM clases
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
        return (aviso + "\n" + respuesta) if aviso else respuesta

    elif accion == "cuanto_debe_alumno":
        from promociones import resumen_cobro_representante
        nombre = datos.get("nombre_alumno", "")
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)
        alumno, aviso = buscar_o_sugerir_con_pendiente(nombre, numero, accion, datos)
        if alumno:
            if alumno['representante'] and alumno['representante'] != '-':
                resumen = resumen_cobro_representante(alumno['representante'], mes, anio)
                if resumen:
                    detalle = "\n".join([f"  • {d}" for d in resumen['alumnos']])
                    respuesta = (f"💰 Cobro para {resumen['representante']} ({mes}/{anio}):\n{detalle}\n• Total clases: {resumen['total_clases']}\n• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}")
                    return (aviso + "\n" + respuesta) if aviso else respuesta
            resumen = resumen_cobro_alumno(alumno['id'], mes, anio)
            if resumen['monto_total'] is None:
                return f"{alumno['nombre']} no tiene promoción cargada todavía."
            respuesta = (f"💰 Cobro de {resumen['alumno']} ({mes}/{anio}):\n• Clases agendadas: {resumen['clases_agendadas']}\n• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}")
            return (aviso + "\n" + respuesta) if aviso else respuesta
        else:
            try:
                resumen = resumen_cobro_representante(nombre, mes, anio)
                if resumen:
                    detalle = "\n".join([f"  • {d}" for d in resumen['alumnos']])
                    return (f"💰 Cobro para {resumen['representante']} ({mes}/{anio}):\n{detalle}\n• Total clases: {resumen['total_clases']}\n• Precio por clase: {resumen['precio_por_clase']} {resumen['moneda']}\n• Total a cobrar: {resumen['monto_total']} {resumen['moneda']}")
            except:
                pass
            return f"No encontré ningún alumno ni representante con el nombre '{nombre}'."
        
    elif accion == "ver_alumno":
        from clases import proximas_clases_alumno
        from promociones import obtener_promo
        from datetime import date

        # Primero intentamos buscar por representante
        from alumnos import buscar_alumno_por_representante
        alumnos_rep = buscar_alumno_por_representante(datos.get("nombre_alumno", ""))
        
        if alumnos_rep:
            # Es un representante → vista agrupada
            hoy = date.today()
            respuesta = f"👤 {datos.get('nombre_alumno')} es representante de:\n\n"
            total_clases = 0
            for a in alumnos_rep:
                proximas = proximas_clases_alumno(a["id"])
                clases_mes = [c for c in proximas if c['fecha'].startswith(f"{hoy.year}-{hoy.month:02d}")]
                dias = ", ".join([c['fecha'].split("-")[2] for c in clases_mes])
                respuesta += f"📚 {a['nombre']}: {dias or 'sin clases'}\n"
                total_clases += len(clases_mes)
            respuesta += f"\nTotal clases: {total_clases}"
            return respuesta

        # No es representante → buscar como alumno normal
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso

        hoy = date.today()
        respuesta = f"📋 {alumno['nombre']}:\n"
        respuesta += f"• Representante: {alumno['representante'] or '—'}\n"
        respuesta += f"• País: {alumno['pais'] or '—'}\n"
        respuesta += f"• Idioma: {alumno['idioma'] or '—'}\n"
        respuesta += f"• WhatsApp: {alumno['whatsapp'] or '—'}\n"
        respuesta += f"• Mail: {alumno['mail'] or '—'}\n"
        respuesta += f"• Moneda: {alumno['moneda'] or '—'}\n"
        respuesta += f"• Método de pago: {alumno['metodo_pago'] or '—'}\n"
        respuesta += f"• Modalidad: {alumno['modalidad'] or '—'}\n"
        respuesta += f"• Alias: {alumno['alias'] or '—'}\n"
        respuesta += f"• Notas: {alumno['notas_recordatorio'] or '—'}\n"

        rangos = obtener_promo(alumno["id"])
        if rangos:
            respuesta += f"\n💰 Promo:\n"
            for r in rangos:
                respuesta += f"• {r['clases_desde']}–{r['clases_hasta']} clases: {r['precio_por_clase']} {r['moneda']}/clase\n"
        else:
            respuesta += f"\n💰 Sin promo cargada\n"

        proximas = proximas_clases_alumno(alumno["id"])
        clases_mes = [c for c in proximas if c['fecha'].startswith(f"{hoy.year}-{hoy.month:02d}")]
        if clases_mes:
            dias = ", ".join([c['fecha'].split("-")[2] for c in clases_mes])
            mes_nombre = hoy.strftime("%B")
            respuesta += f"\n📅 {mes_nombre}: {dias}"
        else:
            respuesta += f"\n📅 Sin clases este mes"

        return (aviso + "\n" + respuesta) if aviso else respuesta    
    
    elif accion == "no_entiendo":
        return "No entendí bien. Podés decirme cosas como:\n• 'pagó Lucas 20000 pesos'\n• 'di clase con Henry'\n• 'quién debe este mes'\n• '¿cuánto gané en febrero?'"

    else:
        return "No entendí esa acción."


@app.route("/webhook", methods=["POST"])
def webhook():
    mensaje_entrante = request.form.get("Body", "").strip()
    numero = request.form.get("From", "desconocido")
    respuesta_texto = ""

    if numero not in historiales:
        historiales[numero] = []
    historial = historiales[numero]


    accion = "no_entiendo"
    datos = {}
    
    try:
        if numero in acciones_pendientes and mensaje_entrante.strip().isdigit():
            accion = "aclaracion_alumno"
            datos = {"numero_opcion": int(mensaje_entrante.strip())}
        else:
            interpretado = interpretar_mensaje(mensaje_entrante, historial)
            accion = interpretado.get("accion", "no_entiendo")
            datos = interpretado.get("datos", {})
            if accion == "aclaracion_alumno" and numero not in acciones_pendientes:
                accion = "no_entiendo"
                datos = {}
        respuesta_texto = ejecutar_accion(accion, datos, numero)
    except Exception as e:
        respuesta_texto = f"Ocurrió un error: {str(e)}"

    historial.append({"role": "user", "content": mensaje_entrante})
    historial.append({"role": "assistant", "content": respuesta_texto})

    # Limpiamos historial si hubo ambigüedad resuelta
    if accion == "aclaracion_alumno" and numero not in acciones_pendientes:
        historiales[numero] = []
    # También limpiamos si el historial tiene muchas menciones de un mismo alumno
    elif len(historial) > MAXIMO_MENSAJES_HISTORIAL * 2:
        historiales[numero] = []  # Reset completo en lugar de truncar

    respuesta = MessagingResponse()
    respuesta.message(respuesta_texto)
    return str(respuesta)


if __name__ == "__main__":
    scheduler = configurar_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)