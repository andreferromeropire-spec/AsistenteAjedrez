from promociones import calcular_monto, agregar_promo, resumen_cobro_alumno, clases_agendadas_mes
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from datetime import date
import os

from interprete import interpretar_mensaje
from notificaciones import configurar_scheduler
from alumnos import buscar_alumno_por_nombre, agregar_alumno, buscar_alumno_con_sugerencia
from pagos import registrar_pago, quien_debe_este_mes, total_cobrado_en_mes, historial_de_pagos_alumno, historial_reciente_alumno, borrar_pago, pagos_del_mes_alumno
from clases import agendar_clase, cancelar_clase, resumen_clases_alumno_mes, reprogramar_clase
from dashboard_routes import dashboard_bp

from database import crear_tablas
crear_tablas()

load_dotenv()
app = Flask(__name__)

# ── Configuración de features ──────────────────────────────
# True = cancelar redirige a Google Calendar (comportamiento actual)
# Cambiar a False cuando el bot pueda escribir en Calendar directamente
CANCELAR_EN_CALENDAR = True
# ───────────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-2026")
app.register_blueprint(dashboard_bp)

historiales = {}
MAXIMO_MENSAJES_HISTORIAL = 10

# acciones_pendientes persiste en DB para soportar múltiples workers
import json as _json

def _get_pendiente(numero):
    from database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT datos FROM acciones_pendientes WHERE numero = ?", (numero,)
    ).fetchone()
    conn.close()
    return _json.loads(row["datos"]) if row else None

def _set_pendiente(numero, datos):
    from database import get_connection
    from datetime import datetime
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO acciones_pendientes (numero, datos, actualizado) VALUES (?, ?, ?)",
        (numero, _json.dumps(datos, default=str), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def _del_pendiente(numero):
    from database import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM acciones_pendientes WHERE numero = ?", (numero,))
    conn.commit()
    conn.close()

def _in_pendiente(numero):
    return _get_pendiente(numero) is not None

# Clase que imita la interfaz de dict para compatibilidad con el código existente
class AccionesPendientesDB:
    def __getitem__(self, numero):
        v = _get_pendiente(numero)
        if v is None:
            raise KeyError(numero)
        return v
    def __setitem__(self, numero, valor):
        _set_pendiente(numero, valor)
    def __delitem__(self, numero):
        _del_pendiente(numero)
    def __contains__(self, numero):
        return _in_pendiente(numero)
    def get(self, numero, default=None):
        v = _get_pendiente(numero)
        return v if v is not None else default

acciones_pendientes = AccionesPendientesDB()


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

        # Guard: si el pendiente es de ausente_o_cancelar, no tiene candidatos
        if pendiente.get("esperando") == "ausente_o_cancelar":
            _del_pendiente(numero)
            _cid = pendiente['clase_id']
            _nom = pendiente['nombre_alumno']
            _fec = pendiente['fecha']
            _hor = pendiente.get('hora_fmt', '')
            _op = datos.get("numero_opcion")
            if _op == 1:
                _c = __import__('database').get_connection()
                _c.execute('UPDATE clases SET ausente = 1 WHERE id = ?', (_cid,))
                _c.commit()
                _c.close()
                return f'\U0001fa91 {_nom} marcado/a ausente el {_fec}{_hor}. Se cobra igual.'
            elif _op == 2 and not CANCELAR_EN_CALENDAR:
                # v2: cuando el bot pueda escribir en Calendar, habilitar esto
                cancelar_clase(_cid, cancelada_por='profesora')
                return f'\u2705 Clase de {_nom} del {_fec} cancelada. No se cobra.'
            else:
                _set_pendiente(numero, pendiente)
                if CANCELAR_EN_CALENDAR:
                    return f'Respondé 1 para marcar ausente a {_nom} el {_fec}. Para cancelar, hacelo en Google Calendar.'
                return f'Respondé 1 para marcar ausente. Para cancelar la clase, hacelo en Google Calendar.' if CANCELAR_EN_CALENDAR else '1 para ausente (se cobra igual) o 2 para cancelar (no se cobra).'

        if "candidatos" not in pendiente:
            return "No tenía candidatos pendientes. \u00bfQué querés hacer?"

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
        nombre_buscado = datos.get("nombre_alumno", "")

        # ── Detección de representante ──
        # Si el nombre buscado corresponde a un representante, pagamos por todos sus alumnos
        from alumnos import buscar_alumno_por_representante
        alumnos_del_rep = buscar_alumno_por_representante(nombre_buscado) if not datos.get("alumno_id_directo") else []

        if alumnos_del_rep and not datos.get("alumno_id_directo"):
            hoy = date.today()
            mes_pago = datos.get("mes", hoy.month)
            anio_pago = datos.get("anio", hoy.year)
            moneda = datos.get("moneda") or alumnos_del_rep[0]["moneda"] or "Dólar"
            metodo = datos.get("metodo") or alumnos_del_rep[0]["metodo_pago"] or "Wise"

            # 1. Recolectar clases de TODOS los alumnos del representante
            clases_por_alumno = {}
            for alumno_rep in alumnos_del_rep:
                modalidad = (alumno_rep["modalidad"] or "").strip()
                conn = __import__("database").get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, fecha FROM clases
                    WHERE alumno_id = ? AND estado = 'agendada' AND pago_id IS NULL
                    AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                    ORDER BY fecha ASC
                """, (alumno_rep["id"], f"{mes_pago:02d}", str(anio_pago)))
                clases = cursor.fetchall()
                conn.close()
                clases_por_alumno[alumno_rep["id"]] = {
                    "alumno": alumno_rep,
                    "clases": clases
                }

            # 2. Total de clases combinadas para calcular precio combo
            total_clases = sum(len(v["clases"]) for v in clases_por_alumno.values())

            if total_clases == 0:
                rep_nombre = alumnos_del_rep[0]["representante"]
                return f"{rep_nombre} no tiene clases sin pagar este mes."

            # 3. Calcular precio usando el total combinado (así aplica la promo correcta)
            from promociones import calcular_monto as calc_monto
            primer_id = alumnos_del_rep[0]["id"]
            monto_total, precio_unit, moneda_promo = calc_monto(primer_id, total_clases)
            if moneda_promo:
                moneda = moneda_promo
            if monto_total is None:
                rep_nombre = alumnos_del_rep[0]["representante"]
                return f"{rep_nombre} no tiene promo cargada. ¿Cuánto pagó?"

            # 4. Distribuir el monto proporcionalmente entre los alumnos
            # Cada alumno paga precio_unit * sus_clases
            resultados = []
            for alumno_id, info in clases_por_alumno.items():
                alumno_rep = info["alumno"]
                clases = info["clases"]
                if not clases:
                    resultados.append(f"• {alumno_rep['nombre']}: sin clases este mes")
                    continue
                n = len(clases)
                monto_alumno = round(precio_unit * n, 2)
                # Fecha del pago = primer día del mes de las clases
                _fecha_clase = clases[0]["fecha"]  # "2026-01-06"
                _fecha_pago = _fecha_clase[:7] + "-01"  # "2026-01-01"
                pago_id = registrar_pago(alumno_id=alumno_rep["id"], monto=monto_alumno,
                                         moneda=moneda, metodo=metodo, notas=datos.get("notas"),
                                         fecha_pago=_fecha_pago)
                conn = __import__("database").get_connection()
                for c in clases:
                    conn.execute("UPDATE clases SET pago_id = ? WHERE id = ?", (pago_id, c["id"]))
                conn.commit()
                conn.close()
                fechas_str = ", ".join([c["fecha"].split("-")[2] for c in clases])
                resultados.append(f"• {alumno_rep['nombre']}: {monto_alumno} {moneda} ({n} clases, días {fechas_str})")

            rep_nombre = alumnos_del_rep[0]["representante"]
            return (f"✅ Pago registrado para {rep_nombre}:\n"
                    f"{'\n'.join(resultados)}\n"
                    f"• Total: {monto_total} {moneda} ({total_clases} clases × {precio_unit}/clase)")

        # ── Caso normal: buscar por nombre de alumno ──
        alumno, aviso = buscar_o_sugerir_con_pendiente(nombre_buscado, numero, accion, datos)
        if not alumno:
            return aviso

        # Si el bot usó sugerencia fuzzy, verificar que no sea demasiado diferente
        # Esto evita que "Carina" matchee silenciosamente con "Fiona" u otro nombre muy distinto
        if aviso and not datos.get("sugerencia_confirmada"):
            from difflib import SequenceMatcher
            # Comparar contra nombre del alumno Y contra su representante
            sim_nombre = SequenceMatcher(None, nombre_buscado.lower(), alumno["nombre"].lower()).ratio()
            rep = (alumno["representante"] if alumno["representante"] else "").lower()
            sim_rep = SequenceMatcher(None, nombre_buscado.lower(), rep).ratio() if rep else 0
            similitud = max(sim_nombre, sim_rep)
            if similitud < 0.4:
                acciones_pendientes[numero] = {
                    "accion": accion,
                    "datos": {**datos, "sugerencia_confirmada": True, "alumno_id_directo": alumno["id"]},
                    "candidatos": [{"nombre": alumno["nombre"], "id": alumno["id"],
                                    "representante": alumno["representante"]}]
                }
                return (f"No encontré '{nombre_buscado}'. ¿Quisiste decir {alumno['nombre']}?\n"
                        f"Respondé 1 para confirmar o escribí el nombre correcto.")

        hoy = date.today()

        # Si viene marcado como "confirmado", el usuario ya aprobó la diferencia de monto
        if datos.get("confirmado"):
            clases_ids = datos.get("clases_ids", [])
            # Fecha del pago = primer día del mes de las clases que cubre
            _fecha_pago_conf = None
            if clases_ids:
                _conn_f = __import__("database").get_connection()
                _row = _conn_f.execute(
                    "SELECT fecha FROM clases WHERE id = ? LIMIT 1", (clases_ids[0],)
                ).fetchone()
                _conn_f.close()
                if _row:
                    _fecha_pago_conf = _row["fecha"][:7] + "-01"
            pago_id = registrar_pago(
                alumno_id=alumno["id"],
                monto=datos["monto"],
                moneda=datos["moneda"],
                metodo=datos["metodo"],
                notas=datos.get("notas"),
                fecha_pago=_fecha_pago_conf
            )
            if clases_ids:
                conn = __import__("database").get_connection()
                for clase_id in clases_ids:
                    conn.execute("UPDATE clases SET pago_id = ? WHERE id = ?", (pago_id, clase_id))
                conn.commit()
                conn.close()
            fechas = datos.get("fechas_clases", [])
            detalle_fechas = ", ".join([f.split("-")[2] for f in fechas]) if fechas else "—"
            respuesta = (f"✅ Registré el pago de {alumno['nombre']}: "
                        f"{datos['monto']} {datos['moneda']} por {datos['metodo']}."
                        f"\nClases marcadas como pagas: {detalle_fechas}")
            return (aviso + "\n" + respuesta) if aviso else respuesta

        # ── Determinar la moneda y método: usar los del alumno si no se especificaron ──
        moneda = datos.get("moneda") or alumno["moneda"] or "Dólar"
        metodo = datos.get("metodo") or alumno["metodo_pago"] or "Wise"

        # ── Determinar qué clases aplican según la modalidad ──
        cantidad_clases = datos.get("cantidad_clases")
        todas_del_mes = datos.get("todas_del_mes", False)
        mes_pago = datos.get("mes", hoy.month)
        anio_pago = datos.get("anio", hoy.year)
        modalidad = (alumno["modalidad"] or "").strip()

        conn = __import__("database").get_connection()
        cursor = conn.cursor()

        if cantidad_clases:
            # Incluir 'dada' además de 'agendada': una clase ya tomada también se cobra
            # Filtrar por mes para no agarrar clases históricas sin pagar
            cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND estado IN ('agendada', 'dada') AND pago_id IS NULL
                AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                ORDER BY fecha ASC LIMIT ?
            """, (alumno["id"], f"{mes_pago:02d}", str(anio_pago), cantidad_clases))
        elif todas_del_mes or modalidad == "Mensual":
            cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND estado IN ('agendada', 'dada') AND pago_id IS NULL
                AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                ORDER BY fecha ASC
            """, (alumno["id"], f"{mes_pago:02d}", str(anio_pago)))
        elif modalidad == "Semanal":
            # Semanal: una clase por vez, del mes actual por defecto
            # Si especificó fecha, buscar esa clase específica
            fecha_especifica = datos.get("fecha")
            if fecha_especifica:
                cursor.execute("""
                    SELECT id, fecha, hora FROM clases
                    WHERE alumno_id = ? AND pago_id IS NULL
                    AND estado IN ('agendada', 'dada')
                    AND fecha = ?
                    ORDER BY fecha ASC LIMIT 1
                """, (alumno["id"], fecha_especifica))
            else:
                cursor.execute("""
                    SELECT id, fecha, hora FROM clases
                    WHERE alumno_id = ? AND pago_id IS NULL
                    AND estado IN ('agendada', 'dada')
                    AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                    ORDER BY fecha ASC LIMIT 1
                """, (alumno["id"], f"{mes_pago:02d}", str(anio_pago)))
        elif "10" in modalidad or "paquete" in modalidad.lower():
            # Paquete de 10: no filtra por mes, se pagan las próximas 10 desde hoy
            cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND estado IN ('agendada', 'dada') AND pago_id IS NULL
                AND fecha >= ?
                ORDER BY fecha ASC LIMIT 10
            """, (alumno["id"], hoy.isoformat()))
        else:
            cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND estado IN ('agendada', 'dada') AND pago_id IS NULL
                AND strftime('%m', fecha) = ? AND strftime('%Y', fecha) = ?
                ORDER BY fecha ASC
            """, (alumno["id"], f"{mes_pago:02d}", str(anio_pago)))

        clases = cursor.fetchall()
        conn.close()

        if not clases:
            respuesta = f"No encontré clases sin pagar para {alumno['nombre']}."
            return (aviso + "\n" + respuesta) if aviso else respuesta

        clases_ids = [c["id"] for c in clases]
        fechas_clases = [c["fecha"] for c in clases]
        n_clases = len(clases)

        # ── Calcular monto esperado según la promo ──
        from promociones import calcular_monto as calc_monto
        monto_esperado, precio_unitario, moneda_promo = calc_monto(alumno["id"], n_clases)
        # Si el usuario especificó una moneda, usarla. Si no, usar la de la promo.
        if moneda_promo and not datos.get("moneda"):
            moneda = moneda_promo

        # Normalizar monto: si viene vacío o None, tratarlo como None
        monto_raw = datos.get("monto")
        monto_pagado = float(monto_raw) if monto_raw not in (None, "", 0) else None

        # Solo comparar montos si la moneda es la misma que la promo
        moneda_pago_raw = datos.get("moneda")  # lo que dijo el usuario (puede ser None)
        monedas_distintas = moneda_pago_raw and moneda_promo and moneda_pago_raw != moneda_promo

        # Siempre confirmar si: montos distintos O monedas distintas
        necesita_confirmacion = False
        if monto_pagado is not None and monto_esperado is not None:
            diferencia = abs(float(monto_pagado) - float(monto_esperado))
            if diferencia > 0.01 or monedas_distintas:
                necesita_confirmacion = True

        if necesita_confirmacion:
            fechas_str = ", ".join([f.split("-")[2] for f in fechas_clases])
            acciones_pendientes[numero] = {
                "accion": "registrar_pago",
                "datos": {
                    **datos,
                    "confirmado": True,
                    "monto": monto_pagado,
                    "moneda": moneda,
                    "metodo": metodo,
                    "clases_ids": clases_ids,
                    "fechas_clases": fechas_clases,
                    "nombre_alumno": alumno["nombre"],
                    "alumno_id_directo": alumno["id"]
                }
            }
            if monedas_distintas:
                return (
                    f"⚠️ {alumno['nombre']} tiene {n_clases} clases (días {fechas_str})\n"
                    f"• Precio habitual: {monto_esperado} {moneda_promo} ({precio_unitario}/clase)\n"
                    f"• Vas a registrar: {monto_pagado} {moneda} (moneda diferente)\n\n"
                    f"¿Confirmás? Respondé 1 para guardar o 2 para cancelar."
                )
            else:
                return (
                    f"⚠️ {alumno['nombre']} tiene {n_clases} clases (días {fechas_str})\n"
                    f"• Precio esperado: {monto_esperado} {moneda} ({precio_unitario}/clase)\n"
                    f"• Registraste: {monto_pagado} {moneda}\n\n"
                    f"¿Guardamos {monto_pagado} igual? Respondé 1 para confirmar o 2 para reingresar."
                )

        monto_final = monto_pagado if monto_pagado is not None else monto_esperado

        if monto_final is None:
            respuesta = (f"{alumno['nombre']} tiene {n_clases} clases agendadas pero "
                        f"no tiene promo cargada y no especificaste el monto. ¿Cuánto pagó?")
            return (aviso + "\n" + respuesta) if aviso else respuesta

        # ── Registrar el pago y marcar clases ──
        # Fecha del pago = primer día del mes de las clases que cubre
        _fecha_pago_n = (fechas_clases[0][:7] + "-01") if fechas_clases else None
        pago_id = registrar_pago(alumno_id=alumno["id"], monto=monto_final,
                                  moneda=moneda, metodo=metodo, notas=datos.get("notas"),
                                  fecha_pago=_fecha_pago_n)

        conn = __import__("database").get_connection()
        for clase_id in clases_ids:
            conn.execute("UPDATE clases SET pago_id = ? WHERE id = ?", (pago_id, clase_id))
        conn.commit()
        conn.close()

        fechas_str = ", ".join([f.split("-")[2] for f in fechas_clases])
        respuesta = (f"✅ Registré el pago de {alumno['nombre']}:\n"
                    f"• {n_clases} clases (días {fechas_str})\n"
                    f"• {monto_final} {moneda} por {metodo}")
        if precio_unitario:
            respuesta += f"\n• {precio_unitario}/clase"
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
        nombre = alumno['nombre'] if alumno else datos.get("nombre_alumno", "el alumno")
        return (
            f"Para cancelar la clase de {nombre}, hacelo directamente en Google Calendar. "
            f"En la próxima sincronización, el sistema lo va a reflejar automáticamente. \U0001f4c5"
        )

    elif accion == "reactivar_clase":
        # v1: Google Calendar es la fuente de verdad — modificar la clase directamente ahí
        # v2: cuando el bot tenga escritura en Calendar, descomentar el bloque de abajo
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        nombre = alumno['nombre'] if alumno else datos.get("nombre_alumno", "la clase")
        return (
            f"Para reactivar la clase de {nombre}, modificala directamente en Google Calendar. "
            f"En la próxima sincronización se va a reflejar automáticamente. 📅"
        )
        # ── v2 (descomentar cuando haya escritura en Calendar) ──────────
        # if not alumno: return aviso
        # fecha_especifica = datos.get("fecha")
        # conn = __import__('database').get_connection()
        # clase = conn.execute(
        #     "SELECT id, fecha FROM clases WHERE alumno_id = ? AND fecha = ? AND estado LIKE 'cancelada%'",
        #     (alumno["id"], fecha_especifica)
        # ).fetchone() if fecha_especifica else conn.execute(
        #     "SELECT id, fecha FROM clases WHERE alumno_id = ? AND estado LIKE 'cancelada%' ORDER BY fecha DESC LIMIT 1",
        #     (alumno["id"],)
        # ).fetchone()
        # if not clase: conn.close(); return f"No encontré clase cancelada de {alumno['nombre']}."
        # estado_nuevo = 'dada' if clase['fecha'] < hoy.isoformat() else 'agendada'
        # conn.execute("UPDATE clases SET estado = ? WHERE id = ?", (estado_nuevo, clase['id']))
        # conn.commit(); conn.close()
        # return f"✅ Clase de {alumno['nombre']} del {clase['fecha']} reactivada como {estado_nuevo}."
        # ────────────────────────────────────────────────────────────────

    elif accion == "marcar_ausente":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        fecha_especifica = datos.get("fecha")
        if fecha_especifica:
            clase = cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND fecha = ?
                AND estado IN ('dada', 'agendada')
            """, (alumno["id"], fecha_especifica)).fetchone()
            if not clase:
                sug = cursor.execute("""
                    SELECT id, fecha, hora FROM clases
                    WHERE alumno_id = ? AND fecha <= date('now')
                    AND estado IN ('dada','agendada')
                    ORDER BY fecha DESC LIMIT 1
                """, (alumno["id"],)).fetchone()
                conn.close()
                if sug:
                    hora_sug = f" a las {sug['hora']}" if sug['hora'] else ""
                    return f"No encontré una clase de {alumno['nombre']} el {fecha_especifica}. La última que tengo es del {sug['fecha']}{hora_sug}. ¿Es esa? Si es, reenvía con esa fecha."
                return f"No encontré ninguna clase de {alumno['nombre']} el {fecha_especifica}."
        else:
            clase = cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND fecha < date('now')
                AND estado IN ('dada', 'agendada')
                ORDER BY fecha DESC, hora DESC LIMIT 1
            """, (alumno["id"],)).fetchone()
            if not clase:
                conn.close()
                return f"No encontré ninguna clase pasada de {alumno['nombre']}."
        conn.close()
        fecha_fmt = clase["fecha"]
        hora_fmt = f" a las {clase['hora']}" if clase["hora"] else ""
        _set_pendiente(numero, {
            'esperando': 'ausente_o_cancelar',
            'clase_id': clase['id'],
            'nombre_alumno': alumno['nombre'],
            'fecha': fecha_fmt,
            'hora_fmt': hora_fmt
        })
        if CANCELAR_EN_CALENDAR:
            return (
                f"🪑 {alumno['nombre']} — clase del {fecha_fmt}{hora_fmt}.\n"
                f"¿Estuvo ausente? Respondé 1 para confirmar (se cobra igual).\n"
                f"Si querés cancelarla, hacelo en Google Calendar y se va a reflejar en la próxima sincronización."
            )
        else:
            return (
                f"🪑 {alumno['nombre']} — clase del {fecha_fmt}{hora_fmt}.\n"
                f"¿Cómo la registramos?\n"
                f"1 - Ausente (se cobra igual)\n"
                f"2 - Cancelada (no se cobra)"
            )

    elif accion == "desmarcar_ausente":
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        if not alumno:
            return aviso
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        fecha_especifica = datos.get("fecha")
        if fecha_especifica:
            clase = cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND fecha = ? AND ausente = 1
            """, (alumno["id"], fecha_especifica)).fetchone()
            if not clase:
                conn.close()
                return f"No encontré ninguna ausencia de {alumno['nombre']} el {fecha_especifica}."
        else:
            clase = cursor.execute("""
                SELECT id, fecha, hora FROM clases
                WHERE alumno_id = ? AND ausente = 1
                ORDER BY fecha DESC LIMIT 1
            """, (alumno["id"],)).fetchone()
            if not clase:
                conn.close()
                return f"No encontré ninguna ausencia registrada de {alumno['nombre']}."
        cursor.execute("UPDATE clases SET ausente = 0 WHERE id = ?", (clase["id"],))
        conn.commit()
        conn.close()
        fecha_fmt = clase["fecha"]
        hora_fmt = f" a las {clase['hora']}" if clase["hora"] else ""
        respuesta = f"✅ Listo, {alumno['nombre']} figura como presente en la clase del {fecha_fmt}{hora_fmt}."
        return (aviso + "\n" + respuesta) if aviso else respuesta


    elif accion == "reprogramar_clase":
        # v1: Google Calendar es la fuente de verdad — reprogramar directamente ahí
        # v2: cuando el bot tenga escritura en Calendar, descomentar el bloque de abajo
        alumno, aviso = buscar_o_sugerir_con_pendiente(datos.get("nombre_alumno", ""), numero, accion, datos)
        nombre = alumno['nombre'] if alumno else datos.get("nombre_alumno", "la clase")
        return (
            f"Para reprogramar la clase de {nombre}, modificala directamente en Google Calendar. "
            f"En la próxima sincronización se va a reflejar automáticamente. 📅"
        )
        # ── v2 (descomentar cuando haya escritura en Calendar) ──────────
        # if not alumno: return aviso
        # fecha_original = datos.get("fecha_original")
        # nueva_fecha = datos.get("nueva_fecha")
        # nueva_hora = datos.get("nueva_hora")
        # if not fecha_original or not nueva_fecha:
        #     return "Necesito la fecha original y la nueva fecha para reprogramar."
        # conn = __import__('database').get_connection()
        # clase = conn.execute(
        #     "SELECT id FROM clases WHERE alumno_id = ? AND fecha = ? AND estado = 'agendada'",
        #     (alumno["id"], fecha_original)
        # ).fetchone()
        # conn.close()
        # if not clase: return f"No encontré clase agendada de {alumno['nombre']} el {fecha_original}."
        # reprogramar_clase(clase["id"], nueva_fecha, nueva_hora)
        # respuesta = f"✅ Reprogramada del {fecha_original} al {nueva_fecha}"
        # if nueva_hora: respuesta += f" a las {nueva_hora}"
        # return (aviso + "\n" + respuesta + ".") if aviso else respuesta + "."
        # ────────────────────────────────────────────────────────────────

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
        nombre_buscado = datos.get("nombre_alumno", "")
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)

        # Detectar si el nombre buscado es un representante con varios alumnos
        from alumnos import buscar_alumno_por_representante, buscar_alumno_con_sugerencia
        alumnos_rep = buscar_alumno_por_representante(nombre_buscado) if not datos.get("alumno_id_directo") else []

        if alumnos_rep and len(alumnos_rep) > 1:
            # Mostrar clases de todos los alumnos del representante, mezcladas cronológicamente
            conn = __import__('database').get_connection()
            cursor = conn.cursor()
            filas = []
            for a in alumnos_rep:
                cursor.execute("""
                    SELECT fecha, hora, pago_id, estado, ausente FROM clases
                    WHERE alumno_id = ?
                    AND strftime('%m', fecha) = ?
                    AND strftime('%Y', fecha) = ?
                    AND estado IN ('agendada', 'dada')
                """, (a["id"], f"{mes:02d}", str(anio)))
                for c in cursor.fetchall():
                    filas.append({**dict(c), "nombre_alumno": a["nombre"]})
            conn.close()
            if not filas:
                return f"{nombre_buscado} no tiene clases en {mes}/{anio}."
            filas.sort(key=lambda x: (x["fecha"], x["hora"] or ""))
            rep_nombre = alumnos_rep[0]["representante"]
            respuesta = f"📅 Clases de {rep_nombre} en {mes}/{anio}:\n"
            pagadas = 0
            ausentes = 0
            for c in filas:
                hora = f" a las {c['hora']}" if c['hora'] else ""
                paga = " ✅" if c['pago_id'] else ""
                if c['pago_id']:
                    pagadas += 1
                if c['ausente']:
                    ausentes += 1
                    emoji = "🪑"
                elif c['estado'] == 'dada':
                    emoji = "🟢"
                else:
                    emoji = "🔵"
                respuesta += f"• {emoji} {c['fecha']}{hora} {c['nombre_alumno']}{paga}\n"
            resumen = f"Total: {len(filas)} clases ({pagadas} pagas, {len(filas)-pagadas} pendientes)"
            if ausentes:
                resumen += f" · {ausentes} ausente(s)"
            respuesta += f"\n{resumen}"
            return respuesta

        # Caso normal: un solo alumno
        alumno, aviso = buscar_o_sugerir_con_pendiente(nombre_buscado, numero, accion, datos)
        if not alumno:
            # Último intento: fuzzy sobre representantes
            alumnos_fuzzy, _ = buscar_alumno_con_sugerencia(nombre_buscado)
            if alumnos_fuzzy:
                rep = alumnos_fuzzy[0].get("representante")
                if rep:
                    alumnos_rep2 = buscar_alumno_por_representante(rep)
                    if len(alumnos_rep2) > 1:
                        datos["nombre_alumno"] = rep
                        return ejecutar_accion(accion, datos, numero)
            return aviso
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fecha, hora, pago_id, estado, ausente FROM clases
            WHERE alumno_id = ?
            AND strftime('%m', fecha) = ?
            AND strftime('%Y', fecha) = ?
            AND estado IN ('agendada', 'dada')
            ORDER BY fecha ASC
        """, (alumno["id"], f"{mes:02d}", str(anio)))
        clases = cursor.fetchall()
        conn.close()
        if not clases:
            return f"{alumno['nombre']} no tiene clases en {mes}/{anio}."
        respuesta = f"📅 Clases de {alumno['nombre']} en {mes}/{anio}:\n"
        pagadas = 0
        ausentes = 0
        for clase in clases:
            hora = f" a las {clase['hora']}" if clase['hora'] else ""
            paga = " ✅" if clase['pago_id'] else ""
            if clase['pago_id']:
                pagadas += 1
            if clase['ausente']:
                ausentes += 1
                emoji = "🪑"
            elif clase['estado'] == 'dada':
                emoji = "🟢"
            else:
                emoji = "🔵"
            respuesta += f"• {emoji} {clase['fecha']}{hora}{paga}\n"
        resumen = f"Total: {len(clases)} clases ({pagadas} pagas, {len(clases)-pagadas} pendientes)"
        if ausentes:
            resumen += f" · {ausentes} ausente(s)"
        respuesta += f"\n{resumen}"
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
        simbolos = {"Dólar": "$", "Libra Esterlina": "£", "ARS$": "AR$", "Pesos": "AR$"}

        def formatear_promo(rangos):
            if not rangos:
                return "💰 Sin promo cargada\n"
            texto = "💰 Promo:\n"
            for r in rangos:
                precio_raw = r['precio_por_clase']
                precio_int = int(precio_raw) if precio_raw == int(precio_raw) else precio_raw
                precio_fmt = f"{precio_int:,}".replace(",", ".")
                simbolo = simbolos.get(r['moneda'], r['moneda'])
                texto += f"• {r['clases_desde']}–{r['clases_hasta']} clases: {simbolo} {precio_fmt}/clase\n"
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
    
    elif accion == "borrar_pago":
        nombre_buscado = datos.get("nombre_alumno", "")
        alumno, aviso = buscar_o_sugerir_con_pendiente(nombre_buscado, numero, accion, datos)
        if not alumno:
            return aviso

        # Verificar que la sugerencia fuzzy no sea demasiado diferente al nombre buscado
        if aviso and not datos.get("sugerencia_confirmada") and not datos.get("pago_id_a_borrar"):
            from difflib import SequenceMatcher
            sim_nombre = SequenceMatcher(None, nombre_buscado.lower(), alumno["nombre"].lower()).ratio()
            rep2 = (alumno["representante"] if alumno["representante"] else "").lower()
            sim_rep2 = SequenceMatcher(None, nombre_buscado.lower(), rep2).ratio() if rep2 else 0
            similitud = max(sim_nombre, sim_rep2)
            if similitud < 0.4:
                acciones_pendientes[numero] = {
                    "accion": accion,
                    "datos": {**datos, "sugerencia_confirmada": True, "alumno_id_directo": alumno["id"]},
                    "candidatos": [{"nombre": alumno["nombre"], "id": alumno["id"],
                                    "representante": alumno["representante"]}]
                }
                return (f"No encontré '{nombre_buscado}'. ¿Quisiste decir {alumno['nombre']}?\n"
                        f"Respondé 1 para confirmar o escribí el nombre correcto.")

        # Si viene con pago_id elegido y confirmación, ejecutamos el borrado
        if datos.get("pago_id_a_borrar") and datos.get("confirmado"):
            pago_id = datos["pago_id_a_borrar"]
            ok, resultado = borrar_pago(pago_id)
            del acciones_pendientes[numero]
            if ok:
                n = resultado  # cantidad de clases desmarcadas
                msg = f"🗑️ Pago borrado."
                if n > 0:
                    msg += f" {n} clase{'s' if n > 1 else ''} quedaron marcadas como no pagas."
                return msg
            else:
                return f"❌ {resultado}"

        # Si viene con pago_id elegido pero sin confirmar, pedimos confirmación
        if datos.get("pago_id_a_borrar"):
            pago_elegido = datos.get("detalle_pago_elegido", {})
            monto = pago_elegido.get("monto", "—")
            moneda = pago_elegido.get("moneda", "—")
            metodo = pago_elegido.get("metodo", "—")
            # Buscar clases asociadas para mostrar en confirmación
            conn_conf = __import__("database").get_connection()
            clases_conf = conn_conf.execute(
                "SELECT fecha FROM clases WHERE pago_id = ? ORDER BY fecha ASC",
                (pago_elegido.get("id"),)
            ).fetchall()
            conn_conf.close()
            if clases_conf:
                dias = ", ".join([c["fecha"].split("-")[2] for c in clases_conf])
                n_cl = len(clases_conf)
                dia_palabra = "día" if n_cl == 1 else "días"
                detalle_clases = f"{n_cl} clase{'s' if n_cl > 1 else ''} — {dia_palabra} {dias}"
            else:
                detalle_clases = "sin clases asociadas"
            acciones_pendientes[numero] = {
                "accion": "borrar_pago",
                "datos": {
                    **datos,
                    "confirmado": True,
                    "nombre_alumno": alumno["nombre"],
                    "alumno_id_directo": alumno["id"]
                }
            }
            return (
                f"⚠️ ¿Confirmás que querés borrar este pago de {alumno['nombre']}?\n"
                f"• {monto} {moneda} por {metodo}\n"
                f"• {detalle_clases}\n\n"
                f"Respondé 1 para confirmar o 2 para cancelar."
            )

        # Primera vez: mostrar todos los pagos del mes pedido (o mes actual)
        from datetime import date as _date_bp
        _hoy = _date_bp.today()
        mes_pedido = datos.get("mes")
        anio_pedido = datos.get("anio")
        pagos = pagos_del_mes_alumno(alumno["id"], mes=mes_pedido, anio=anio_pedido)
        mes_mostrar = mes_pedido or _hoy.month
        anio_mostrar = anio_pedido or _hoy.year
        meses_es = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        if not pagos:
            return f"{alumno['nombre']} no tiene pagos registrados en {meses_es[mes_mostrar]} {anio_mostrar}."

        simbolos = {"Dólar": "$", "Libra Esterlina": "£", "ARS$": "AR$", "Pesos": "AR$"}
        lista = []
        conn_h = __import__("database").get_connection()
        for i, p in enumerate(pagos):
            sim = simbolos.get(p["moneda"], "")
            clases_pago = conn_h.execute(
                "SELECT fecha FROM clases WHERE pago_id = ? ORDER BY fecha ASC",
                (p["id"],)
            ).fetchall()
            if clases_pago:
                dias = ", ".join([c["fecha"].split("-")[2] for c in clases_pago])
                mes_año = clases_pago[0]["fecha"][:7]
                palabra_dia = "días" if len(clases_pago) > 1 else "día"
                detalle_clases = f"{len(clases_pago)} clase{'s' if len(clases_pago)>1 else ''} del {mes_año} ({palabra_dia} {dias})"
            else:
                detalle_clases = f"registrado {p['fecha']}"
            lista.append(f"{i+1}. {sim}{p['monto']} {p['moneda']} — {detalle_clases}")
        conn_h.close()

        acciones_pendientes[numero] = {
            "accion": "borrar_pago",
            "datos": {
                "nombre_alumno": alumno["nombre"],
                "alumno_id_directo": alumno["id"]
            },
            "pagos_candidatos": [dict(p) for p in pagos]
        }
        texto = f"Pagos de {alumno['nombre']} en {meses_es[mes_mostrar]} {anio_mostrar}:\n" + "\n".join(lista)
        texto += "\n0. Cancelar"
        texto += "\n\n¿Cuál querés borrar? Podés responder:\n• Un número: \'1\'\n• Varios: \'1,2\' o \'1 2\'\n• Todos: \'T\' o \'todos\'"
        return (aviso + "\n" + texto) if aviso else texto

    elif accion == "ignorar_evento":
        titulo = datos.get("titulo", "")
        if not titulo:
            return "No entendi que evento queresIgnorar. Decime el titulo exacto."
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        key = f"titulo_{titulo}"
        cursor.execute(
            "INSERT OR IGNORE INTO eventos_ignorados (google_event_id, titulo, fecha_ignorado) VALUES (?, ?, ?)",
            (key, titulo, date.today().isoformat())
        )
        conn.commit()
        conn.close()
        return f"Listo, voy a ignorar ese evento en futuras sincronizaciones."

    elif accion == "sincronizar_calendario":
        from sincronizacion import sincronizacion_diaria
        hoy = date.today()
        mes = datos.get("mes", hoy.month)
        anio = datos.get("anio", hoy.year)
        resultado = sincronizacion_diaria(mes, anio, enviar_whatsapp=False)
        nuevos = resultado["nuevos"]
        cancelados = resultado["cancelados"]
        modificados = resultado["modificados"]
        no_id = resultado["no_identificados"]
        if nuevos == 0 and cancelados == 0 and modificados == 0:
            return f"✅ Sin cambios en {mes}/{anio} — el calendario ya estaba actualizado."
        respuesta = f"✅ Sincronización {mes}/{anio}:\n"
        if nuevos: respuesta += f"• {nuevos} clase(s) nueva(s)\n"
        if cancelados: respuesta += f"• {cancelados} clase(s) cancelada(s)\n"
        if modificados: respuesta += f"• {modificados} clase(s) modificada(s)\n"
        if no_id:
            lista = "\n".join([f"  {e}" for e in no_id])
            respuesta += f"\n⚠️ Eventos sin identificar:\n{lista}"
        return respuesta.strip()

    elif accion == "no_entiendo":
        return "No entendí bien. Podés decirme cosas como:\n• 'pagó Lucas 20000 pesos'\n• 'di clase con Henry'\n• 'quién debe este mes'\n• '¿cuánto gané en febrero?'"

    else:
        return "No entendí esa acción."



def procesar_mensaje(mensaje_entrante, numero, historial=None):
    """
    Lógica compartida entre el webhook de WhatsApp y el chat del dashboard.
    Recibe el mensaje y el identificador del usuario, devuelve el texto de respuesta.
    """
    if historial is None:
        historial = []

    accion = "no_entiendo"
    datos = {}

    # Caso especial: respuesta 1/2 a pregunta ausente vs cancelar
    if numero in acciones_pendientes:
        _p = _get_pendiente(numero)
        if _p and _p.get('esperando') == 'ausente_o_cancelar':
            _del_pendiente(numero)
            _cid = _p['clase_id']
            _nom = _p['nombre_alumno']
            _fec = _p['fecha']
            _hor = _p.get('hora_fmt', '')
            _t = mensaje_entrante.strip().lower()
            if _t == '1' or 'ausent' in _t or 'falt' in _t or 'no asistio' in _t:
                _c = __import__('database').get_connection()
                _c.execute('UPDATE clases SET ausente = 1 WHERE id = ?', (_cid,))
                _c.commit()
                _c.close()
                return f'🪑 {_nom} marcado/a ausente el {_fec}{_hor}. Se cobra igual.'
            elif _t == '2' or 'cancel' in _t:
                cancelar_clase(_cid, cancelada_por='profesora')
                return f'✅ Clase de {_nom} del {_fec} cancelada. No se cobra.'
            else:
                _set_pendiente(numero, _p)
                return f'Respondé 1 para marcar ausente. Para cancelar la clase, hacelo en Google Calendar.' if CANCELAR_EN_CALENDAR else '1 para ausente (se cobra igual) o 2 para cancelar (no se cobra).'

    def _es_respuesta_pendiente(msg, pendiente):
        """True si el mensaje es una respuesta válida a la acción pendiente."""
        msg = msg.strip().lower()
        if msg.isdigit():
            return True
        # Selección múltiple solo para borrar_pago
        if pendiente and pendiente.get("accion") == "borrar_pago":
            if msg in ("t", "todos", "all", "0", "cancelar"):
                return True
            import re as _re2
            partes = _re2.split(r"[,\s]+", msg)
            if all(p.isdigit() for p in partes if p):
                return True
        return False

    if numero in acciones_pendientes and _es_respuesta_pendiente(mensaje_entrante, acciones_pendientes[numero]):
        pendiente = acciones_pendientes[numero]
        opcion = int(mensaje_entrante.strip())

        # Si el pendiente es de ausente_o_cancelar, procesarlo aquí también como fallback
        if pendiente.get("esperando") == "ausente_o_cancelar":
            _del_pendiente(numero)
            _cid = pendiente['clase_id']
            _nom = pendiente['nombre_alumno']
            _fec = pendiente['fecha']
            _hor = pendiente.get('hora_fmt', '')
            if opcion == 1:
                _c = __import__('database').get_connection()
                _c.execute('UPDATE clases SET ausente = 1 WHERE id = ?', (_cid,))
                _c.commit()
                _c.close()
                return f'🪑 {_nom} marcado/a ausente el {_fec}{_hor}. Se cobra igual.'
            elif opcion == 2:
                cancelar_clase(_cid, cancelada_por='profesora')
                return f'✅ Clase de {_nom} del {_fec} cancelada. No se cobra.'
            else:
                _set_pendiente(numero, pendiente)
                return f'Respondé 1 para marcar ausente. Para cancelar la clase, hacelo en Google Calendar.' if CANCELAR_EN_CALENDAR else '1 para ausente (se cobra igual) o 2 para cancelar (no se cobra).'

        if pendiente.get("accion") == "confirmar_borrado":
            accion = "confirmar_borrado"
            datos = {"numero_opcion": opcion}

        elif pendiente.get("accion") == "registrar_pago" and pendiente["datos"].get("confirmado"):
            if opcion == 1:
                accion = "registrar_pago"
                datos = pendiente["datos"]
                del acciones_pendientes[numero]
            elif opcion == 2:
                del acciones_pendientes[numero]
                return "Cancelado. Mandame el pago de nuevo con el monto correcto."
            else:
                return "Responde 1 para confirmar o 2 para reingresar el monto."

        elif pendiente.get("accion") == "borrar_pago":
            if "pagos_candidatos" in pendiente:
                candidatos = pendiente["pagos_candidatos"]
                txt = mensaje_entrante.strip().lower()

                # Cancelar
                if txt in ("0", "cancelar", "cancel"):
                    del acciones_pendientes[numero]
                    return "Cancelado, no se borró nada."

                # Parsear selección: "T"/"todos", "1,2", "1 2 3", o número solo
                if txt in ("t", "todos", "all"):
                    indices = list(range(len(candidatos)))
                else:
                    import re as _re
                    partes = _re.split(r"[,\s]+", txt)
                    indices = []
                    for p in partes:
                        if p.isdigit():
                            n = int(p) - 1
                            if 0 <= n < len(candidatos):
                                indices.append(n)
                    if not indices:
                        return f"No entendí. Respondé con números (ej: \'1,2\'), \'T\' para todos, o \'0\' para cancelar."

                elegidos = [candidatos[i] for i in indices]
                simbolos = {"Dólar": "$", "Libra Esterlina": "£", "ARS$": "AR$", "Pesos": "AR$"}
                resumen = []
                for e in elegidos:
                    sim = simbolos.get(e.get("moneda",""), "")
                    resumen.append(f"• {sim}{e.get('monto','')} {e.get('moneda','')} — {e.get('fecha','')}")

                # Guardar ids a borrar y pedir confirmación
                acciones_pendientes[numero] = {
                    "accion": "borrar_pago",
                    "datos": {
                        **pendiente["datos"],
                        "pago_ids_a_borrar": [e["id"] for e in elegidos],
                        "confirmado": False
                    }
                }
                n = len(elegidos)
                return (
                    f"⚠️ ¿Confirmás que querés borrar {n} pago{'s' if n > 1 else ''} de {pendiente['datos']['nombre_alumno']}?\n"
                    + "\n".join(resumen)
                    + "\n\nRespondé 1 para confirmar o 2 para cancelar."
                )

            elif pendiente["datos"].get("confirmado") or pendiente["datos"].get("pago_id_a_borrar") or pendiente["datos"].get("pago_ids_a_borrar"):
                if opcion == 2:
                    del acciones_pendientes[numero]
                    return "Cancelado, no se borró nada."
                elif opcion == 1:
                    d = pendiente["datos"]
                    ids = d.get("pago_ids_a_borrar") or ([d["pago_id_a_borrar"]] if d.get("pago_id_a_borrar") else [])
                    if not ids:
                        del acciones_pendientes[numero]
                        return "No había pagos para borrar."
                    del acciones_pendientes[numero]
                    total_clases = 0
                    errores = []
                    for pid in ids:
                        ok, resultado = borrar_pago(pid)
                        if ok:
                            total_clases += resultado
                        else:
                            errores.append(str(resultado))
                    n = len(ids)
                    msg = f"🗑️ {n} pago{'s' if n > 1 else ''} borrado{'s' if n > 1 else ''}."
                    if total_clases > 0:
                        msg += f" {total_clases} clase{'s' if total_clases > 1 else ''} quedaron como no pagas."
                    if errores:
                        msg += f" Errores: {', '.join(errores)}"
                    return msg
                else:
                    return "Respondé 1 para confirmar o 2 para cancelar."
            else:
                accion = "aclaracion_alumno"
                datos = {"numero_opcion": opcion}

        else:
            accion = "aclaracion_alumno"
            datos = {"numero_opcion": opcion}

    else:
        if numero in acciones_pendientes and not mensaje_entrante.strip().isdigit():
            del acciones_pendientes[numero]
        interpretado = interpretar_mensaje(mensaje_entrante, historial)
        accion = interpretado.get("accion", "no_entiendo")
        datos = interpretado.get("datos", {})
        if accion == "aclaracion_alumno" and numero not in acciones_pendientes:
            accion = "no_entiendo"
            datos = {}

    return ejecutar_accion(accion, datos, numero)


@app.route("/webhook", methods=["POST"])
def webhook():
    mensaje_entrante = request.form.get("Body", "").strip()
    numero = request.form.get("From", "desconocido")

    if numero not in historiales:
        historiales[numero] = []
    historial = historiales[numero]

    try:
        respuesta_texto = procesar_mensaje(mensaje_entrante, numero, historial)
    except Exception as e:
        respuesta_texto = f"Ocurrió un error: {str(e)}"

    historial.append({"role": "user", "content": mensaje_entrante})
    historial.append({"role": "assistant", "content": respuesta_texto})
    if len(historial) > MAXIMO_MENSAJES_HISTORIAL * 2:
        historiales[numero] = []

    respuesta = MessagingResponse()
    respuesta.message(respuesta_texto)
    return str(respuesta)

@app.route("/diagnostico", methods=["GET"])
def diagnostico():
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM alumnos")
    alumnos = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM clases")
    clases = cursor.fetchone()['total']
    conn.close()
    return f"Alumnos: {alumnos}, Clases: {clases}"

@app.route("/setup", methods=["GET"])
def setup():
    from database import crear_tablas
    crear_tablas()
    return "Tablas creadas"

@app.route("/debug_alumno/<nombre>", methods=["GET"])
def debug_alumno(nombre):
    from database import get_connection
    import json
    conn = get_connection()
    alumno = conn.execute("SELECT id FROM alumnos WHERE nombre LIKE ?", (f"%{nombre}%",)).fetchone()
    if not alumno:
        return f"No encontré alumno con nombre '{nombre}'"
    clases = conn.execute(
        "SELECT id, fecha, hora, estado, pago_id, ausente FROM clases WHERE alumno_id = ? ORDER BY fecha DESC LIMIT 30",
        (alumno["id"],)
    ).fetchall()
    conn.close()
    rows = [dict(c) for c in clases]
    return "<pre>" + json.dumps(rows, indent=2, default=str) + "</pre>"

@app.route("/migrar_moneda", methods=["GET"])
def migrar_moneda():
    from database import get_connection
    conn = get_connection()
    a = conn.execute("UPDATE alumnos SET moneda = 'ARS$' WHERE moneda = 'Pesos'").rowcount
    p = conn.execute("UPDATE pagos SET moneda = 'ARS$' WHERE moneda = 'Pesos'").rowcount
    pr = conn.execute("UPDATE promociones SET moneda = 'ARS$' WHERE moneda = 'Pesos'").rowcount
    conn.commit()
    conn.close()
    return f"Migrado: {a} alumnos, {p} pagos, {pr} promociones"

@app.route("/sincronizar_alumnos", methods=["GET"])
def sincronizar_alumnos_endpoint():
    from sincronizar_sheets import sincronizar_alumnos_desde_sheets
    sincronizar_alumnos_desde_sheets()
    return "Alumnos sincronizados desde Google Sheets"

@app.route("/sincronizar_calendario")
def sincronizar_calendario_endpoint():
    from calendar_google import sincronizar_mes
    from datetime import date
    hoy = date.today()
    resultado = sincronizar_mes(hoy.month, hoy.year)
    return f"✅ {resultado['clases_registradas']} clases registradas. No identificadas: {resultado['no_identificadas']}"

if __name__ == "__main__":
    scheduler = configurar_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)