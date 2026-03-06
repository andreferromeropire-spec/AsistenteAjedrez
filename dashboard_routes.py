"""
dashboard_routes.py
"""
from flask import Blueprint, Response, request, session, redirect, jsonify
from functools import wraps
from datetime import date
import os

from database import get_connection

dashboard_bp = Blueprint('dashboard', __name__)
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "ajedrez2026")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('dashboard_logged_in'):
            return redirect('/dashboard/login')
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route('/dashboard/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['dashboard_logged_in'] = True
            return redirect('/dashboard')
        error = '<p class="error">Contraseña incorrecta</p>'
    html = LOGIN_HTML.replace('ERRORBLOCK', error)
    return Response(html, mimetype='text/html')


@dashboard_bp.route('/dashboard/logout')
def logout():
    session.pop('dashboard_logged_in', None)
    return redirect('/dashboard/login')


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return Response(DASHBOARD_HTML, mimetype='text/html')


@dashboard_bp.route('/dashboard/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json()
    mensaje = data.get('mensaje', '').strip()
    historial = data.get('historial', [])
    if not mensaje:
        return jsonify({'respuesta': 'Escribi algo primero.'})
    try:
        from interprete import interpretar_mensaje
        import bot as bot_module
        acciones_pendientes = bot_module.acciones_pendientes
        numero_web = 'dashboard_web'
        accion = 'no_entiendo'
        datos = {}

        if numero_web in acciones_pendientes and mensaje.strip().isdigit():
            pendiente = acciones_pendientes[numero_web]
            opcion = int(mensaje.strip())
            accion_pendiente = pendiente.get('accion')

            if accion_pendiente == 'confirmar_borrado':
                accion = 'confirmar_borrado'
                datos = {'numero_opcion': opcion}

            elif accion_pendiente == 'borrar_pago':
                if 'pagos_candidatos' in pendiente:
                    # El usuario elige qué pago borrar de la lista
                    candidatos = pendiente['pagos_candidatos']
                    if opcion == 0:
                        del acciones_pendientes[numero_web]
                        return jsonify({'respuesta': 'Cancelado, no se borró nada.'})
                    elif 1 <= opcion <= len(candidatos):
                        elegido = candidatos[opcion - 1]
                        accion = 'borrar_pago'
                        datos = {
                            **pendiente['datos'],
                            'pago_id_a_borrar': elegido['id'],
                            'detalle_pago_elegido': elegido
                        }
                        acciones_pendientes[numero_web] = {'accion': 'borrar_pago', 'datos': datos}
                    else:
                        return jsonify({'respuesta': f"Elegí un número entre 0 y {len(candidatos)}."})
                elif pendiente['datos'].get('confirmado') or pendiente['datos'].get('pago_id_a_borrar'):
                    # El usuario confirma o cancela el borrado
                    if opcion == 1:
                        accion = 'borrar_pago'
                        datos = pendiente['datos']
                    elif opcion == 2:
                        del acciones_pendientes[numero_web]
                        return jsonify({'respuesta': 'Cancelado, no se borro nada.'})
                    else:
                        return jsonify({'respuesta': 'Responde 1 para confirmar o 2 para cancelar.'})
                else:
                    accion = 'aclaracion_alumno'
                    datos = {'numero_opcion': opcion}

            elif accion_pendiente == 'registrar_pago' and pendiente['datos'].get('confirmado'):
                # Confirmacion de diferencia de monto
                if opcion == 1:
                    accion = 'registrar_pago'
                    datos = pendiente['datos']
                    del acciones_pendientes[numero_web]
                elif opcion == 2:
                    del acciones_pendientes[numero_web]
                    return jsonify({'respuesta': 'Cancelado. Mandame el pago de nuevo con el monto correcto.'})
                else:
                    return jsonify({'respuesta': 'Responde 1 para confirmar o 2 para reingresar el monto.'})

            else:
                accion = 'aclaracion_alumno'
                datos = {'numero_opcion': opcion}

        else:
            if numero_web in acciones_pendientes and not mensaje.strip().isdigit():
                del acciones_pendientes[numero_web]
            interpretado = interpretar_mensaje(mensaje, historial)
            accion = interpretado.get('accion', 'no_entiendo')
            datos = interpretado.get('datos', {})
            if accion == 'aclaracion_alumno' and numero_web not in acciones_pendientes:
                accion = 'no_entiendo'
                datos = {}

        respuesta = bot_module.ejecutar_accion(accion, datos, numero_web)
        return jsonify({'respuesta': respuesta})
    except Exception as e:
        return jsonify({'respuesta': 'Error: ' + str(e)})


@dashboard_bp.route('/dashboard/api/resumen')
@login_required
def api_resumen():
    try:
        mes = int(request.args.get('mes', date.today().month))
        anio = int(request.args.get('anio', date.today().year))
        conn = get_connection()
        total_alumnos = conn.execute("SELECT COUNT(*) FROM alumnos WHERE activo=1").fetchone()[0]
        clases = conn.execute("""
            SELECT estado, COUNT(*) as n FROM clases
            WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
            GROUP BY estado
        """, (f"{mes:02d}", str(anio))).fetchall()
        clases_dict = {r[0]: r[1] for r in clases if r[0] is not None}
        pagos = conn.execute("""
            SELECT moneda, SUM(monto) as total FROM pagos
            WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
            GROUP BY moneda
        """, (f"{mes:02d}", str(anio))).fetchall()
        pagos_dict = {r[0]: r[1] for r in pagos if r[0] is not None}
        conn.close()
        return jsonify({
            'total_alumnos': total_alumnos,
            'clases_agendadas': clases_dict.get('agendada', 0),
            'clases_canceladas': sum(v for k, v in clases_dict.items() if k and 'cancelada' in k),
            'pagos': pagos_dict
        })
    except Exception as e:
        return jsonify({'error': str(e), 'total_alumnos': 0, 'clases_agendadas': 0, 'clases_canceladas': 0, 'pagos': {}}), 200


@dashboard_bp.route('/dashboard/api/alumnos')
@login_required
def api_alumnos():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    alumnos = conn.execute("""
        SELECT a.id, a.nombre, a.representante, a.pais, a.moneda,
               a.metodo_pago, a.modalidad, a.whatsapp, a.mail,
               COUNT(CASE WHEN c.estado='agendada'
                     AND strftime('%m',c.fecha)=?
                     AND strftime('%Y',c.fecha)=?
                     THEN 1 END) as clases_mes,
               MAX(CASE WHEN p.fecha >= date('now','start of month') THEN 1 ELSE 0 END) as pago_este_mes
        FROM alumnos a
        LEFT JOIN clases c ON c.alumno_id = a.id
        LEFT JOIN pagos p ON p.alumno_id = a.id
            AND strftime('%m',p.fecha)=?
            AND strftime('%Y',p.fecha)=?
        WHERE a.activo = 1
        GROUP BY a.id
        ORDER BY a.nombre
    """, (f"{mes:02d}", str(anio), f"{mes:02d}", str(anio))).fetchall()
    conn.close()
    return jsonify([dict(a) for a in alumnos])


@dashboard_bp.route('/dashboard/api/clases')
@login_required
def api_clases():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    alumno_filtro = request.args.get('alumno', '')
    conn = get_connection()
    query = """
        SELECT c.fecha, c.hora, c.estado, c.origen, c.pago_id,
               a.nombre, a.pais, a.moneda, a.modalidad
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE strftime('%m',c.fecha)=? AND strftime('%Y',c.fecha)=?
        AND a.activo=1
    """
    params = [f"{mes:02d}", str(anio)]
    if alumno_filtro:
        query += " AND a.nombre LIKE ?"
        params.append(f"%{alumno_filtro}%")
    query += " ORDER BY c.fecha, c.hora"
    clases = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(c) for c in clases])


@dashboard_bp.route('/dashboard/api/pagos')
@login_required
def api_pagos():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    pagos = conn.execute("""
        SELECT p.id, p.fecha, p.monto, p.moneda, p.metodo, p.notas, a.nombre, a.representante
        FROM pagos p
        JOIN alumnos a ON p.alumno_id = a.id
        WHERE strftime('%m',p.fecha)=? AND strftime('%Y',p.fecha)=?
        ORDER BY p.fecha DESC
    """, (f"{mes:02d}", str(anio))).fetchall()
    # Para cada pago, buscar las fechas de clases asociadas
    resultado = []
    for p in pagos:
        d = dict(p)
        clases = conn.execute(
            "SELECT fecha FROM clases WHERE pago_id=? ORDER BY fecha ASC",
            (p['id'],)
        ).fetchall()
        if clases:
            dias = ", ".join([c['fecha'].split('-')[2] for c in clases])
            meses = clases[0]['fecha'][:7]  # YYYY-MM
            d['clases_resumen'] = f"{len(clases)} clase{'s' if len(clases)>1 else ''} — días {dias}"
        else:
            d['clases_resumen'] = ''
        resultado.append(d)
    conn.close()
    return jsonify(resultado)


@dashboard_bp.route('/dashboard/api/borrar_pago_id', methods=['POST'])
@login_required
def api_borrar_pago_id():
    data = request.get_json()
    pago_id = data.get('pago_id')
    if not pago_id:
        return jsonify({'ok': False, 'error': 'Falta pago_id'})
    try:
        from pagos import borrar_pago
        ok, resultado = borrar_pago(pago_id)
        return jsonify({'ok': ok, 'clases_desmarcadas': resultado if ok else 0})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@dashboard_bp.route('/dashboard/api/sincronizar', methods=['POST'])
@login_required
def api_sincronizar():
    try:
        from sincronizacion import sincronizacion_diaria
        from datetime import date, datetime
        data = request.get_json() or {}
        hoy = date.today()

        # Acepta lista de meses [{mes, anio}, ...] o mes/anio individuales
        meses_lista = data.get('meses', None)
        if not meses_lista:
            mes = int(data.get('mes', hoy.month))
            anio = int(data.get('anio', hoy.year))
            meses_lista = [{'mes': mes, 'anio': anio}]

        total_nuevos = 0
        total_cancelados = 0
        total_modificados = 0
        todos_no_identificados = []
        detalles = []

        for item in meses_lista:
            m = int(item['mes'])
            a = int(item['anio'])
            resultado = sincronizacion_diaria(m, a, enviar_whatsapp=False)
            total_nuevos += resultado['nuevos']
            total_cancelados += resultado['cancelados']
            total_modificados += resultado['modificados']
            todos_no_identificados += resultado.get('no_identificados', [])
            detalles.append({'mes': m, 'anio': a, 'nuevos': resultado['nuevos'],
                             'cancelados': resultado['cancelados'], 'modificados': resultado['modificados']})

        # Guardar timestamp de última sync
        _ultima_sync['ts'] = datetime.now().strftime('%d/%m %H:%M')
        _ultima_sync['meses'] = [f"{i['mes']}/{i['anio']}" for i in meses_lista]

        return jsonify({
            'ok': True,
            'nuevos': total_nuevos,
            'cancelados': total_cancelados,
            'modificados': total_modificados,
            'no_identificados': todos_no_identificados,
            'detalles': detalles
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# Estado en memoria para última sincronización
_ultima_sync = {'ts': None, 'meses': []}


@dashboard_bp.route('/dashboard/api/ultima_sync')
@login_required
def api_ultima_sync():
    return jsonify(_ultima_sync)


@dashboard_bp.route('/dashboard/api/clases_sin_pagar')
@login_required
def api_clases_sin_pagar():
    """Devuelve clases sin pago_id del mes, agrupadas por responsable."""
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    clases = conn.execute("""
        SELECT c.id, c.fecha, c.hora, c.estado,
               a.id as alumno_id, a.nombre, a.representante,
               a.moneda, a.metodo_pago, a.modalidad
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE c.pago_id IS NULL
        AND c.estado IN ('agendada', 'dada', 'cancelada_sin_anticipacion')
        AND strftime('%m', c.fecha) = ?
        AND strftime('%Y', c.fecha) = ?
        AND a.activo = 1
        ORDER BY a.representante, a.nombre, c.fecha
    """, (f"{mes:02d}", str(anio))).fetchall()

    # Agrupar por responsable
    grupos = {}
    for c in clases:
        responsable = c['representante'] or c['nombre']
        if responsable not in grupos:
            grupos[responsable] = {
                'responsable': responsable,
                'es_representante': bool(c['representante']),
                'moneda': c['moneda'],
                'metodo_pago': c['metodo_pago'],
                'alumnos': {},
                'clases': []
            }
        nombre = c['nombre']
        if nombre not in grupos[responsable]['alumnos']:
            grupos[responsable]['alumnos'][nombre] = {'alumno_id': c['alumno_id'], 'clases': []}
        grupos[responsable]['alumnos'][nombre]['clases'].append({
            'id': c['id'], 'fecha': c['fecha'], 'hora': c['hora'], 'estado': c['estado']
        })
        grupos[responsable]['clases'].append(c['id'])

    # Calcular precio combo para cada grupo
    resultado = []
    for responsable, grupo in grupos.items():
        total_clases = sum(len(a['clases']) for a in grupo['alumnos'].values())
        precio_unitario = None
        moneda = grupo['moneda']
        # Buscar promo usando total combinado (precio combo)
        for alumno_nombre, adata in grupo['alumnos'].items():
            rangos = conn.execute(
                "SELECT * FROM promociones WHERE alumno_id=? ORDER BY clases_desde",
                (adata['alumno_id'],)).fetchall()
            for r in rangos:
                if r['clases_desde'] <= total_clases <= r['clases_hasta']:
                    precio_unitario = r['precio_por_clase']
                    moneda = r['moneda']
                    break
            if precio_unitario is None and rangos:
                precio_unitario = rangos[-1]['precio_por_clase']
                moneda = rangos[-1]['moneda']
            if precio_unitario is not None:
                break

        monto_calculado = round(precio_unitario * total_clases, 2) if precio_unitario else None

        resultado.append({
            'responsable': responsable,
            'es_representante': grupo['es_representante'],
            'moneda': moneda,
            'metodo_pago': grupo['metodo_pago'],
            'alumnos': [
                {'nombre': n, 'alumno_id': a['alumno_id'],
                 'clases': a['clases'], 'cantidad': len(a['clases'])}
                for n, a in grupo['alumnos'].items()
            ],
            'total_clases': total_clases,
            'precio_unitario': precio_unitario,
            'monto_calculado': monto_calculado,
            'clase_ids': grupo['clases']
        })

    conn.close()
    return jsonify(resultado)


@dashboard_bp.route('/dashboard/api/registrar_pago_rapido', methods=['POST'])
@login_required
def api_registrar_pago_rapido():
    """Registra un pago y vincula las clases indicadas."""
    from pagos import registrar_pago
    data = request.get_json()
    alumno_id = data.get('alumno_id')
    clase_ids = data.get('clase_ids', [])
    monto = data.get('monto')
    moneda = data.get('moneda')
    metodo = data.get('metodo')

    if not alumno_id or not clase_ids or monto is None:
        return jsonify({'ok': False, 'error': 'Faltan datos'})

    try:
        conn = get_connection()
        # Para representantes: registrar un pago por alumno con su proporción
        alumnos_data = data.get('alumnos_ids', [{'alumno_id': alumno_id, 'clase_ids': clase_ids}])
        pagos_registrados = 0
        for item in alumnos_data:
            aid = item['alumno_id']
            cids = item['clase_ids']
            if not cids:
                continue
            # Derivar fecha del pago del mes de la primera clase
            primera_clase = conn.execute("SELECT fecha FROM clases WHERE id=?", (cids[0],)).fetchone()
            if primera_clase:
                partes = primera_clase['fecha'].split('-')
                fecha_pago = f"{partes[0]}-{partes[1]}-01"
            else:
                fecha_pago = None
            # Monto proporcional si son varios alumnos
            monto_alumno = data.get('monto_proporcional', {}).get(str(aid), monto)
            pago_id = registrar_pago(aid, monto_alumno, moneda, metodo,
                                     notas='Registrado desde dashboard', fecha_pago=fecha_pago)
            # Vincular clases
            conn.execute(
                f"UPDATE clases SET pago_id=? WHERE id IN ({','.join('?'*len(cids))})",
                [pago_id] + list(cids))
            pagos_registrados += 1
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'pagos': pagos_registrados})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@dashboard_bp.route('/dashboard/api/deudores')
@login_required
def api_deudores():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    deudores = conn.execute("""
        SELECT a.id, a.nombre, a.representante, a.moneda
        FROM alumnos a
        WHERE a.modalidad = 'Mensual' AND a.activo = 1
        AND a.id NOT IN (
            SELECT DISTINCT alumno_id FROM pagos
            WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        )
    """, (f"{mes:02d}", str(anio))).fetchall()

    # Agrupar por representante para calcular precio combo
    grupos = {}  # clave: representante o nombre si no tiene
    for d in deudores:
        clave = d['representante'] if d['representante'] else d['nombre']
        if clave not in grupos:
            grupos[clave] = {'representante': d['representante'], 'moneda': d['moneda'], 'alumnos': []}
        grupos[clave]['alumnos'].append({'id': d['id'], 'nombre': d['nombre'], 'moneda': d['moneda']})

    resultado = []
    for clave, grupo in grupos.items():
        alumnos = grupo['alumnos']

        # Contar clases de cada alumno en el mes
        clases_por_alumno = {}
        for a in alumnos:
            n = conn.execute("""
                SELECT COUNT(*) FROM clases
                WHERE alumno_id=? AND estado='agendada'
                AND strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
            """, (a['id'], f"{mes:02d}", str(anio))).fetchone()[0]
            clases_por_alumno[a['id']] = n

        total_clases = sum(clases_por_alumno.values())

        # Precio combo: buscar en las promos del primer alumno usando total combinado
        # (asumimos que todos los alumnos del mismo representante tienen la misma escala)
        precio_unitario = None
        moneda = grupo['moneda']
        for a in alumnos:
            rangos = conn.execute(
                "SELECT * FROM promociones WHERE alumno_id=? ORDER BY clases_desde",
                (a['id'],)).fetchall()
            for r in rangos:
                if r['clases_desde'] <= total_clases <= r['clases_hasta']:
                    precio_unitario = r['precio_por_clase']
                    moneda = r['moneda']
                    break
            if precio_unitario is None and rangos:
                precio_unitario = rangos[-1]['precio_por_clase']
                moneda = rangos[-1]['moneda']
            if precio_unitario is not None:
                break

        total = round(precio_unitario * total_clases, 2) if precio_unitario else None

        es_combo = len(alumnos) > 1
        nombres = ", ".join([a['nombre'] for a in alumnos])

        resultado.append({
            'nombre': nombres,
            'representante': grupo['representante'] or '-',
            'clases': total_clases,
            'precio_unitario': precio_unitario,
            'total': total,
            'moneda': moneda,
            'es_combo': es_combo
        })

    conn.close()
    return jsonify(resultado)


@dashboard_bp.route('/dashboard/api/grafico_anual')
@login_required
def api_grafico_anual():
    """Clases agendadas y dadas por mes para todo el año."""
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    filas = conn.execute("""
        SELECT strftime('%m', fecha) as mes,
               SUM(CASE WHEN estado IN ('agendada','dada') THEN 1 ELSE 0 END) as total,
               SUM(CASE WHEN estado = 'dada' THEN 1 ELSE 0 END) as dadas,
               SUM(CASE WHEN estado LIKE 'cancelada%' THEN 1 ELSE 0 END) as canceladas
        FROM clases
        WHERE strftime('%Y', fecha) = ?
        GROUP BY mes
        ORDER BY mes
    """, (str(anio),)).fetchall()
    conn.close()
    # Armar los 12 meses siempre (con 0 si no hay datos)
    por_mes = {r['mes']: r for r in filas}
    resultado = []
    for m in range(1, 13):
        key = f"{m:02d}"
        r = por_mes.get(key)
        resultado.append({
            'mes': m,
            'total': r['total'] if r else 0,
            'dadas': r['dadas'] if r else 0,
            'canceladas': r['canceladas'] if r else 0
        })
    return jsonify(resultado)


@dashboard_bp.route('/dashboard/api/ingresos_anuales')
@login_required
def api_ingresos_anuales():
    """Ingresos mensuales por moneda para todo el año."""
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    filas = conn.execute("""
        SELECT strftime('%m', fecha) as mes, moneda, SUM(monto) as total
        FROM pagos
        WHERE strftime('%Y', fecha) = ?
        GROUP BY mes, moneda
        ORDER BY mes
    """, (str(anio),)).fetchall()
    conn.close()
    # Organizar por moneda → array de 12 valores
    monedas = {}
    for r in filas:
        m = r['moneda']
        if m not in monedas:
            monedas[m] = [0] * 12
        monedas[m][int(r['mes']) - 1] = r['total']
    return jsonify(monedas)


@dashboard_bp.route('/dashboard/api/tipo_cambio')
@login_required
def api_tipo_cambio():
    """Devuelve tipo de cambio del día: blue ARS/USD y GBP/USD."""
    import urllib.request, json as _json
    resultado = {'ars_usd': None, 'gbp_usd': None, 'error': None}
    try:
        # Dólar blue desde bluelytics
        req = urllib.request.Request(
            'https://api.bluelytics.com.ar/v2/latest',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = _json.loads(r.read())
        resultado['ars_usd'] = data['blue']['value_sell']
    except Exception as e:
        resultado['error'] = f"Blue no disponible: {e}"
    try:
        # GBP/USD desde frankfurter (oficial, suficiente para esterlinas)
        req2 = urllib.request.Request(
            'https://api.frankfurter.app/latest?from=GBP&to=USD',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req2, timeout=5) as r2:
            data2 = _json.loads(r2.read())
        resultado['gbp_usd'] = data2['rates']['USD']
    except Exception as e2:
        if resultado['error']:
            resultado['error'] += f" | GBP no disponible: {e2}"
        else:
            resultado['error'] = f"GBP no disponible: {e2}"
    return jsonify(resultado)


LOGIN_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Ajedrez</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',sans-serif;background:#f5f0e8;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border:1px solid #e0d8cc;border-radius:6px;padding:3rem 2.5rem;width:100%;max-width:380px;box-shadow:0 8px 40px rgba(0,0,0,0.08)}
.logo{text-align:center;margin-bottom:2.5rem}
.logo .piece{font-size:2.5rem;margin-bottom:0.5rem}
.logo h1{font-family:'Playfair Display',serif;font-size:1.4rem;color:#2c2416}
.logo p{color:#999;font-size:0.8rem;margin-top:0.3rem;letter-spacing:0.1em;text-transform:uppercase}
label{display:block;color:#888;font-size:0.75rem;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem}
input[type=password]{width:100%;background:#faf8f5;border:1px solid #e0d8cc;border-radius:4px;color:#2c2416;padding:0.85rem 1rem;font-size:1rem;font-family:'DM Sans',sans-serif;outline:none;transition:border-color 0.2s}
input[type=password]:focus{border-color:#b48c50}
.error{color:#c0392b;font-size:0.8rem;margin-top:0.75rem}
button{width:100%;margin-top:1.5rem;background:#b48c50;color:#fff;border:none;border-radius:4px;padding:0.9rem;font-size:0.85rem;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;cursor:pointer;font-family:'DM Sans',sans-serif;transition:background 0.2s}
button:hover{background:#9a7540}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="piece">&#9823;</div>
    <h1>Ajedrez Dashboard</h1>
    <p>Panel de gestion</p>
  </div>
  <form method="POST">
    <label for="password">Contrasena</label>
    <input type="password" id="password" name="password" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;" autofocus>
    ERRORBLOCK
    <button type="submit">Ingresar</button>
  </form>
</div>
</body>
</html>"""


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Ajedrez</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--gold:#1a56a0;--gold-light:#1a56a0;--gold-dim:rgba(26,86,160,0.08);--green:#1e7a52;--green-bg:rgba(30,122,82,0.1);--red:#b03030;--red-bg:rgba(176,48,48,0.1)}
[data-theme="light"]{--bg:#ffffff;--bg2:#f0f5fa;--surface:#ffffff;--surface2:#eaf1f8;--border:#b8cfe0;--text:#0a1628;--text-dim:#2c4a6a;--text-muted:#6a8faa;--shadow:rgba(10,40,80,0.08)}
[data-theme="dark"]{--bg:#0c1018;--bg2:#111820;--surface:#161e28;--surface2:#1c2530;--border:#253040;--text:#d0dce8;--text-dim:#5a7090;--text-muted:#354555;--shadow:rgba(0,0,0,0.4)}
[data-theme="navy"]{--bg:#07090f;--bg2:#0b0e18;--surface:#0f1420;--surface2:#131928;--border:#1a2438;--text:#b8ccdf;--text-dim:#4a6280;--text-muted:#253545;--shadow:rgba(0,0,0,0.5);--gold:#4d8fd4;--gold-light:#4d8fd4;--gold-dim:rgba(77,143,212,0.12);--green:#4a9e7a;--red:#c0524a}
html{font-size:15px}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background 0.25s,color 0.25s}
header{display:flex;align-items:center;justify-content:space-between;padding:0.9rem 1.75rem;background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;box-shadow:0 2px 12px var(--shadow)}
.header-left{display:flex;align-items:center;gap:0.75rem}
.header-left h1{font-family:'Playfair Display',serif;font-size:1.05rem;color:var(--gold-light)}
.header-right{display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap}
select,.btn{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.4rem 0.75rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.82rem;cursor:pointer;outline:none;transition:border-color 0.2s,background 0.2s}
select:focus,.btn:hover{border-color:var(--gold)}
.btn{display:flex;align-items:center;gap:0.35rem}
.theme-group{display:flex;border:1px solid var(--border);border-radius:4px;overflow:hidden}
.theme-btn{background:var(--surface2);border:none;color:var(--text-dim);padding:0.4rem 0.6rem;cursor:pointer;font-size:0.85rem;transition:background 0.15s,color 0.15s;border-right:1px solid var(--border)}
.theme-btn:last-child{border-right:none}
.theme-btn.active{background:var(--gold-dim);color:var(--gold-light)}
.theme-btn:hover:not(.active){background:var(--border)}
main{padding:1.5rem 1.75rem;max-width:1440px;margin:0 auto}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:6px;overflow:hidden;margin-bottom:1.5rem;box-shadow:0 2px 8px var(--shadow)}
.metric{background:var(--surface);padding:1.1rem 1.25rem}
.metric-label{font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.3rem}
.metric-value{font-size:1.6rem;font-weight:300;color:var(--gold-light);line-height:1}
.metric-value.green{color:var(--green)}
.metric-value.red{color:var(--red)}
.main-layout{display:grid;grid-template-columns:1fr 340px;gap:1.25rem;align-items:start}
@media(max-width:1024px){.main-layout{grid-template-columns:1fr}}
.tabs{display:flex;border-bottom:1px solid var(--border);margin-bottom:1.25rem;overflow-x:auto}
.tab-btn{background:none;border:none;color:var(--text-dim);padding:0.7rem 1.1rem;font-family:'DM Sans',sans-serif;font-size:0.82rem;cursor:pointer;white-space:nowrap;border-bottom:2px solid transparent;transition:all 0.15s}
.tab-btn:hover{color:var(--text)}
.tab-btn.active{color:var(--gold-light);border-bottom-color:var(--gold)}
.tab-panel{display:none}
.tab-panel.active{display:block}
.table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:5px;box-shadow:0 1px 4px var(--shadow)}
table{width:100%;border-collapse:collapse;font-size:0.83rem}
thead{background:var(--surface2)}
th{padding:0.65rem 0.9rem;text-align:left;font-size:0.67rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid var(--border)}
td{padding:0.65rem 0.9rem;border-bottom:1px solid var(--bg2);color:var(--text);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--gold-dim)}
.badge{display:inline-block;padding:0.18rem 0.5rem;border-radius:3px;font-size:0.68rem;font-weight:500;letter-spacing:0.04em;text-transform:uppercase}
.badge-green{background:var(--green-bg);color:var(--green)}
.badge-red{background:var(--red-bg);color:var(--red)}
.badge-gold{background:var(--gold-dim);color:var(--gold-light)}
.badge-gray{background:var(--bg2);color:var(--text-dim)}
.filters{display:flex;gap:0.6rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center}
.filters input[type=text]{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.38rem 0.75rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.83rem;outline:none;width:200px}
.filters input:focus{border-color:var(--gold)}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem}
@media(max-width:800px){.grid-2{grid-template-columns:1fr}}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:5px;padding:1.25rem;box-shadow:0 1px 4px var(--shadow)}
.chart-box h3{font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem}
.toggle-chip{display:inline-flex;align-items:center;padding:0.2rem 0.6rem;border-radius:20px;font-size:0.72rem;cursor:pointer;border:1px solid var(--border);background:var(--surface2);color:var(--text-muted);transition:all 0.15s;user-select:none}
.toggle-chip.active{border-color:var(--gold);background:var(--gold-dim);color:var(--gold-light)}
.totals-row{display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:0.75rem}
.total-chip{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:0.45rem 0.9rem;font-size:0.82rem}
.total-chip span{color:var(--gold-light);font-weight:500}
.empty{padding:2.5rem;text-align:center;color:var(--text-muted);font-size:0.85rem}
.btn-icon{background:none;border:none;cursor:pointer;padding:0.2rem 0.35rem;border-radius:3px;font-size:0.85rem;opacity:0.45;transition:opacity 0.15s,background 0.15s;color:var(--text)}
.btn-icon:hover{opacity:1;background:var(--gold-dim)}
.btn-icon.danger:hover{background:var(--red-bg);color:var(--red)}
.actions-cell{display:flex;gap:0.2rem;justify-content:center}
.section-title{font-family:'Playfair Display',serif;font-size:0.95rem;color:var(--gold-light);margin-bottom:0.9rem;display:flex;align-items:center;gap:0.5rem}
.section-title::after{content:'';flex:1;height:1px;background:var(--border)}
.section{margin-bottom:1.75rem}
.mes-nav{display:flex;align-items:center;gap:0.25rem}
.mes-btn{padding:0.4rem 0.55rem!important;font-size:0.75rem}
.sync-group{position:relative;display:flex}
.sync-group .btn:first-child{border-right:none;border-radius:4px 0 0 4px}
.sync-arrow{padding:0.4rem 0.5rem!important;border-radius:0 4px 4px 0!important;font-size:0.7rem}
.sync-dropdown{display:none;position:absolute;top:calc(100% + 6px);right:0;background:var(--surface);border:1px solid var(--border);border-radius:5px;padding:0.75rem;min-width:200px;z-index:200;box-shadow:0 4px 16px var(--shadow);flex-direction:column;gap:0.4rem}
.sync-dropdown.open{display:flex}
.sync-dropdown-title{font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.25rem}
.sync-dropdown label{display:flex;align-items:center;gap:0.5rem;font-size:0.83rem;cursor:pointer;padding:0.2rem 0}
.sync-dropdown label:hover{color:var(--gold-light)}
.sync-go{margin-top:0.4rem;width:100%;font-size:0.8rem;padding:0.5rem}
.sync-info{font-size:0.7rem;color:var(--text-muted);white-space:nowrap}
.cobros-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem}
.cobros-vistas{display:flex;border:1px solid var(--border);border-radius:4px;overflow:hidden}
.cobros-vista-btn{background:var(--surface2);border:none;color:var(--text-dim);padding:0.4rem 0.85rem;font-family:'DM Sans',sans-serif;font-size:0.8rem;cursor:pointer;border-right:1px solid var(--border);transition:background 0.15s,color 0.15s}
.cobros-vista-btn:last-child{border-right:none}
.cobros-vista-btn.active{background:var(--gold-dim);color:var(--gold-light)}
.cobros-vista-btn:hover:not(.active){background:var(--border)}
.cobros-grupo{background:var(--surface);border:1px solid var(--border);border-radius:5px;margin-bottom:0.75rem;overflow:hidden}
.cobros-grupo-header{display:flex;align-items:center;justify-content:space-between;padding:0.75rem 1rem;background:var(--surface2);border-bottom:1px solid var(--border);flex-wrap:wrap;gap:0.5rem}
.cobros-grupo-titulo{font-weight:500;font-size:0.9rem}
.cobros-grupo-sub{font-size:0.75rem;color:var(--text-muted);margin-top:0.1rem}
.cobros-grupo-monto{font-size:0.95rem;color:var(--gold-light);font-weight:500}
.cobros-grupo-monto.alerta{color:var(--red)}
.cobros-grupo-clases{padding:0.5rem 1rem;font-size:0.8rem;color:var(--text-dim);border-bottom:1px solid var(--bg2)}
.cobros-grupo-clases:last-child{border-bottom:none}
.cobros-inline-form{padding:0.75rem 1rem;background:var(--bg2);border-top:1px solid var(--border);display:flex;gap:0.5rem;flex-wrap:wrap;align-items:flex-end}
.cobros-inline-form label{font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;display:block;margin-bottom:0.2rem}
.cobros-inline-form input,.cobros-inline-form select{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:0.38rem 0.6rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.82rem;outline:none}
.cobros-inline-form input:focus,.cobros-inline-form select:focus{border-color:var(--gold)}
.chat-panel{background:var(--surface);border:1px solid var(--border);border-radius:6px;display:flex;flex-direction:column;height:calc(100vh - 100px);position:sticky;top:80px;box-shadow:0 2px 12px var(--shadow);overflow:hidden}
.chat-header{padding:0.85rem 1rem;border-bottom:1px solid var(--border);background:var(--surface2);display:flex;align-items:center;gap:0.5rem}
.chat-header h3{font-size:0.85rem;color:var(--text);font-weight:500}
.chat-header p{font-size:0.72rem;color:var(--text-muted);margin-top:0.1rem}
.chat-dot{width:8px;height:8px;background:var(--green);border-radius:50%;flex-shrink:0}
.chat-messages{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:0.75rem;scroll-behavior:smooth}
.chat-messages::-webkit-scrollbar{width:4px}
.chat-messages::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.msg{max-width:88%;display:flex;flex-direction:column;gap:0.2rem}
.msg.user{align-self:flex-end;align-items:flex-end}
.msg.bot{align-self:flex-start;align-items:flex-start}
.msg-bubble{padding:0.6rem 0.85rem;border-radius:12px;font-size:0.83rem;line-height:1.45;word-break:break-word}
.msg.user .msg-bubble{background:var(--gold);color:#fff;border-bottom-right-radius:3px}
.msg.bot .msg-bubble{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-bottom-left-radius:3px}
.msg-time{font-size:0.65rem;color:var(--text-muted);padding:0 0.2rem}
.typing{display:none;align-self:flex-start}
.typing.visible{display:flex}
.typing-bubble{background:var(--surface2);border:1px solid var(--border);border-radius:12px;border-bottom-left-radius:3px;padding:0.6rem 0.85rem;display:flex;gap:4px;align-items:center}
.typing-dot{width:6px;height:6px;background:var(--text-muted);border-radius:50%;animation:bounce 1.2s infinite}
.typing-dot:nth-child(2){animation-delay:0.2s}
.typing-dot:nth-child(3){animation-delay:0.4s}
@keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
.chat-input-area{padding:0.75rem;border-top:1px solid var(--border);display:flex;gap:0.5rem;background:var(--surface)}
.chat-input{flex:1;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.55rem 0.85rem;border-radius:20px;font-family:'DM Sans',sans-serif;font-size:0.85rem;outline:none;resize:none;max-height:100px;transition:border-color 0.2s}
.chat-input:focus{border-color:var(--gold)}
.chat-send{background:var(--gold);color:#fff;border:none;border-radius:50%;width:36px;height:36px;flex-shrink:0;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:1rem;transition:background 0.15s;align-self:flex-end}
.chat-send:hover{background:var(--gold-light)}
.chat-send:disabled{background:var(--border);cursor:not-allowed}
.chat-hint{font-size:0.7rem;color:var(--text-muted);padding:0 0.75rem 0.4rem;line-height:1.4}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <span style="font-size:1.4rem">&#9823;</span>
    <h1>Ajedrez Dashboard</h1>
  </div>
  <div class="header-right">
    <div class="mes-nav">
      <button class="btn mes-btn" onclick="cambiarMes(-1)">&#9664;</button>
      <select id="sel-mes">
        <option value="1">Enero</option><option value="2">Febrero</option>
        <option value="3">Marzo</option><option value="4">Abril</option>
        <option value="5">Mayo</option><option value="6">Junio</option>
        <option value="7">Julio</option><option value="8">Agosto</option>
        <option value="9">Septiembre</option><option value="10">Octubre</option>
        <option value="11">Noviembre</option><option value="12">Diciembre</option>
      </select>
      <select id="sel-anio">
        <option value="2025">2025</option>
        <option value="2026" selected>2026</option>
        <option value="2027">2027</option>
      </select>
      <button class="btn mes-btn" onclick="cambiarMes(1)">&#9654;</button>
    </div>
    <div class="theme-group">
      <button class="theme-btn active" onclick="setTheme('light',this)">&#9728;</button>
      <button class="theme-btn" onclick="setTheme('dark',this)">&#9790;</button>
      <button class="theme-btn" onclick="setTheme('navy',this)">&#127754;</button>
    </div>
    <button class="btn" onclick="cargarTodo()">&#8635; Actualizar</button>
    <div class="sync-group">
      <button class="btn" id="btn-sync" onclick="sincronizarCalendario()">&#128197; Sincronizar</button>
      <button class="btn sync-arrow" id="btn-sync-arrow" onclick="toggleSyncMenu()" title="Elegir meses a sincronizar">&#9660;</button>
      <div class="sync-dropdown" id="sync-dropdown">
        <div class="sync-dropdown-title">Sincronizar meses:</div>
        <label><input type="checkbox" class="sync-check" data-offset="0" checked> Mes actual</label>
        <label><input type="checkbox" class="sync-check" data-offset="1"> Mes siguiente</label>
        <label><input type="checkbox" class="sync-check" data-offset="-1"> Mes anterior</label>
        <label><input type="checkbox" class="sync-check" data-offset="2"> En 2 meses</label>
        <button class="btn sync-go" onclick="sincronizarSeleccion()">&#128197; Sincronizar selección</button>
      </div>
    </div>
    <div class="sync-info" id="sync-info"></div>
    <a href="/dashboard/logout"><button class="btn">Salir</button></a>
  </div>
</header>

<main>
  <div class="metrics" id="metrics">
    <div class="metric"><div class="metric-label">Alumnos activos</div><div class="metric-value" id="m-alumnos">-</div></div>
    <div class="metric"><div class="metric-label">Clases agendadas</div><div class="metric-value" id="m-clases">-</div></div>
    <div class="metric"><div class="metric-label">Canceladas</div><div class="metric-value red" id="m-canceladas">-</div></div>
    <div class="metric"><div class="metric-label">Cobrado USD</div><div class="metric-value green" id="m-usd">-</div></div>
    <div class="metric"><div class="metric-label">Cobrado GBP</div><div class="metric-value green" id="m-gbp">-</div></div>
    <div class="metric"><div class="metric-label">Cobrado ARS</div><div class="metric-value green" id="m-ars">-</div></div>
    <div class="metric"><div class="metric-label">Total est. USD <span style="font-size:0.6rem;opacity:0.6">(blue)</span></div><div class="metric-value green" id="m-total-usd">-</div></div>
  </div>

  <div class="main-layout">
    <div>
      <div class="tabs">
        <button class="tab-btn active" onclick="showTab('clases',this)">Clases</button>
        <button class="tab-btn" onclick="showTab('cobros',this)">Cobros</button>
        <button class="tab-btn" onclick="showTab('pagos',this)">Pagos</button>
        <button class="tab-btn" onclick="showTab('deuda',this)">Deuda</button>
        <button class="tab-btn" onclick="showTab('alumnos',this)">Alumnos</button>
        <button class="tab-btn" onclick="showTab('graficos',this)">Graficos</button>
      </div>

      <div class="tab-panel active" id="tab-clases">
        <div class="filters">
          <select id="filtro-alumno-clases" onchange="cargarClases()">
            <option value="">Todos los alumnos</option>
          </select>
          <select id="filtro-estado" onchange="cargarClases()">
            <option value="">Todos los estados</option>
            <option value="agendada">Agendada</option>
            <option value="cancelada">Cancelada</option>
            <option value="dada">Dada</option>
          </select>
          <select id="filtro-pago" onchange="cargarClases()">
            <option value="">Pagas y no pagas</option>
            <option value="paga">&#10003; Pagas</option>
            <option value="impaga">&#9633; No pagas</option>
          </select>
          <select id="filtro-periodo" onchange="cargarClases()">
            <option value="">Todo el mes</option>
            <option value="semana">Esta semana</option>
          </select>
        </div>
        <div class="table-wrap">
          <table><thead><tr><th>Fecha</th><th>Hora</th><th>Alumno</th><th>Estado</th><th>Pago</th><th>Pais</th></tr></thead>
          <tbody id="t-clases"><tr><td colspan="6" class="empty">Cargando...</td></tr></tbody></table>
        </div>
      </div>

      <div class="tab-panel" id="tab-cobros">
        <div class="cobros-toolbar">
          <div class="cobros-vistas">
            <button class="cobros-vista-btn active" onclick="setCobrosVista('responsable',this)">Por responsable</button>
            <button class="cobros-vista-btn" onclick="setCobrosVista('semana',this)">Por semana</button>
            <button class="cobros-vista-btn" onclick="setCobrosVista('checks',this)">Con checkboxes</button>
          </div>
          <div style="display:flex;gap:0.5rem;align-items:center">
            <button class="btn" id="btn-registrar-seleccion" style="display:none" onclick="registrarSeleccionChecks()">&#10003; Registrar seleccionadas</button>
            <button class="btn" id="btn-abrir-formularios" style="display:none" onclick="abrirFormulariosSeleccionados()">&#10003; Abrir formularios</button>
            <button class="btn" id="btn-registrar-abiertos" style="display:none" onclick="registrarTodosAbiertos()">&#10003; Registrar todos</button>
          </div>
        </div>
        <div id="cobros-content"><div class="empty" style="padding:2.5rem;text-align:center;color:var(--text-muted)">Cargando...</div></div>

        <!-- Modal inline de confirmación de monto -->
        <div id="cobros-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:500;align-items:center;justify-content:center">
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1.5rem;min-width:320px;max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,0.2)">
            <div style="font-family:'Playfair Display',serif;font-size:1rem;color:var(--gold-light);margin-bottom:1rem" id="modal-titulo">Confirmar pago</div>
            <div style="font-size:0.82rem;color:var(--text-muted);margin-bottom:0.4rem" id="modal-detalle"></div>
            <div style="display:flex;flex-direction:column;gap:0.75rem;margin-top:0.75rem">
              <div>
                <label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.3rem">Monto</label>
                <input id="modal-monto" type="number" step="0.01" style="width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.5rem 0.75rem;border-radius:4px;font-size:0.9rem;font-family:'DM Sans',sans-serif;outline:none">
              </div>
              <div>
                <label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.3rem">Moneda</label>
                <select id="modal-moneda" style="width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.5rem 0.75rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.83rem;outline:none">
                  <option>Dólar</option><option>Libra Esterlina</option><option>Pesos</option>
                </select>
              </div>
              <div>
                <label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.3rem">Método</label>
                <select id="modal-metodo" style="width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.5rem 0.75rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.83rem;outline:none">
                  <option>Wise</option><option>PayPal</option><option>Transferencia nacional</option>
                </select>
              </div>
              <div style="display:flex;gap:0.5rem;margin-top:0.25rem">
                <button class="btn" style="flex:1;justify-content:center" onclick="confirmarPagoModal()">&#10003; Confirmar</button>
                <button class="btn" style="flex:1;justify-content:center" onclick="cerrarModal()">Cancelar</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="tab-panel" id="tab-pagos">
        <div class="section">
          <div class="section-title">Pagos registrados</div>
          <div class="filters"><input type="text" placeholder="Buscar..." oninput="filtrarTabla('t-pagos',this.value)"></div>
          <div class="table-wrap">
            <table><thead><tr><th>Fecha</th><th>Alumno</th><th>Monto</th><th>Moneda</th><th>Metodo</th><th>Clases</th><th>Notas</th><th></th></tr></thead>
            <tbody id="t-pagos"><tr><td colspan="7" class="empty">Cargando...</td></tr></tbody></table>
          </div>
          <div class="totals-row" id="totales-pagos"></div>
        </div>
      </div>

      <div class="tab-panel" id="tab-deuda">
        <div class="section">
          <div class="section-title">Alumnos mensuales sin pago</div>
          <div class="table-wrap">
            <table><thead><tr><th>Alumno</th><th>Representante</th><th>Clases</th><th>$/clase</th><th>Total</th><th>Moneda</th></tr></thead>
            <tbody id="t-deuda"><tr><td colspan="6" class="empty">Cargando...</td></tr></tbody></table>
          </div>
          <div class="totals-row" id="totales-deuda"></div>
        </div>
      </div>

      <div class="tab-panel" id="tab-alumnos">
        <div class="filters"><input type="text" placeholder="Buscar nombre o representante..." oninput="filtrarTabla('t-alumnos',this.value)"></div>
        <div class="table-wrap">
          <table><thead><tr><th>ID</th><th>Nombre</th><th>Representante</th><th>Pais</th><th>Moneda</th><th>Metodo</th><th>Modalidad</th><th>Clases</th><th>Pago</th><th></th></tr></thead>
          <tbody id="t-alumnos"><tr><td colspan="9" class="empty">Cargando...</td></tr></tbody></table>
        </div>
      </div>

      <div class="tab-panel" id="tab-graficos">
        <div class="grid-2">
          <div class="chart-box">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem">
              <h3 style="margin:0">Clases por mes</h3>
              <div style="display:flex;gap:0.4rem;flex-wrap:wrap" id="grafico-toggles">
                <label class="toggle-chip active" data-serie="total"><input type="checkbox" checked style="display:none"> Agendadas</label>
                <label class="toggle-chip active" data-serie="dadas"><input type="checkbox" checked style="display:none"> Dadas</label>
                <label class="toggle-chip" data-serie="canceladas"><input type="checkbox" style="display:none"> Canceladas</label>
              </div>
            </div>
            <canvas id="chart-anual" height="260"></canvas>
          </div>
          <div class="chart-box">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;flex-wrap:wrap;gap:0.5rem">
              <h3 style="margin:0">Ingresos mensuales</h3>
              <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">
                <select id="ingr-moneda-sel" onchange="renderIngresos()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.25rem 0.5rem;border-radius:4px;font-family:'DM Sans',sans-serif;font-size:0.78rem;outline:none">
                  <option value="todas">Todas las monedas</option>
                  <option value="Dolar">Dólar</option>
                  <option value="Libra Esterlina">Libra Esterlina</option>
                  <option value="Pesos">Pesos</option>
                  <option value="usd_total">Todo en USD (blue)</option>
                </select>
                <span id="ingr-tc-info" style="font-size:0.7rem;color:var(--text-muted)"></span>
              </div>
            </div>
            <canvas id="chart-ingresos" height="260"></canvas>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-panel">
      <div class="chat-header">
        <div class="chat-dot"></div>
        <div>
          <h3>Asistente &#9823;</h3>
          <p>Mismo bot que WhatsApp</p>
        </div>
      </div>
      <div class="chat-messages" id="chat-messages">
        <div class="msg bot">
          <div class="msg-bubble">Hola! Soy el mismo bot de WhatsApp. Registra pagos, clases, consulta deudas... lo que necesites.</div>
          <div class="msg-time">ahora</div>
        </div>
      </div>
      <div class="typing" id="typing">
        <div class="typing-bubble">
          <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
        </div>
      </div>
      <p class="chat-hint">Ej: "pago Grace $100 dolares Wise", "clase con Lucas hoy", "quien debe este mes"</p>
      <div class="chat-input-area">
        <textarea class="chat-input" id="chat-input" placeholder="Escribe tu mensaje..." rows="1"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();enviarMensaje()}"
          oninput="autoResize(this)"></textarea>
        <button class="chat-send" id="chat-send" onclick="enviarMensaje()">&#9658;</button>
      </div>
    </div>
  </div>
</main>

<script>
var mes = new Date().getMonth() + 1;
var anio = new Date().getFullYear();
var charts = {};
var chatHistorial = [];

document.getElementById('sel-mes').value = mes;
document.getElementById('sel-anio').value = anio;
document.getElementById('sel-mes').addEventListener('change', function() { mes = +this.value; cargarTodo(); });
document.getElementById('sel-anio').addEventListener('change', function() { anio = +this.value; cargarTodo(); });

var DIAS_SEMANA = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
var MESES_NOMBRES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                     'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

function cambiarMes(delta) {
  var d = new Date(anio, mes - 1 + delta, 1);
  mes = d.getMonth() + 1;
  anio = d.getFullYear();
  document.getElementById('sel-mes').value = mes;
  document.getElementById('sel-anio').value = anio;
  cargarTodo();
}

function toggleSyncMenu() {
  var dd = document.getElementById('sync-dropdown');
  dd.classList.toggle('open');
}


function mesOffset(offset) {
  var d = new Date(anio, mes - 1 + offset, 1);
  return {mes: d.getMonth() + 1, anio: d.getFullYear()};
}

function sincronizarSeleccion() {
  var checks = document.querySelectorAll('.sync-check:checked');
  if (checks.length === 0) { alert('Seleccioná al menos un mes.'); return; }
  var meses = [];
  checks.forEach(function(c) {
    var offset = parseInt(c.getAttribute('data-offset'));
    meses.push(mesOffset(offset));
  });
  document.getElementById('sync-dropdown').classList.remove('open');
  ejecutarSync(meses);
}

function setTheme(tema, btn) {
  document.documentElement.setAttribute('data-theme', tema);
  localStorage.setItem('dashboard-theme', tema);
  document.querySelectorAll('.theme-btn').forEach(function(b) { b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  if (document.getElementById('tab-graficos').classList.contains('active')) cargarGraficos();
}

(function() {
  var saved = localStorage.getItem('dashboard-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  var idx = {light:0, dark:1, navy:2}[saved] || 0;
  var btns = document.querySelectorAll('.theme-btn');
  btns.forEach(function(b){ b.classList.remove('active'); });
  if (btns[idx]) btns[idx].classList.add('active');
})();

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function ahora() {
  return new Date().toLocaleTimeString('es-AR', {hour:'2-digit', minute:'2-digit'});
}

function agregarMensaje(texto, tipo) {
  var container = document.getElementById('chat-messages');
  var div = document.createElement('div');
  div.className = 'msg ' + tipo;
  var bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = texto.split('\\n').join('<br>');
  var time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = ahora();
  div.appendChild(bubble);
  div.appendChild(time);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function enviarMensaje() {
  var input = document.getElementById('chat-input');
  var texto = input.value.trim();
  if (!texto) return;
  agregarMensaje(texto, 'user');
  chatHistorial.push({role:'user', content:texto});
  input.value = '';
  input.style.height = 'auto';
  var typing = document.getElementById('typing');
  var container = document.getElementById('chat-messages');
  typing.classList.add('visible');
  container.appendChild(typing);
  container.scrollTop = container.scrollHeight;
  var btn = document.getElementById('chat-send');
  btn.disabled = true;
  var recent = chatHistorial.slice(-10);
  fetch('/dashboard/api/chat', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({mensaje:texto, historial:recent})
  })
  .then(function(r){ return r.json(); })
  .then(function(data) {
    typing.classList.remove('visible');
    agregarMensaje(data.respuesta, 'bot');
    chatHistorial.push({role:'assistant', content:data.respuesta});
    var palabras = ['registre','pago','agende','cancele','actualice','borre','agregue'];
    var lower = data.respuesta.toLowerCase();
    for (var i=0; i<palabras.length; i++) {
      if (lower.indexOf(palabras[i]) !== -1) { setTimeout(cargarTodo, 800); break; }
    }
    btn.disabled = false;
    input.focus();
  })
  .catch(function() {
    typing.classList.remove('visible');
    agregarMensaje('Error de conexion. Intenta de nuevo.', 'bot');
    btn.disabled = false;
  });
}

function api(ruta) {
  var sep = ruta.indexOf('?') !== -1 ? '&' : '?';
  return fetch('/dashboard/api/' + ruta + sep + 'mes=' + mes + '&anio=' + anio).then(function(r){ return r.json(); });
}

function fmt(n) { return Number(n).toLocaleString('es-AR'); }

function estadoBadge(e) {
  var map = {
    'agendada':'<span class="badge badge-gold">Agendada</span>',
    'cancelada_con_anticipacion':'<span class="badge badge-gray">Cancelada ok</span>',
    'cancelada_sin_anticipacion':'<span class="badge badge-red">Cancelada tarde</span>',
    'cancelada_por_profesora':'<span class="badge badge-gray">Cancelada prof</span>',
    'dada':'<span class="badge badge-green">Dada</span>'
  };
  return map[e] || e;
}

function cargarTodo() {
  // Cargar tipo de cambio primero para que las métricas ya lo tengan
  if (!window._tipoCambio) {
    fetch('/dashboard/api/tipo_cambio').then(function(r){ return r.json(); })
    .then(function(tc) {
      window._tipoCambio = tc;
      var info = document.getElementById('ingr-tc-info');
      if (info && tc.ars_usd) info.textContent = '\u00b7 Blue: $' + tc.ars_usd + ' ARS/USD';
      cargarResumen(); // Re-cargar métricas con el TC ya disponible
    }).catch(function(){ window._tipoCambio = {}; });
  }
  cargarResumen();
  poblarFiltroAlumnos();
  cargarClases();
  cargarPagos();
  cargarDeudores();
  cargarAlumnos();
  cargarUltimaSync();
}

function cargarResumen() {
  api('resumen').then(function(d) {
    document.getElementById('m-alumnos').textContent = d.total_alumnos;
    document.getElementById('m-clases').textContent = d.clases_agendadas;
    document.getElementById('m-canceladas').textContent = d.clases_canceladas;
    var usd = d.pagos['Dolar'] || d.pagos['D\u00f3lar'] || 0;
    var gbp = d.pagos['Libra Esterlina'] || 0;
    var ars = d.pagos['Pesos'] || 0;
    document.getElementById('m-usd').textContent = usd ? '$'+fmt(usd) : '-';
    document.getElementById('m-gbp').textContent = gbp ? '\u00a3'+fmt(gbp) : '-';
    document.getElementById('m-ars').textContent = ars ? '$'+fmt(ars) : '-';
    // Calcular total en USD si hay tipo de cambio disponible
    if (window._tipoCambio && window._tipoCambio.ars_usd) {
      var tc = window._tipoCambio;
      var totalUsd = usd + (gbp * (tc.gbp_usd || 1.27)) + (ars / tc.ars_usd);
      var elTotal = document.getElementById('m-total-usd');
      if (elTotal) elTotal.textContent = '~$' + fmt(Math.round(totalUsd));
    }
  });
}

function poblarFiltroAlumnos() {
  api('alumnos').then(function(datos) {
    var sel = document.getElementById('filtro-alumno-clases');
    var actual = sel.value;
    // Mantener solo la primera opcion
    while (sel.options.length > 1) sel.remove(1);
    datos.sort(function(a,b){ return a.nombre.localeCompare(b.nombre); });
    datos.forEach(function(a) {
      var opt = document.createElement('option');
      opt.value = a.nombre;
      opt.textContent = a.nombre;
      if (a.nombre === actual) opt.selected = true;
      sel.appendChild(opt);
    });
  });
}

function formatFecha(fechaStr) {
  // fechaStr = "2026-03-10" → "Mar 10/03"
  var partes = fechaStr.split('-');
  var d = new Date(+partes[0], +partes[1] - 1, +partes[2]);
  return DIAS_SEMANA[d.getDay()] + ' ' + partes[2] + '/' + partes[1];
}

function semanaActual() {
  var hoy = new Date();
  var lunes = new Date(hoy);
  lunes.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7));
  var domingo = new Date(lunes);
  domingo.setDate(lunes.getDate() + 6);
  return {desde: lunes, hasta: domingo};
}

function cargarClases() {
  var estadoFiltro = document.getElementById('filtro-estado').value;
  var alumnoFiltro = document.getElementById('filtro-alumno-clases').value;
  var pagoFiltro = document.getElementById('filtro-pago').value;
  var periodoFiltro = document.getElementById('filtro-periodo').value;
  var url = 'clases' + (alumnoFiltro ? '?alumno='+encodeURIComponent(alumnoFiltro) : '');
  api(url).then(function(datos) {
    if (estadoFiltro) datos = datos.filter(function(c){ return c.estado.indexOf(estadoFiltro) !== -1; });
    if (pagoFiltro === 'paga') datos = datos.filter(function(c){ return !!c.pago_id; });
    if (pagoFiltro === 'impaga') datos = datos.filter(function(c){ return !c.pago_id; });
    if (periodoFiltro === 'semana') {
      var sem = semanaActual();
      datos = datos.filter(function(c) {
        var p = c.fecha.split('-');
        var d = new Date(+p[0], +p[1]-1, +p[2]);
        return d >= sem.desde && d <= sem.hasta;
      });
    }
    var html = datos.length ? datos.map(function(c) {
      var pagoBadge = c.pago_id ? '<span title="Pago registrado" style="color:var(--green)">&#10003;</span>' : '';
      return '<tr><td style="white-space:nowrap">'+formatFecha(c.fecha)+'</td><td>'+(c.hora||'-')+'</td><td><strong>'+c.nombre+'</strong></td><td>'+estadoBadge(c.estado)+'</td><td style="text-align:center">'+pagoBadge+'</td><td>'+(c.pais||'-')+'</td></tr>';
    }).join('') : '<tr><td colspan="6" class="empty">Sin clases en este periodo</td></tr>';
    document.getElementById('t-clases').innerHTML = html;
  });
}

function cargarPagos() {
  api('pagos').then(function(datos) {
    var monedas = {};
    var html = datos.length ? datos.map(function(p) {
      monedas[p.moneda] = (monedas[p.moneda]||0) + p.monto;
      var sim = p.moneda === 'Libra Esterlina' ? '\u00a3' : '$';
      var rep = (p.representante && p.representante !== '-') ? '<br><span style="color:var(--text-muted);font-size:0.75rem">'+p.representante+'</span>' : '';
      var np = p.nombre.replace(/"/g, '&quot;');
      var sim = p.moneda === 'Libra Esterlina' ? 'GBP' : p.moneda;
      var resumen = encodeURIComponent(p.fecha + ' ' + fmt(p.monto) + ' ' + sim + ' ' + p.nombre);
      var borrar = '<button class="btn-icon danger btn-borrar-pago" title="Borrar pago" data-pago-id="'+p.id+'" data-resumen="'+resumen+'">&#128465;</button>';
      var clases_res = p.clases_resumen ? '<span style="color:var(--text-dim);font-size:0.78rem">'+p.clases_resumen+'</span>' : '-';
      return '<tr><td>'+p.fecha+'</td><td><strong>'+p.nombre+'</strong>'+rep+'</td><td>'+sim+fmt(p.monto)+'</td><td><span class="badge badge-gold">'+p.moneda+'</span></td><td>'+(p.metodo||'-')+'</td><td>'+clases_res+'</td><td style="color:var(--text-muted);font-size:0.78rem">'+(p.notas||'-')+'</td><td>'+borrar+'</td></tr>';
    }).join('') : '<tr><td colspan="7" class="empty">Sin pagos registrados</td></tr>';
    document.getElementById('t-pagos').innerHTML = html;
    var chips = Object.keys(monedas).map(function(m) {
      var s = m === 'Libra Esterlina' ? '\u00a3' : '$';
      return '<div class="total-chip">Total '+m+': <span>'+s+fmt(monedas[m])+'</span></div>';
    }).join('');
    document.getElementById('totales-pagos').innerHTML = chips;
  });
}

function cargarDeudores() {
  api('deudores').then(function(datos) {
    var porCobrar = {};
    var html = datos.length ? datos.map(function(d) {
      if (d.total && d.moneda) porCobrar[d.moneda] = (porCobrar[d.moneda]||0) + d.total;
      var sim = d.moneda === 'Libra Esterlina' ? '\u00a3' : '$';
      return '<tr><td><strong>'+d.nombre+'</strong></td><td>'+d.representante+'</td><td>'+d.clases+'</td><td>'+(d.precio_unitario ? sim+fmt(d.precio_unitario) : '-')+'</td><td>'+(d.total ? '<strong>'+sim+fmt(d.total)+'</strong>' : '-')+'</td><td><span class="badge badge-gold">'+d.moneda+'</span></td></tr>';
    }).join('') : '<tr><td colspan="6" class="empty" style="color:var(--green)">Todos pagaron este mes</td></tr>';
    document.getElementById('t-deuda').innerHTML = html;
    var chips = Object.keys(porCobrar).map(function(m) {
      var s = m === 'Libra Esterlina' ? '\u00a3' : '$';
      return '<div class="total-chip">Por cobrar '+m+': <span>'+s+fmt(porCobrar[m])+'</span></div>';
    }).join('') || '<span style="color:var(--text-muted);font-size:0.82rem">Sin deuda pendiente</span>';
    document.getElementById('totales-deuda').innerHTML = chips;
  });
}

function cargarAlumnos() {
  api('alumnos').then(function(datos) {
    var html = datos.map(function(a) {
      var pago = a.pago_este_mes ? '<span class="badge badge-green">Si</span>' : '<span class="badge badge-red">No</span>';
      var n = a.nombre.replace(/"/g, '&quot;');
      var acciones = '<div class="actions-cell">'
        + '<button class="btn-icon btn-editar" title="Ver / editar" data-nombre="'+n+'">&#9998;</button>'
        + '<button class="btn-icon danger btn-borrar-alumno" title="Borrar" data-nombre="'+n+'">&#128465;</button>'
        + '</div>';
      return '<tr><td style="font-size:0.75rem;color:var(--text-muted);font-family:monospace">#'+a.id+'</td><td><strong>'+a.nombre+'</strong></td><td>'+(a.representante||'-')+'</td><td>'+(a.pais||'-')+'</td><td><span class="badge badge-gold">'+(a.moneda||'-')+'</span></td><td style="font-size:0.78rem;color:var(--text-muted)">'+(a.metodo_pago||'-')+'</td><td style="font-size:0.78rem;color:var(--text-muted)">'+(a.modalidad||'-')+'</td><td style="text-align:center">'+a.clases_mes+'</td><td style="text-align:center">'+pago+'</td><td>'+acciones+'</td></tr>';
    }).join('') || '<tr><td colspan="9" class="empty">Sin alumnos</td></tr>';
    document.getElementById('t-alumnos').innerHTML = html;
  });
}

var graficosSeriesVisibles = {total: true, dadas: true, canceladas: false};
var graficosData = null;

function cargarGraficos() {
  var isDark = ['dark','navy'].indexOf(document.documentElement.getAttribute('data-theme')) !== -1;
  var tickColor = isDark ? '#8a9bb0' : '#6a8faa';
  var gridColor = isDark ? '#1a2535' : '#e0eaf4';
  var meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

  // Gráfico 1: Clases por mes (anual)
  fetch('/dashboard/api/grafico_anual?anio=' + anio).then(function(r){ return r.json(); })
  .then(function(datos) {
    graficosData = datos;
    renderGraficoAnual(datos, meses, tickColor, gridColor);
  });

  // Gráfico 2: Ingresos mensuales
  fetch('/dashboard/api/ingresos_anuales?anio=' + anio).then(function(r){ return r.json(); })
  .then(function(data) {
    window._ingresosData = data;
    window._ingresosTickColor = tickColor;
    window._ingresosGridColor = gridColor;
    window._ingresosMeses = meses;
    // Cargar tipo de cambio en paralelo
    fetch('/dashboard/api/tipo_cambio').then(function(r){ return r.json(); })
    .then(function(tc) {
      window._tipoCambio = tc;
      var info = document.getElementById('ingr-tc-info');
      if (tc.ars_usd && !tc.error) {
        info.textContent = '\u00b7 Blue: $' + tc.ars_usd + ' ARS/USD';
      } else if (tc.error) {
        info.textContent = '\u00b7 TC no disponible';
        info.title = tc.error;
      }
      renderIngresos();
    }).catch(function() {
      window._tipoCambio = {};
      renderIngresos();
    });
  });

  // Activar toggles
  document.querySelectorAll('.toggle-chip').forEach(function(chip) {
    chip.onclick = function() {
      var serie = chip.getAttribute('data-serie');
      graficosSeriesVisibles[serie] = !graficosSeriesVisibles[serie];
      chip.classList.toggle('active', graficosSeriesVisibles[serie]);
      chip.querySelector('input').checked = graficosSeriesVisibles[serie];
      if (graficosData) renderGraficoAnual(graficosData, meses, tickColor, gridColor);
    };
  });
}

function renderIngresos() {
  var monedas = window._ingresosData;
  var tickColor = window._ingresosTickColor || '#6a8faa';
  var gridColor = window._ingresosGridColor || '#e0eaf4';
  var meses = window._ingresosMeses || ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  var tc = window._tipoCambio || {};
  if (!monedas) return;

  var sel = document.getElementById('ingr-moneda-sel').value;
  var colores = {'D\u00f3lar': '#4a9e7a', 'Libra Esterlina': '#5b8db8', 'Pesos': '#c0524a'};
  var datasets = [];
  var yLabel = '';

  if (sel === 'usd_total') {
    // Convertir todo a USD usando blue para ARS y frankfurter para GBP
    var arsUsd = tc.ars_usd ? 1 / tc.ars_usd : null;
    var gbpUsd = tc.gbp_usd || null;
    var total = [0,0,0,0,0,0,0,0,0,0,0,0];
    var ok = true;
    Object.keys(monedas).forEach(function(m) {
      monedas[m].forEach(function(v, i) {
        if (!v) return;
        if (m === 'D\u00f3lar' || m === 'Dolar') {
          total[i] += v;
        } else if ((m === 'Libra Esterlina') && gbpUsd) {
          total[i] += v * gbpUsd;
        } else if (m === 'Pesos' && arsUsd) {
          total[i] += v * arsUsd;
        } else {
          ok = false; // Falta tipo de cambio
        }
      });
    });
    if (!ok) {
      document.getElementById('ingr-tc-info').textContent = '\u00b7 Falta TC para convertir';
    }
    datasets.push({
      label: 'Total USD (estimado)',
      data: total.map(function(v){ return Math.round(v * 100) / 100; }),
      borderColor: '#4a9e7a',
      backgroundColor: '#4a9e7a22',
      borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.3, fill: true
    });
    yLabel = 'USD';
  } else if (sel === 'todas') {
    Object.keys(monedas).forEach(function(m) {
      datasets.push({
        label: m,
        data: monedas[m],
        borderColor: colores[m] || '#b48c50',
        backgroundColor: (colores[m] || '#b48c50') + '22',
        borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.3, fill: true
      });
    });
  } else {
    // Moneda específica — buscar con o sin tilde
    var key = Object.keys(monedas).find(function(k){ return k === sel || k.replace('\u00f3','o') === sel.replace('\u00f3','o'); });
    if (key && monedas[key]) {
      datasets.push({
        label: key,
        data: monedas[key],
        borderColor: colores[key] || '#b48c50',
        backgroundColor: (colores[key] || '#b48c50') + '22',
        borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.3, fill: true
      });
    }
  }

  if (charts.ingresos) charts.ingresos.destroy();
  charts.ingresos = new Chart(document.getElementById('chart-ingresos').getContext('2d'), {
    type: 'line',
    data: { labels: meses, datasets: datasets },
    options: {
      plugins: {
        legend: { labels: { color: tickColor, font: { size: 11 }, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString('es-AR');
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: tickColor }, grid: { color: gridColor } },
        y: { ticks: { color: tickColor, callback: function(v){ return v.toLocaleString('es-AR'); } },
             grid: { color: gridColor }, beginAtZero: true,
             title: yLabel ? { display: true, text: yLabel, color: tickColor, font: { size: 10 } } : { display: false } }
      }
    }
  });
}


function renderGraficoAnual(datos, meses, tickColor, gridColor) {
  if (charts.anual) charts.anual.destroy();
  var datasets = [];
  if (graficosSeriesVisibles.total) datasets.push({
    label: 'Agendadas', data: datos.map(function(d){return d.total;}),
    backgroundColor: 'rgba(26,86,160,0.45)', borderColor: '#1a56a0', borderWidth: 1, borderRadius: 3
  });
  if (graficosSeriesVisibles.dadas) datasets.push({
    label: 'Dadas', data: datos.map(function(d){return d.dadas;}),
    backgroundColor: 'rgba(30,122,82,0.5)', borderColor: '#1e7a52', borderWidth: 1, borderRadius: 3
  });
  if (graficosSeriesVisibles.canceladas) datasets.push({
    label: 'Canceladas', data: datos.map(function(d){return d.canceladas;}),
    backgroundColor: 'rgba(176,48,48,0.45)', borderColor: '#b03030', borderWidth: 1, borderRadius: 3
  });
  charts.anual = new Chart(document.getElementById('chart-anual').getContext('2d'), {
    type: 'bar',
    data: { labels: meses, datasets: datasets },
    options: {
      plugins: { legend: { labels: { color: tickColor, font: { size: 11 }, boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: tickColor }, grid: { color: gridColor } },
        y: { ticks: { color: tickColor }, grid: { color: gridColor }, beginAtZero: true }
      }
    }
  });
}

function showTab(id, btn) {
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  document.getElementById('tab-'+id).classList.add('active');
  if (btn) btn.classList.add('active');
  if (id === 'graficos') cargarGraficos();
  if (id === 'cobros') cargarCobros();
}

function filtrarTabla(tablaId, texto) {
  document.querySelectorAll('#'+tablaId+' tr').forEach(function(f){
    f.style.display = f.textContent.toLowerCase().indexOf(texto.toLowerCase()) !== -1 ? '' : 'none';
  });
}

// Funciones de accion rapida via delegacion de eventos (evita problemas de escapado)
function enviarAlChat(texto) {
  var input = document.getElementById('chat-input');
  input.value = texto;
  input.focus();
  input.style.borderColor = 'var(--gold)';
  setTimeout(function(){ input.style.borderColor = ''; }, 1500);
}

function editarAlumno(nombre) {
  enviarAlChat('ver ' + nombre);
  setTimeout(enviarMensaje, 100);
}

function borrarAlumno(nombre) {
  if (!confirm('\u00bfBorrar a ' + nombre + '? Esto abrira el flujo de confirmacion en el chat.')) return;
  enviarAlChat('borra a ' + nombre);
  setTimeout(enviarMensaje, 100);
}

function borrarPago(nombre) {
  enviarAlChat('borrar un pago de ' + nombre);
  setTimeout(enviarMensaje, 100);
}

function borrarPagoDirecto(pagoId, resumen) {
  if (!confirm('\u00bfBorrar este pago?\\n' + resumen)) return;
  fetch('/dashboard/api/borrar_pago_id', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pago_id: pagoId})
  }).then(function(r){ return r.json(); })
  .then(function(d) {
    if (d.ok) {
      var msg = '\u2705 Pago borrado.';
      if (d.clases_desmarcadas > 0) msg += ' (' + d.clases_desmarcadas + ' clase(s) desmarcada(s))';
      alert(msg);
      cargarTodo();
  poblarFiltroAlumnos();
    } else {
      alert('Error: ' + (d.error || 'No se pudo borrar'));
    }
  }).catch(function(){ alert('Error de conexion'); });
}

// Delegacion de eventos para botones generados dinamicamente + cerrar dropdown
document.addEventListener('click', function(e) {
  // Cerrar dropdown de sync si se hace click fuera
  var sg = document.querySelector('.sync-group');
  if (sg && !sg.contains(e.target)) {
    var dd = document.getElementById('sync-dropdown');
    if (dd) dd.classList.remove('open');
  }
  var btn = e.target.closest('button');
  if (!btn) return;
  // Cancelar formulario inline de cobros (responsable)
  if (btn.classList.contains('cobro-cancelar-btn')) {
    var gi = btn.getAttribute('data-gi');
    var f = document.getElementById('cobro-form-' + gi);
    if (f) f.style.display = 'none';
    return;
  }
  // Cancelar formulario inline de cobros (semana)
  if (btn.classList.contains('cobros-sem-cancelar')) {
    var si = btn.getAttribute('data-si');
    var fs = document.getElementById('sem-form-' + si);
    if (fs) fs.style.display = 'none';
    return;
  }
  if (btn.classList.contains('btn-borrar-pago')) {
    var pagoId = btn.getAttribute('data-pago-id');
    var resumen = decodeURIComponent(btn.getAttribute('data-resumen') || '');
    borrarPagoDirecto(pagoId, resumen);
    return;
  }
  var nombre = btn.getAttribute('data-nombre');
  if (!nombre) return;
  if (btn.classList.contains('btn-editar')) editarAlumno(nombre);
  else if (btn.classList.contains('btn-borrar-alumno')) borrarAlumno(nombre);
});


// ── COBROS ──────────────────────────────────────────────
var cobrosVista = 'responsable';
var cobrosData = [];

function setCobrosVista(v, btn) {
  cobrosVista = v;
  document.querySelectorAll('.cobros-vista-btn').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  var btnSel = document.getElementById('btn-registrar-seleccion');
  btnSel.style.display = v === 'checks' ? 'flex' : 'none';
  renderCobros();
}

function cargarCobros() {
  api('clases_sin_pagar').then(function(datos) {
    cobrosData = datos;
    renderCobros();
  });
}

function renderCobros() {
  var cont = document.getElementById('cobros-content');
  if (!cobrosData || !cobrosData.length) {
    cont.innerHTML = '<div class="empty" style="padding:2.5rem;text-align:center;color:var(--green)">\u2705 Todo cobrado este mes</div>';
    return;
  }
  if (cobrosVista === 'responsable') renderCobrosResponsable(cont);
  else if (cobrosVista === 'semana') renderCobrosSemana(cont);
  else renderCobrosChecks(cont);
}

function simMoneda(m) { return m === 'Libra Esterlina' ? '\u00a3' : '$'; }

function renderCobrosResponsable(cont) {
  var html = '<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;font-size:0.8rem;color:var(--text-muted)">'
    + '<input type="checkbox" id="resp-master" onchange="selectAllResponsable(this)" style="width:15px;height:15px;cursor:pointer">'
    + '<label for="resp-master" style="cursor:pointer">Seleccionar todos</label>'
    + '</div>';
  html += cobrosData.map(function(g, gi) {
    var sim = simMoneda(g.moneda);
    var montoStr = g.monto_calculado ? sim + fmt(g.monto_calculado) + ' ' + g.moneda : 'sin precio';
    var sublinea = g.es_representante ? 'Representante' : 'Alumno';
    var alumnos = g.alumnos.map(function(a) {
      var fechas = a.clases.map(function(c){ return formatFecha(c.fecha); }).join(', ');
      return '<div class="cobros-grupo-clases"><strong>' + a.nombre + '</strong> \u2014 ' + a.cantidad + ' clase(s): <span style="color:var(--text-muted)">' + fechas + '</span></div>';
    }).join('');
    return '<div class="cobros-grupo" id="cobro-grupo-' + gi + '">'
      + '<div class="cobros-grupo-header">'
      + '<div style="display:flex;align-items:center;gap:0.6rem">'
      + '<input type="checkbox" class="resp-check" data-gi="' + gi + '" onchange="actualizarBotonesResponsable()" style="width:15px;height:15px;cursor:pointer">'
      + '<div><div class="cobros-grupo-titulo">' + g.responsable + '</div>'
      + '<div class="cobros-grupo-sub">' + sublinea + ' &bull; ' + g.total_clases + ' clase(s) sin pagar</div></div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:0.75rem">'
      + '<span class="cobros-grupo-monto">' + montoStr + '</span>'
      + '<button class="btn" onclick="abrirPago(' + gi + ')">Registrar pago</button>'
      + '</div></div>'
      + alumnos
      + '<div class="cobros-inline-form" id="cobro-form-' + gi + '" style="display:none"></div>'
      + '</div>';
  }).join('');
  cont.innerHTML = html;
}

function selectAllResponsable(master) {
  document.querySelectorAll('.resp-check').forEach(function(c){ c.checked = master.checked; });
  actualizarBotonesResponsable();
}

function actualizarBotonesResponsable() {
  var checks = document.querySelectorAll('.resp-check:checked');
  var btnAbrir = document.getElementById('btn-abrir-formularios');
  var btnReg = document.getElementById('btn-registrar-abiertos');
  btnAbrir.style.display = checks.length ? 'flex' : 'none';
  // btn-registrar-abiertos se muestra solo si hay formularios abiertos
  var hayAbiertos = document.querySelectorAll('.cobros-inline-form[style*="flex"]').length > 0;
  btnReg.style.display = hayAbiertos ? 'flex' : 'none';
}

function abrirFormulariosSeleccionados() {
  var checks = document.querySelectorAll('.resp-check:checked');
  // Cerrar todos primero
  document.querySelectorAll('.cobros-inline-form').forEach(function(f){ f.style.display = 'none'; });
  checks.forEach(function(chk) {
    var gi = parseInt(chk.getAttribute('data-gi'));
    abrirPago(gi);
  });
  // Mostrar botón de registrar todos
  document.getElementById('btn-registrar-abiertos').style.display = 'flex';
  document.getElementById('btn-abrir-formularios').style.display = 'none';
}

function registrarTodosAbiertos() {
  // Recolectar todos los formularios visibles y enviarlos en secuencia
  var forms = document.querySelectorAll('.cobros-inline-form[style*="flex"]');
  if (!forms.length) return;
  var pendientes = [];
  forms.forEach(function(form) {
    var gi = parseInt(form.id.replace('cobro-form-', ''));
    var monto = parseFloat(form.querySelector('.cobro-monto-input').value);
    var moneda = form.querySelector('.cobro-moneda-input').value;
    var metodo = form.querySelector('.cobro-metodo-input').value;
    if (!monto || isNaN(monto)) return; // Saltear sin precio
    pendientes.push({gi: gi, monto: monto, moneda: moneda, metodo: metodo});
  });
  if (!pendientes.length) { alert('No hay formularios con monto v\u00e1lido para registrar.'); return; }
  var registrados = 0;
  var errores = [];
  function procesarSiguiente(idx) {
    if (idx >= pendientes.length) {
      var msg = '\u2705 ' + registrados + ' pago(s) registrado(s).';
      if (errores.length) msg += '\n\u26a0\ufe0f Errores: ' + errores.join(', ');
      alert(msg);
      document.getElementById('btn-registrar-abiertos').style.display = 'none';
      document.getElementById('btn-abrir-formularios').style.display = 'none';
      var master = document.getElementById('resp-master');
      if (master) master.checked = false;
      cargarCobros();
      cargarTodo();
      return;
    }
    var p = pendientes[idx];
    var g = cobrosData[p.gi];
    enviarPagoRapido(g, p.monto, p.moneda, p.metodo, function() {
      registrados++;
      procesarSiguiente(idx + 1);
    });
    // Si hay error, enviarPagoRapido muestra alert — igual seguimos
  }
  procesarSiguiente(0);
}

function renderCobrosSemana(cont) {
  var semanas = {};
  // Agrupar clases por semana Y por responsable dentro de cada semana
  cobrosData.forEach(function(g) {
    g.alumnos.forEach(function(a) {
      a.clases.forEach(function(c) {
        var partes = c.fecha.split('-');
        var d = new Date(+partes[0], +partes[1]-1, +partes[2]);
        var lunes = new Date(d);
        lunes.setDate(d.getDate() - ((d.getDay() + 6) % 7));
        var key = lunes.toISOString().slice(0,10);
        if (!semanas[key]) semanas[key] = {lunes: lunes, grupos: {}};
        var resp = g.responsable;
        if (!semanas[key].grupos[resp]) {
          semanas[key].grupos[resp] = {
            gi: cobrosData.indexOf(g),
            responsable: resp,
            moneda: g.moneda,
            metodo: g.metodo_pago,
            monto_calculado: g.monto_calculado,
            precio_unitario: g.precio_unitario,
            items: []
          };
        }
        semanas[key].grupos[resp].items.push({
          alumno: a.nombre, alumno_id: a.alumno_id,
          clase_id: c.id, fecha: c.fecha, hora: c.hora,
          es_representante: g.es_representante
        });
      });
    });
  });

  var keys = Object.keys(semanas).sort();
  if (!keys.length) { cont.innerHTML = '<div class="empty">Todo cobrado</div>'; return; }

  var html = '<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;font-size:0.8rem;color:var(--text-muted)">'
    + '<input type="checkbox" id="sem-master" onchange="selectAllSemana(this)" style="width:15px;height:15px;cursor:pointer">'
    + '<label for="sem-master" style="cursor:pointer">Seleccionar todos</label></div>';

  var semIdx = 0;
  html += keys.map(function(key) {
    var sem = semanas[key];
    var domingo = new Date(sem.lunes); domingo.setDate(sem.lunes.getDate() + 6);
    var titulo = 'Semana del ' + sem.lunes.getDate() + '/' + (sem.lunes.getMonth()+1)
               + ' al ' + domingo.getDate() + '/' + (domingo.getMonth()+1);
    var totalItems = Object.values(sem.grupos).reduce(function(s,g){return s+g.items.length;},0);
    var respKeys = Object.keys(sem.grupos);
    var si = semIdx++;

    var gruposHtml = respKeys.map(function(resp) {
      var grupo = sem.grupos[resp];
      var n = grupo.items.length;
      var monto = grupo.precio_unitario ? Math.round(grupo.precio_unitario * n * 100)/100 : null;
      var montoStr = monto ? simMoneda(grupo.moneda) + fmt(monto) + ' ' + grupo.moneda : 'sin precio';
      var filas = grupo.items.map(function(it) {
        return '<div class="cobros-grupo-clases" style="padding-left:1.5rem">'
          + formatFecha(it.fecha) + ' ' + (it.hora||'')
          + ' \u2014 <strong>' + it.alumno + '</strong>'
          + (it.es_representante ? ' <span style="color:var(--text-muted);font-size:0.75rem">(' + resp + ')</span>' : '')
          + '</div>';
      }).join('');
      return '<div style="border-top:1px solid var(--bg2)">'
        + '<div style="display:flex;justify-content:space-between;align-items:center;padding:0.5rem 1rem">'
        + '<span style="font-size:0.83rem;font-weight:500">' + resp + '</span>'
        + '<span style="font-size:0.82rem;color:var(--gold-light)">' + montoStr + '</span>'
        + '</div>' + filas + '</div>';
    }).join('');

    // Guardar datos del grupo para poder registrar
    return '<div class="cobros-grupo" id="sem-grupo-' + si + '" data-sem-key="' + key + '">'
      + '<div class="cobros-grupo-header">'
      + '<div style="display:flex;align-items:center;gap:0.6rem">'
      + '<input type="checkbox" class="sem-check" data-si="' + si + '" data-key="' + key + '" '
      + 'onchange="actualizarBotonesSemana()" style="width:15px;height:15px;cursor:pointer">'
      + '<div><div class="cobros-grupo-titulo">' + titulo + '</div>'
      + '<div class="cobros-grupo-sub">' + totalItems + ' clase(s) \u2014 ' + respKeys.length + ' responsable(s)</div>'
      + '</div></div>'
      + '<button class="btn" onclick="abrirPagoSemana(' + si + ','' + key + '')">Registrar semana</button>'
      + '</div>'
      + gruposHtml
      + '<div class="cobros-inline-form cobros-sem-form" id="sem-form-' + si + '" style="display:none"></div>'
      + '</div>';
  }).join('');

  // Guardar mapa semanas para usar al registrar
  window._semanasData = semanas;
  cont.innerHTML = html;
}

function selectAllSemana(master) {
  document.querySelectorAll('.sem-check').forEach(function(c){ c.checked = master.checked; });
  actualizarBotonesSemana();
}

function actualizarBotonesSemana() {
  var checks = document.querySelectorAll('.sem-check:checked');
  var btnAbrir = document.getElementById('btn-abrir-formularios');
  var btnReg = document.getElementById('btn-registrar-abiertos');
  if (btnAbrir) btnAbrir.style.display = checks.length ? 'flex' : 'none';
  var hayAbiertos = document.querySelectorAll('.cobros-sem-form[style*="flex"]').length > 0;
  if (btnReg) btnReg.style.display = hayAbiertos ? 'flex' : 'none';
}

function abrirPagoSemana(si, key) {
  var sem = window._semanasData && window._semanasData[key];
  if (!sem) return;
  var form = document.getElementById('sem-form-' + si);
  if (!form) return;
  if (form.style.display !== 'none') { form.style.display = 'none'; return; }
  document.querySelectorAll('.cobros-sem-form').forEach(function(f){ f.style.display = 'none'; });

  // Un sub-formulario por responsable
  var html = '';
  Object.keys(sem.grupos).forEach(function(resp, ri) {
    var g = sem.grupos[resp];
    var n = g.items.length;
    var monto = g.precio_unitario ? Math.round(g.precio_unitario * n * 100)/100 : '';
    var metodosOpts = ['Wise','PayPal','Transferencia nacional'].map(function(m){
      return '<option' + (m===g.metodo?' selected':'') + '>' + m + '</option>';
    }).join('');
    var monedaOpts = ['D\u00f3lar','Libra Esterlina','Pesos'].map(function(m){
      return '<option' + (m===g.moneda?' selected':'') + '>' + m + '</option>';
    }).join('');
    html += '<div style="border-top:1px solid var(--bg2);padding:0.6rem 1rem 0">'
      + '<div style="font-size:0.8rem;font-weight:500;margin-bottom:0.4rem">' + resp + ' (' + n + ' clases)</div>'
      + '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:flex-end">'
      + '<div><label style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:0.2rem">Monto</label>'
      + '<input type="number" step="0.01" class="sem-monto-' + si + '" data-resp="' + resp + '" value="' + monto + '" style="width:110px;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:0.38rem 0.6rem;border-radius:4px;font-size:0.82rem"></div>'
      + '<div><label style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:0.2rem">Moneda</label>'
      + '<select class="sem-moneda-' + si + '" data-resp="' + resp + '" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:0.38rem 0.6rem;border-radius:4px;font-size:0.82rem">' + monedaOpts + '</select></div>'
      + '<div><label style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:0.2rem">M\u00e9todo</label>'
      + '<select class="sem-metodo-' + si + '" data-resp="' + resp + '" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:0.38rem 0.6rem;border-radius:4px;font-size:0.82rem">' + metodosOpts + '</select></div>'
      + '</div></div>';
  });
  html += '<div style="display:flex;gap:0.5rem;padding:0.75rem 1rem">'
    + '<button class="btn" onclick="confirmarPagoSemana(' + si + ','' + key + '')">\u2713 Confirmar todos</button>'
    + '<button class="btn cobros-sem-cancelar" data-si="' + si + '">Cancelar</button></div>';
  form.innerHTML = html;
  form.style.display = 'flex';
  form.style.flexDirection = 'column';
}

function confirmarPagoSemana(si, key) {
  var sem = window._semanasData && window._semanasData[key];
  if (!sem) return;
  var respKeys = Object.keys(sem.grupos);
  var pagos = [];
  var sinMonto = [];
  respKeys.forEach(function(resp) {
    var g = sem.grupos[resp];
    var montoEl = document.querySelector('.sem-monto-' + si + '[data-resp="' + resp + '"]');
    var monedaEl = document.querySelector('.sem-moneda-' + si + '[data-resp="' + resp + '"]');
    var metodoEl = document.querySelector('.sem-metodo-' + si + '[data-resp="' + resp + '"]');
    if (!montoEl) return;
    var monto = parseFloat(montoEl.value);
    if (!monto || isNaN(monto)) { sinMonto.push(resp); return; }
    var clase_ids = g.items.map(function(it){ return it.clase_id; });
    // Buscar gData en cobrosData
    var gData = cobrosData.find(function(x){ return x.responsable === resp; });
    if (!gData) return;
    var gMod = Object.assign({}, gData);
    gMod.total_clases = g.items.length;
    gMod.clase_ids = clase_ids;
    gMod.alumnos = g.items.reduce(function(acc, it) {
      var found = acc.find(function(x){ return x.alumno_id === it.alumno_id; });
      if (found) { found.clases.push({id: it.clase_id}); found.cantidad++; }
      else acc.push({alumno_id: it.alumno_id, nombre: it.alumno, clases: [{id: it.clase_id}], cantidad: 1});
      return acc;
    }, []);
    pagos.push({g: gMod, monto: monto, moneda: monedaEl.value, metodo: metodoEl.value});
  });
  if (sinMonto.length) alert('Sin monto: ' + sinMonto.join(', '));
  if (!pagos.length) return;
  var registrados = 0;
  function siguiente(i) {
    if (i >= pagos.length) {
      alert('\u2705 ' + registrados + ' pago(s) registrado(s).');
      cargarCobros(); cargarTodo(); return;
    }
    var p = pagos[i];
    enviarPagoRapido(p.g, p.monto, p.moneda, p.metodo, function(){ registrados++; siguiente(i+1); });
  }
  siguiente(0);
}

function renderCobrosChecks(cont) {
  var filas = [];
  cobrosData.forEach(function(g, gi) {
    g.alumnos.forEach(function(a) {
      a.clases.forEach(function(c) {
        var checkId = 'chk-' + gi + '-' + a.alumno_id + '-' + c.id;
        filas.push('<tr>'
          + '<td><input type="checkbox" class="cobro-check" id="' + checkId + '" '
          + 'data-clase-id="' + c.id + '" data-alumno-id="' + a.alumno_id + '" '
          + 'data-responsable="' + g.responsable + '" data-moneda="' + g.moneda + '" data-metodo="' + (g.metodo_pago||'') + '" '
          + 'onchange="actualizarSeleccion()"></td>'
          + '<td style="white-space:nowrap">' + formatFecha(c.fecha) + '</td>'
          + '<td>' + (c.hora||'-') + '</td>'
          + '<td><strong>' + a.nombre + '</strong>'
          + (g.es_representante ? '<br><span style="font-size:0.74rem;color:var(--text-muted)">' + g.responsable + '</span>' : '')
          + '</td>'
          + '<td><span class="badge badge-gold">' + g.moneda + '</span></td>'
          + '</tr>');
      });
    });
  });
  cont.innerHTML = '<div class="table-wrap"><table><thead><tr>'
    + '<th><input type="checkbox" onchange="selectAllChecks(this)"></th>'
    + '<th>Fecha</th><th>Hora</th><th>Alumno / Responsable</th><th>Moneda</th>'
    + '</tr></thead><tbody>' + filas.join('') + '</tbody></table></div>';
}

function selectAllChecks(master) {
  document.querySelectorAll('.cobro-check').forEach(function(c){ c.checked = master.checked; });
  actualizarSeleccion();
}

function actualizarSeleccion() {
  var checks = document.querySelectorAll('.cobro-check:checked');
  document.getElementById('btn-registrar-seleccion').style.display = checks.length ? 'flex' : 'none';
}

function registrarSeleccionChecks() {
  // Registra cada responsable seleccionado por separado, automáticamente
  var checks = document.querySelectorAll('.cobro-check:checked');
  if (!checks.length) return;
  var grupos = {};
  checks.forEach(function(c) {
    var resp = c.getAttribute('data-responsable');
    var aid = c.getAttribute('data-alumno-id');
    var cid = parseInt(c.getAttribute('data-clase-id'));
    if (!grupos[resp]) grupos[resp] = {alumnos: {}, moneda: c.getAttribute('data-moneda'), metodo: c.getAttribute('data-metodo')};
    if (!grupos[resp].alumnos[aid]) grupos[resp].alumnos[aid] = [];
    grupos[resp].alumnos[aid].push(cid);
  });
  var responsables = Object.keys(grupos);
  // Construir lista de pagos a registrar, uno por responsable
  var pagos = [];
  var sinPrecio = [];
  responsables.forEach(function(resp) {
    var gData = cobrosData.find(function(x){ return x.responsable === resp; });
    if (!gData) return;
    var alumnos = Object.entries(grupos[resp].alumnos).map(function(e){
      return {alumno_id: parseInt(e[0]), clase_ids: e[1]};
    });
    var totalClases = alumnos.reduce(function(s,a){return s+a.clase_ids.length;},0);
    var monto = gData.precio_unitario ? Math.round(gData.precio_unitario * totalClases * 100) / 100 : null;
    if (monto === null) { sinPrecio.push(resp); return; }
    // Reconstruir g con solo las clases seleccionadas
    var gMod = Object.assign({}, gData);
    gMod.total_clases = totalClases;
    gMod.clase_ids = alumnos.reduce(function(s,a){return s.concat(a.clase_ids);}, []);
    gMod.alumnos = alumnos.map(function(a) {
      var orig = gData.alumnos.find(function(x){ return x.alumno_id === a.alumno_id; }) || {};
      return Object.assign({}, orig, {clases: a.clase_ids.map(function(id){return {id:id};}), cantidad: a.clase_ids.length});
    });
    pagos.push({g: gMod, monto: monto, moneda: grupos[resp].moneda, metodo: grupos[resp].metodo, resp: resp});
  });
  if (sinPrecio.length) {
    alert('Sin precio cargado: ' + sinPrecio.join(', ') + '. Registralos manualmente desde "Por responsable".');
  }
  if (!pagos.length) return;
  var registrados = 0;
  function procesarSiguiente(idx) {
    if (idx >= pagos.length) {
      alert('\u2705 ' + registrados + ' pago(s) registrado(s) autom\u00e1ticamente.');
      cargarCobros(); cargarTodo(); return;
    }
    var p = pagos[idx];
    enviarPagoRapido(p.g, p.monto, p.moneda, p.metodo, function() {
      registrados++;
      procesarSiguiente(idx + 1);
    });
  }
  procesarSiguiente(0);
}

function abrirPago(gi) {
  var g = cobrosData[gi];
  var form = document.getElementById('cobro-form-' + gi);
  if (form.style.display !== 'none') { form.style.display = 'none'; return; }
  document.querySelectorAll('.cobros-inline-form').forEach(function(f){ f.style.display = 'none'; });
  var montoStr = g.monto_calculado || '';
  var metodosOptions = ['Wise','PayPal','Transferencia nacional'].map(function(m){
    return '<option' + (m===g.metodo_pago?' selected':'') + '>' + m + '</option>';
  }).join('');
  var monedaOptions = ['D\u00f3lar','Libra Esterlina','Pesos'].map(function(m){
    return '<option' + (m===g.moneda?' selected':'') + '>' + m + '</option>';
  }).join('');
  form.innerHTML = '<div><label>Monto</label><input type="number" step="0.01" class="cobro-monto-input" value="' + montoStr + '"></div>'
    + '<div><label>Moneda</label><select class="cobro-moneda-input">' + monedaOptions + '</select></div>'
    + '<div><label>M\u00e9todo</label><select class="cobro-metodo-input">' + metodosOptions + '</select></div>'
    + '<div style="display:flex;gap:0.4rem;align-self:flex-end">'
    + '<button class="btn" onclick="confirmarPagoInline(' + gi + ')">\u2713 Confirmar</button>'
    + '<button class="btn cobro-cancelar-btn" data-gi="' + gi + '">Cancelar</button>'
    + '</div>';
  form.style.display = 'flex';
}

function confirmarPagoInline(gi) {
  var g = cobrosData[gi];
  var form = document.getElementById('cobro-form-' + gi);
  var monto = parseFloat(form.querySelector('.cobro-monto-input').value);
  var moneda = form.querySelector('.cobro-moneda-input').value;
  var metodo = form.querySelector('.cobro-metodo-input').value;
  if (!monto || isNaN(monto)) { alert('Ingres\u00e1 un monto v\u00e1lido.'); return; }
  enviarPagoRapido(g, monto, moneda, metodo, function() {
    form.style.display = 'none';
    cargarCobros();
    cargarTodo();
  });
}

function abrirModalDirecto(responsable, alumnos, monto, moneda, metodo) {
  var gData = cobrosData.find(function(x){ return x.responsable === responsable; });
  window._modalPendiente = {responsable: responsable, alumnos: alumnos, gData: gData};
  document.getElementById('modal-titulo').textContent = 'Registrar pago \u2014 ' + responsable;
  var total = alumnos.reduce(function(s,a){return s+a.clase_ids.length;},0);
  document.getElementById('modal-detalle').textContent = total + ' clase(s) seleccionadas';
  document.getElementById('modal-monto').value = monto || '';
  document.getElementById('modal-moneda').value = moneda || 'D\u00f3lar';
  document.getElementById('modal-metodo').value = metodo || 'Wise';
  document.getElementById('cobros-modal').style.display = 'flex';
}

function cerrarModal() {
  document.getElementById('cobros-modal').style.display = 'none';
  window._modalPendiente = null;
}

function confirmarPagoModal() {
  if (!window._modalPendiente) return;
  var mp = window._modalPendiente;
  var monto = parseFloat(document.getElementById('modal-monto').value);
  var moneda = document.getElementById('modal-moneda').value;
  var metodo = document.getElementById('modal-metodo').value;
  if (!monto || isNaN(monto)) { alert('Ingres\u00e1 un monto v\u00e1lido.'); return; }
  if (!mp.gData) { cerrarModal(); return; }
  var gMod = Object.assign({}, mp.gData);
  gMod.alumnos = mp.alumnos.map(function(a) {
    var orig = mp.gData.alumnos.find(function(x){ return x.alumno_id === a.alumno_id; });
    return Object.assign({}, orig || {}, {clases: a.clase_ids.map(function(id){ return {id:id}; }), cantidad: a.clase_ids.length});
  });
  gMod.total_clases = mp.alumnos.reduce(function(s,a){return s+a.clase_ids.length;},0);
  gMod.clase_ids = mp.alumnos.reduce(function(s,a){return s.concat(a.clase_ids);}, []);
  enviarPagoRapido(gMod, monto, moneda, metodo, function() {
    cerrarModal();
    cargarCobros();
    cargarTodo();
  });
}

function enviarPagoRapido(g, monto, moneda, metodo, callback) {
  var totalClases = g.total_clases;
  var montoProp = {};
  g.alumnos.forEach(function(a) {
    montoProp[String(a.alumno_id)] = totalClases > 0 ? Math.round((monto * a.cantidad / totalClases) * 100) / 100 : monto;
  });
  var alumnosIds = g.alumnos.map(function(a){
    var cids = a.clases ? a.clases.map(function(c){ return typeof c === 'object' ? c.id : c; }) : [];
    return {alumno_id: a.alumno_id, clase_ids: cids};
  });
  fetch('/dashboard/api/registrar_pago_rapido', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      alumno_id: g.alumnos[0].alumno_id,
      clase_ids: g.clase_ids,
      monto: monto, moneda: moneda, metodo: metodo,
      alumnos_ids: alumnosIds,
      monto_proporcional: montoProp
    })
  }).then(function(r){ return r.json(); })
  .then(function(d) {
    if (d.ok) { callback(); }
    else { alert('Error: ' + (d.error || 'No se pudo registrar')); }
  }).catch(function(){ alert('Error de conexi\u00f3n.'); });
}

// ── FIN COBROS ────────────────────────────────────────────

function cargarUltimaSync() {
  fetch('/dashboard/api/ultima_sync').then(function(r){ return r.json(); }).then(function(d) {
    var el = document.getElementById('sync-info');
    if (d.ts) {
      el.innerHTML = '&#x23F1; ' + d.ts;
      el.title = 'Última sync: ' + d.meses.join(', ');
    } else {
      el.textContent = '';
    }
  }).catch(function(){});
}

function sincronizarCalendario() {
  ejecutarSync([{mes: mes, anio: anio}]);
}

function ejecutarSync(mesesLista) {
  var btn = document.getElementById('btn-sync');
  btn.disabled = true;
  btn.textContent = '\u23f3 Sincronizando...';
  fetch('/dashboard/api/sincronizar', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({meses: mesesLista})
  })
  .then(function(r){ return r.json(); })
  .then(function(d) {
    btn.disabled = false;
    btn.innerHTML = '&#128197; Sincronizar';
    if (d.ok) {
      var mesNombres = mesesLista.map(function(m){ return MESES_NOMBRES[m.mes] + ' ' + m.anio; }).join(', ');
      if (d.nuevos === 0 && d.cancelados === 0 && d.modificados === 0) {
        alert('\u2705 Sin cambios en: ' + mesNombres);
      } else {
        var partes = ['Sincronizaci\u00f3n \u2014 ' + mesNombres + ':'];
        if (d.nuevos > 0) partes.push('- ' + d.nuevos + ' clase(s) nueva(s)');
        if (d.cancelados > 0) partes.push('- ' + d.cancelados + ' clase(s) cancelada(s)');
        if (d.modificados > 0) partes.push('- ' + d.modificados + ' clase(s) modificada(s)');
        if (d.no_identificados && d.no_identificados.length > 0) {
          partes.push('Eventos sin identificar:');
          d.no_identificados.forEach(function(e){ partes.push(e); });
        }
        alert(partes.join(String.fromCharCode(10)));
      }
      cargarTodo();
    } else {
      alert('Error: ' + (d.error || 'No se pudo sincronizar'));
    }
  })
  .catch(function() {
    btn.disabled = false;
    btn.innerHTML = '&#128197; Sincronizar';
    alert('Error de conexi\u00f3n.');
  });
}

cargarTodo();
setInterval(cargarTodo, 60000);
</script>
</body>
</html>"""