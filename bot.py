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

acciones_pendientes = {}


def buscar_o_sugerir_con_pendiente(nombre_buscado, numero, accion, datos):
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


def buscar_en_todo(nombre_buscado):
    """Busca en alumnos Y en representantes, devuelve lista de candidatos."""
    from alumnos import buscar_alumno_por_nombre, buscar_alumno_por_representante
    candidatos = []

    alumnos = buscar_alumno_por_nombre(nombre_buscado)
    for a in alumnos:
        candidatos.append({
            "tipo": "alumno",
            "nombre": a['nombre'],
            "id": a['id'],
            "detalle": "alumno"
        })

    como_rep = buscar_alumno_por_representante(nombre_buscado)
    if como_rep:
        grupos = {}
        for a in como_rep:
            rep = a['representante']
            if rep not in grupos:
                grupos[rep] = []
            grupos[rep].append(a['nombre'])

        for rep_nombre, alumnos_rep in grupos.items():
            candidatos.append({
                "tipo": "representante",
                "nombre": rep_nombre,
                "alumnos": alumnos_rep,
                "detalle": f"representante de {' y '.join(alumnos_rep)}"
            })

    return candidatos


def ejecutar_accion(accion, datos, numero):

    if accion == "aclaracion_alumno":
        if numero not in acciones_pendientes:
            return "No tenía ninguna acción pendiente. ¿Qué querés hacer?"

        pendiente = acciones_pendientes[numero]
        numero_opcion = datos.get("numero_opcion")
        nombre_aclaracion = datos.get("nombre_alumno", "")

        if "candidatos_custom" in pendiente:
            candidatos = pendiente["candidatos_custom"]
            elegido = None
            if numero_opcion and 1 <= numero_opcion <= len(candidatos):
                elegido = candidatos[numero_opcion - 1]
            elif nombre_aclaracion:
                for c in candidatos:
                    if nombre_aclaracion.lower() in c['nombre'].lower():
                        elegido = c
                        break
            if not elegido:
                lista = "\n".join([f"{i+1}. {c['nombre']} — {c['detalle']}" for i, c in enumerate(candidatos)])
                return f"No entendí cuál elegiste:\n{lista}\n\nRespondé con el número."
            del acciones_pendientes[numero]
            nuevos_datos = pendiente["datos"].copy()
            nuevos_datos["candidato_elegido"] = elegido
            return ejecutar_accion(pendiente["accion"], nuevos_datos, numero)

        candidatos = pendiente["candidatos"]
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
        nuevos_datos["nombre_alumno"] = alumno_elegido["nombre"]
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
        existentes = buscar_alumno_por_nombre(datos.get("nombre", ""))
        exactos = [a for a in existentes if a['nombre'].lower() == datos.get("nombre", "").lower()]
        if exactos:
            return (f"⚠️ Ya existe un alumno llamado '{exactos[0]['nombre']}'. "
                    f"Por favor ingresá el apellido o cambiá el nombre del actual con "
                    f"'actualizá el nombre de {exactos[0]['nombre']} a [nombre completo]'.")
        agregar_alumno(
            nombre=datos.get("nombre"),
            pais=datos.get("pais"),
            moneda=datos.get("moneda"),
            metodo_pago=datos.get("metodo_pago"),
            modalidad=datos.get("modalidad"),
            representante=datos.get("representante")
        )
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
        from alumnos import buscar_alumno_por_representante, obtener_alumno_por_id

        meses_es = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        simbolos = {"Dólar": "$", "Libra Esterlina": "£", "Pesos": "$"}

        def formatear_promo(rangos):
            if not rangos:
                return "💰 Sin promo cargada\n"
            texto = "💰 Promo:\n"
            for r in rangos:
                precio = int(r['precio_por_clase']) if r['precio_por_clase'] == int(r['precio_por_clase']) else r['precio_por_clase']
                simbolo = simbolos.get(r['moneda'], r['moneda'])
                texto += f"• {r['clases_desde']}–{r['clases_hasta']} clases: {simbolo}{precio}/h\n"
            return texto

        def mostrar_representante(nombre_rep, hoy):
            nombre_mes = meses_es[hoy.month]
            alumnos_rep = buscar_alumno_por_representante(nombre_rep)
            nombres = " y ".join([a['nombre'] for a in alumnos_rep])
            respuesta = f"👤 {nombre_rep} es representante de {nombres}\n\n"
            a0 = alumnos_rep[0]
            respuesta += f"• Representante: {nombre_rep}\n"
            respuesta += f"• País: {a0['pais'] or '—'}\n"
            respuesta += f"• Idioma: {a0['idioma'] or '—'}\n"
            respuesta += f"• WhatsApp: {a0['whatsapp'] or '—'}\n"
            respuesta += f"• Mail: {a0['mail'] or '—'}\n"
            respuesta += f"• Moneda: {a0['moneda'] or '—'}\n"
            respuesta += f"• Método de pago: {a0['metodo_pago'] or '—'}\n"
            respuesta += f"• Modalidad: {a0['modalidad'] or '—'}\n"
            respuesta += f"• Alias: {a0['alias'] or '—'}\n"
            respuesta += f"• Notas: {a0['notas_recordatorio'] or '—'}\n\n"
            respuesta += formatear_promo(obtener_promo(a0["id"]))
            total_clases = 0
            for a in alumnos_rep:
                proximas = proximas_clases_alumno(a["id"])
                clases_mes = [c for c in proximas if c['fecha'].startswith(f"{hoy.year}-{hoy.month:02d}")]
                dias = ", ".join([c['fecha'].split("-")[2] for c in clases_mes])
                respuesta += f"\n{a['nombre']}\nClases {nombre_mes}: {dias or 'sin clases'}\n"
                total_clases += len(clases_mes)
            respuesta += f"\nTotal clases {nombre_mes}: {total_clases}"
            return respuesta

        def mostrar_alumno(alumno, hoy):
            nombre_mes = meses_es[hoy.month]
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
            respuesta += f"• Notas: {alumno['notas_recordatorio'] or '—'}\n\n"
            respuesta += formatear_promo(obtener_promo(alumno["id"]))
            proximas = proximas_clases_alumno(alumno["id"])
            clases_mes = [c for c in proximas if c['fecha'].startswith(f"{hoy.year}-{hoy.month:02d}")]
            if clases_mes:
                dias = ", ".join([c['fecha'].split("-")[2] for c in clases_mes])
                respuesta += f"\n📅 {nombre_mes}: {dias}"
            else:
                respuesta += f"\n📅 Sin clases este mes"
            return respuesta

        hoy = date.today()
        nombre_buscado = datos.get("nombre_alumno", "")

        if datos.get("candidato_elegido"):
            candidato = datos["candidato_elegido"]
            if candidato["tipo"] == "representante":
                return mostrar_representante(candidato["nombre"], hoy)
            else:
                alumno = obtener_alumno_por_id(candidato["id"])
                return mostrar_alumno(alumno, hoy)

        candidatos = buscar_en_todo(nombre_buscado)

        if not candidatos:
            return f"No encontré ningún alumno ni representante con el nombre '{nombre_buscado}'."

        if len(candidatos) == 1:
            c = candidatos[0]
            if c["tipo"] == "representante":
                return mostrar_representante(c["nombre"], hoy)
            else:
                alumno = obtener_alumno_por_id(c["id"])
                return mostrar_alumno(alumno, hoy)

        acciones_pendientes[numero] = {
            "accion": accion,
            "datos": datos,
            "candidatos_custom": candidatos
        }
        lista = "\n".join([f"{i+1}. {c['nombre']} — {c['detalle']}" for i, c in enumerate(candidatos)])
        return f"Encontré más de uno:\n{lista}\n\n¿A cuál te referís? Respondé con el número."

    elif accion == "actualizar_dato_alumno":
        from alumnos import actualizar_alumno, obtener_alumno_por_id, actualizar_representante

        nombre = datos.get("nombre_alumno", "")
        campo = datos.get("campo")
        nuevo_valor = datos.get("nuevo_valor")

        if not campo or nuevo_valor is None:
            return "Necesito saber qué campo cambiar y el nuevo valor."

        campos_permitidos = ["nombre", "representante", "pais", "idioma", "contacto_preferido",
                             "mail", "whatsapp", "horas_semanales", "dia_habitual", "precio",
                             "moneda", "metodo_pago", "modalidad", "notas_recordatorio", "alias"]
        if campo not in campos_permitidos:
            return f"No puedo editar el campo '{campo}'."

        if datos.get("candidato_elegido"):
            candidato = datos["candidato_elegido"]
            if candidato["tipo"] == "alumno":
                alumno = obtener_alumno_por_id(candidato["id"])
                actualizar_alumno(alumno["id"], campo, nuevo_valor)
                alumno_actualizado = obtener_alumno_por_id(alumno["id"])
                respuesta = f"✅ {candidato['nombre']} actualizado: {campo} = {nuevo_valor}\n\n"
                respuesta += f"• Representante: {alumno_actualizado['representante'] or '—'}\n"
                respuesta += f"• WhatsApp: {alumno_actualizado['whatsapp'] or '—'}\n"
                respuesta += f"• Mail: {alumno_actualizado['mail'] or '—'}\n"
                respuesta += f"• Moneda: {alumno_actualizado['moneda'] or '—'}\n"
                respuesta += f"• Método de pago: {alumno_actualizado['metodo_pago'] or '—'}\n"
                respuesta += f"• Modalidad: {alumno_actualizado['modalidad'] or '—'}"
                return respuesta
            else:
                actualizar_representante(candidato["nombre"], campo, nuevo_valor)
                return f"✅ Representante {candidato['nombre']} actualizado: {campo} = {nuevo_valor}\n(Aplicado a alumnos: {', '.join(candidato['alumnos'])})"

        candidatos = buscar_en_todo(nombre)

        if not candidatos:
            return f"No encontré ningún alumno ni representante con el nombre '{nombre}'."

        if len(candidatos) == 1:
            datos["candidato_elegido"] = candidatos[0]
            return ejecutar_accion(accion, datos, numero)

        acciones_pendientes[numero] = {
            "accion": accion,
            "datos": datos,
            "candidatos_custom": candidatos
        }
        lista = "\n".join([f"{i+1}. {c['nombre']} — {c['detalle']}" for i, c in enumerate(candidatos)])
        return f"Encontré más de uno:\n{lista}\n\n¿A cuál te referís? Respondé con el número."

    elif accion == "borrar_alumno":
        nombre_buscado = datos.get("nombre_alumno", "")

        if datos.get("candidato_elegido"):
            candidato = datos["candidato_elegido"]
            if candidato["tipo"] == "representante":
                from alumnos import buscar_alumno_por_representante
                alumnos_rep = buscar_alumno_por_representante(candidato["nombre"])
                nombres = " y ".join([a['nombre'] for a in alumnos_rep])
                ids = [a['id'] for a in alumnos_rep]
                acciones_pendientes[numero] = {
                    "accion": "confirmar_borrado",
                    "datos": {"alumno_ids": ids, "nombre": candidato["nombre"], "nombres_alumnos": nombres}
                }
                return (f"⚠️ {candidato['nombre']} es representante de {nombres}.\n"
                        f"Borrar a {candidato['nombre']} implica borrar a todas sus alumnas.\n\n"
                        f"¿Cómo querés borrarlo?\n"
                        f"1. Inactivo (se pueden reactivar después)\n"
                        f"2. Borrado definitivo\n"
                        f"3. Cancelar")
            else:
                from alumnos import obtener_alumno_por_id
                alumno = obtener_alumno_por_id(candidato["id"])
                acciones_pendientes[numero] = {
                    "accion": "confirmar_borrado",
                    "datos": {"alumno_ids": [alumno["id"]], "nombre": alumno["nombre"]}
                }
                return (f"⚠️ Estás por borrar a {alumno['nombre']} "
                        f"(representante: {alumno['representante'] or 'sin representante'}).\n\n"
                        f"¿Cómo querés borrarlo?\n"
                        f"1. Inactivo (se puede reactivar después)\n"
                        f"2. Borrado definitivo\n"
                        f"3. Cancelar")

        candidatos = buscar_en_todo(nombre_buscado)

        if not candidatos:
            return f"No encontré ningún alumno ni representante con el nombre '{nombre_buscado}'."

        if len(candidatos) == 1:
            datos["candidato_elegido"] = candidatos[0]
            return ejecutar_accion(accion, datos, numero)

        acciones_pendientes[numero] = {
            "accion": accion,
            "datos": datos,
            "candidatos_custom": candidatos
        }
        lista = "\n".join([f"{i+1}. {c['nombre']} — {c['detalle']}" for i, c in enumerate(candidatos)])
        return f"Encontré más de uno:\n{lista}\n\n¿A cuál te referís? Respondé con el número."

    elif accion == "confirmar_borrado":
        if numero not in acciones_pendientes:
            return "No tenía ningún borrado pendiente."

        pendiente = acciones_pendientes[numero]
        ids = pendiente["datos"].get("alumno_ids", [pendiente["datos"].get("alumno_id")])
        nombre = pendiente["datos"]["nombre"]
        opcion = datos.get("numero_opcion")

        if opcion == 1:
            from alumnos import desactivar_alumno
            for aid in ids:
                desactivar_alumno(aid)
            del acciones_pendientes[numero]
            return f"✅ {nombre} marcado como inactivo. Podés reactivarlo cuando quieras."
        elif opcion == 2:
            from alumnos import borrar_alumno_definitivo
            for aid in ids:
                borrar_alumno_definitivo(aid)
            del acciones_pendientes[numero]
            return f"🗑️ {nombre} borrado definitivamente."
        elif opcion == 3:
            del acciones_pendientes[numero]
            return "Cancelado, no se borró nada."
        else:
            return "Respondé con 1 (inactivo), 2 (borrado definitivo) o 3 (cancelar)."

    elif accion == "actualizar_promo":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        rangos = datos.get("promo", [])
        moneda = datos.get("moneda", alumno["moneda"])
        if not rangos:
            return "Necesito los rangos de la promo. Ejemplo: '1-3 clases $28, 4-5 clases $26'"
        from promociones import reemplazar_promo
        reemplazar_promo(alumno["id"], rangos, moneda)
        detalle = ", ".join([f"{r['desde']}-{r['hasta']} clases ${r['precio']}" for r in rangos])
        return f"✅ Promo de {alumno['nombre']} actualizada: {detalle}"
    
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
            pendiente = acciones_pendientes[numero]
            if pendiente.get("accion") == "confirmar_borrado":
                accion = "confirmar_borrado"
                datos = {"numero_opcion": int(mensaje_entrante.strip())}
            else:
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

    if accion == "aclaracion_alumno" and numero not in acciones_pendientes:
        historiales[numero] = []
    elif accion not in ["no_entiendo"] and numero not in acciones_pendientes:
        historiales[numero] = []
    elif len(historial) > MAXIMO_MENSAJES_HISTORIAL * 2:
        historiales[numero] = []

    respuesta = MessagingResponse()
    respuesta.message(respuesta_texto)
    return str(respuesta)


if __name__ == "__main__":
    scheduler = configurar_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)