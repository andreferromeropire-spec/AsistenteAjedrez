"""
dashboard_routes.py
===================
Rutas del dashboard web para Flask.
Se importa en bot.py con: from dashboard_routes import dashboard_bp

Acceso: https://tu-bot.railway.app/dashboard
Contraseña: variable de entorno DASHBOARD_PASSWORD (default: ajedrez2026)
"""

from flask import Blueprint, render_template_string, request, session, redirect, jsonify
from functools import wraps
from datetime import date
import os

from database import get_connection

dashboard_bp = Blueprint('dashboard', __name__)

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "ajedrez2026")


# ─────────────────────────────────────────────
# AUTENTICACIÓN
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('dashboard_logged_in'):
            return redirect('/dashboard/login')
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route('/dashboard/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['dashboard_logged_in'] = True
            return redirect('/dashboard')
        error = "Contraseña incorrecta"
    return render_template_string(LOGIN_HTML, error=error)


@dashboard_bp.route('/dashboard/logout')
def logout():
    session.pop('dashboard_logged_in', None)
    return redirect('/dashboard/login')


# ─────────────────────────────────────────────
# RUTA PRINCIPAL
# ─────────────────────────────────────────────
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_HTML)


# ─────────────────────────────────────────────
# API: CHAT WEB
# Recibe un mensaje de texto y lo pasa por el mismo
# intérprete y ejecutor que usa el bot de WhatsApp.
# ─────────────────────────────────────────────
@dashboard_bp.route('/dashboard/api/chat', methods=['POST'])
@login_required
def api_chat():
    """
    Recibe un mensaje del chat web y devuelve la respuesta del bot.
    Usa exactamente la misma lógica que el webhook de WhatsApp,
    así que todo lo que funciona en WhatsApp funciona acá también.
    """
    data = request.get_json()
    mensaje = data.get('mensaje', '').strip()
    historial = data.get('historial', [])

    if not mensaje:
        return jsonify({'respuesta': 'Escribí algo primero.'})

    try:
        from interprete import interpretar_mensaje
        # bot.py maneja acciones_pendientes por número de WhatsApp.
        # En el dashboard usamos un número fijo para la sesión web.
        numero_web = 'dashboard_web'

        # Importamos ejecutar_accion y acciones_pendientes desde bot
        import bot as bot_module
        acciones_pendientes = bot_module.acciones_pendientes

        accion = 'no_entiendo'
        datos = {}

        if numero_web in acciones_pendientes and mensaje.strip().isdigit():
            pendiente = acciones_pendientes[numero_web]
            if pendiente.get('accion') == 'confirmar_borrado':
                accion = 'confirmar_borrado'
                datos = {'numero_opcion': int(mensaje.strip())}
            else:
                accion = 'aclaracion_alumno'
                datos = {'numero_opcion': int(mensaje.strip())}
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
        return jsonify({'respuesta': f'Error: {str(e)}'})


# ─────────────────────────────────────────────
# API: DATOS (solo lectura)
# ─────────────────────────────────────────────

@dashboard_bp.route('/dashboard/api/resumen')
@login_required
def api_resumen():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    total_alumnos = conn.execute("SELECT COUNT(*) FROM alumnos WHERE activo=1").fetchone()[0]
    clases = conn.execute("""
        SELECT estado, COUNT(*) as n FROM clases
        WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        GROUP BY estado
    """, (f"{mes:02d}", str(anio))).fetchall()
    clases_dict = {r['estado']: r['n'] for r in clases}
    pagos = conn.execute("""
        SELECT moneda, SUM(monto) as total FROM pagos
        WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        GROUP BY moneda
    """, (f"{mes:02d}", str(anio))).fetchall()
    pagos_dict = {r['moneda']: r['total'] for r in pagos}
    conn.close()
    return jsonify({
        'total_alumnos': total_alumnos,
        'clases_agendadas': clases_dict.get('agendada', 0),
        'clases_canceladas': sum(v for k, v in clases_dict.items() if 'cancelada' in k),
        'pagos': pagos_dict
    })


@dashboard_bp.route('/dashboard/api/alumnos')
@login_required
def api_alumnos():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    alumnos = conn.execute("""
        SELECT a.id, a.nombre, a.representante, a.pais, a.moneda,
               a.metodo_pago, a.modalidad, a.whatsapp, a.mail, a.notas_recordatorio,
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
    alumno_id = request.args.get('alumno_id')
    conn = get_connection()
    query = """
        SELECT c.fecha, c.hora, c.estado, c.origen,
               a.nombre, a.pais, a.moneda, a.modalidad
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE strftime('%m',c.fecha)=? AND strftime('%Y',c.fecha)=?
        AND a.activo=1
    """
    params = [f"{mes:02d}", str(anio)]
    if alumno_id:
        query += " AND c.alumno_id=?"
        params.append(alumno_id)
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
        SELECT p.fecha, p.monto, p.moneda, p.metodo, p.notas, a.nombre, a.representante
        FROM pagos p
        JOIN alumnos a ON p.alumno_id = a.id
        WHERE strftime('%m',p.fecha)=? AND strftime('%Y',p.fecha)=?
        ORDER BY p.fecha DESC
    """, (f"{mes:02d}", str(anio))).fetchall()
    conn.close()
    return jsonify([dict(p) for p in pagos])


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
    resultado = []
    for d in deudores:
        clases = conn.execute("""
            SELECT COUNT(*) FROM clases
            WHERE alumno_id=? AND estado='agendada'
            AND strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        """, (d['id'], f"{mes:02d}", str(anio))).fetchone()[0]
        rangos = conn.execute("""
            SELECT * FROM promociones WHERE alumno_id=? ORDER BY clases_desde
        """, (d['id'],)).fetchall()
        precio = None
        moneda = d['moneda']
        for r in rangos:
            if r['clases_desde'] <= clases <= r['clases_hasta']:
                precio = r['precio_por_clase']
                moneda = r['moneda']
                break
        if precio is None and rangos:
            precio = rangos[-1]['precio_por_clase']
            moneda = rangos[-1]['moneda']
        resultado.append({
            'nombre': d['nombre'],
            'representante': d['representante'] or '—',
            'clases': clases,
            'precio_unitario': precio,
            'total': round(precio * clases, 2) if precio else None,
            'moneda': moneda
        })
    conn.close()
    return jsonify(resultado)


@dashboard_bp.route('/dashboard/api/grafico_clases')
@login_required
def api_grafico_clases():
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))
    conn = get_connection()
    datos = conn.execute("""
        SELECT a.nombre, COUNT(*) as total
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE c.estado = 'agendada'
        AND strftime('%m',c.fecha)=? AND strftime('%Y',c.fecha)=?
        AND a.activo=1
        GROUP BY a.nombre
        ORDER BY total DESC
    """, (f"{mes:02d}", str(anio))).fetchall()
    conn.close()
    return jsonify([dict(d) for d in datos])


# ─────────────────────────────────────────────
# LOGIN HTML
# ─────────────────────────────────────────────
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Ajedrez — Login</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'DM Sans', sans-serif;
    background: #f5f0e8;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #fff;
    border: 1px solid #e0d8cc;
    border-radius: 6px;
    padding: 3rem 2.5rem;
    width: 100%;
    max-width: 380px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.08);
  }
  .logo { text-align: center; margin-bottom: 2.5rem; }
  .logo .piece { font-size: 2.5rem; margin-bottom: 0.5rem; }
  .logo h1 { font-family: 'Playfair Display', serif; font-size: 1.4rem; color: #2c2416; }
  .logo p { color: #999; font-size: 0.8rem; margin-top: 0.3rem; letter-spacing: 0.1em; text-transform: uppercase; }
  label { display: block; color: #888; font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.5rem; }
  input[type=password] {
    width: 100%; background: #faf8f5; border: 1px solid #e0d8cc;
    border-radius: 4px; color: #2c2416; padding: 0.85rem 1rem;
    font-size: 1rem; font-family: 'DM Sans', sans-serif; outline: none; transition: border-color 0.2s;
  }
  input[type=password]:focus { border-color: #b48c50; }
  .error { color: #c0392b; font-size: 0.8rem; margin-top: 0.75rem; }
  button {
    width: 100%; margin-top: 1.5rem; background: #b48c50; color: #fff;
    border: none; border-radius: 4px; padding: 0.9rem;
    font-size: 0.85rem; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: background 0.2s;
  }
  button:hover { background: #9a7540; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="piece">♟️</div>
    <h1>Ajedrez Dashboard</h1>
    <p>Panel de gestión</p>
  </div>
  <form method="POST">
    <label for="password">Contraseña</label>
    <input type="password" id="password" name="password" placeholder="••••••••" autofocus>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <button type="submit">Ingresar</button>
  </form>
</div>
</body>
</html>'''


# ─────────────────────────────────────────────
# DASHBOARD HTML
# ─────────────────────────────────────────────
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Ajedrez</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  /* ── TEMAS ── */
  :root {
    --gold: #b48c50;
    --gold-light: #c9a060;
    --gold-dim: rgba(180,140,80,0.12);
    --green: #2e7d5e;
    --green-bg: rgba(46,125,94,0.1);
    --red: #b84040;
    --red-bg: rgba(184,64,64,0.1);
  }

  [data-theme="light"] {
    --bg: #f5f0e8;
    --bg2: #ece6d8;
    --surface: #ffffff;
    --surface2: #faf8f4;
    --border: #e0d8cc;
    --text: #2c2416;
    --text-dim: #8a7a68;
    --text-muted: #b0a090;
    --shadow: rgba(0,0,0,0.07);
  }

  [data-theme="dark"] {
    --bg: #0f0e0c;
    --bg2: #161411;
    --surface: #1a1816;
    --surface2: #201e1b;
    --border: #2e2b27;
    --text: #e8ddd0;
    --text-dim: #7a6f62;
    --text-muted: #4a4540;
    --shadow: rgba(0,0,0,0.4);
  }

  [data-theme="navy"] {
    --bg: #0a0f1a;
    --bg2: #0d1422;
    --surface: #111827;
    --surface2: #162035;
    --border: #1e2d45;
    --text: #c8d8f0;
    --text-dim: #5a7090;
    --text-muted: #2e4060;
    --shadow: rgba(0,0,0,0.5);
    --gold: #5b9bd5;
    --gold-light: #7ab8f0;
    --gold-dim: rgba(91,155,213,0.12);
    --green: #4a9e7a;
    --red: #c0524a;
  }

  html { font-size: 15px; }
  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    transition: background 0.25s, color 0.25s;
  }

  /* ── HEADER ── */
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.9rem 1.75rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 12px var(--shadow);
  }
  .header-left { display: flex; align-items: center; gap: 0.75rem; }
  .header-left h1 { font-family: 'Playfair Display', serif; font-size: 1.05rem; color: var(--gold-light); }
  .header-right { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }

  select, .btn {
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    padding: 0.4rem 0.75rem; border-radius: 4px;
    font-family: 'DM Sans', sans-serif; font-size: 0.82rem; cursor: pointer; outline: none;
    transition: border-color 0.2s, background 0.2s;
  }
  select:focus, .btn:hover { border-color: var(--gold); }
  .btn { display: flex; align-items: center; gap: 0.35rem; }

  /* Theme switcher */
  .theme-group { display: flex; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
  .theme-btn {
    background: var(--surface2); border: none; color: var(--text-dim);
    padding: 0.4rem 0.6rem; cursor: pointer; font-size: 0.85rem;
    transition: background 0.15s, color 0.15s;
    border-right: 1px solid var(--border);
  }
  .theme-btn:last-child { border-right: none; }
  .theme-btn.active { background: var(--gold-dim); color: var(--gold-light); }
  .theme-btn:hover:not(.active) { background: var(--border); }

  /* ── MAIN ── */
  main { padding: 1.5rem 1.75rem; max-width: 1440px; margin: 0 auto; }

  /* ── MÉTRICAS ── */
  .metrics {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1px; background: var(--border);
    border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 8px var(--shadow);
  }
  .metric { background: var(--surface); padding: 1.1rem 1.25rem; }
  .metric-label { font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.3rem; }
  .metric-value { font-size: 1.6rem; font-weight: 300; color: var(--gold-light); line-height: 1; }
  .metric-value.green { color: var(--green); }
  .metric-value.red { color: var(--red); }

  /* ── LAYOUT CON SIDEBAR DE CHAT ── */
  .main-layout { display: grid; grid-template-columns: 1fr 340px; gap: 1.25rem; align-items: start; }
  @media (max-width: 1024px) { .main-layout { grid-template-columns: 1fr; } }

  /* ── TABS ── */
  .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: 1.25rem; overflow-x: auto; }
  .tab-btn {
    background: none; border: none; color: var(--text-dim);
    padding: 0.7rem 1.1rem; font-family: 'DM Sans', sans-serif; font-size: 0.82rem;
    cursor: pointer; white-space: nowrap; border-bottom: 2px solid transparent;
    transition: all 0.15s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--gold-light); border-bottom-color: var(--gold); }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* ── TABLAS ── */
  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 5px; box-shadow: 0 1px 4px var(--shadow); }
  table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
  thead { background: var(--surface2); }
  th { padding: 0.65rem 0.9rem; text-align: left; font-size: 0.67rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border); }
  td { padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--bg2); color: var(--text); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--gold-dim); }

  /* ── BADGES ── */
  .badge { display: inline-block; padding: 0.18rem 0.5rem; border-radius: 3px; font-size: 0.68rem; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; }
  .badge-green { background: var(--green-bg); color: var(--green); }
  .badge-red { background: var(--red-bg); color: var(--red); }
  .badge-gold { background: var(--gold-dim); color: var(--gold-light); }
  .badge-gray { background: var(--bg2); color: var(--text-dim); }

  /* ── FILTROS ── */
  .filters { display: flex; gap: 0.6rem; margin-bottom: 1rem; flex-wrap: wrap; align-items: center; }
  .filters input[type=text] {
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    padding: 0.38rem 0.75rem; border-radius: 4px;
    font-family: 'DM Sans', sans-serif; font-size: 0.83rem; outline: none; width: 200px;
  }
  .filters input:focus { border-color: var(--gold); }

  /* ── GRID 2 ── */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }
  @media (max-width: 800px) { .grid-2 { grid-template-columns: 1fr; } }

  /* ── CHART BOX ── */
  .chart-box { background: var(--surface); border: 1px solid var(--border); border-radius: 5px; padding: 1.25rem; box-shadow: 0 1px 4px var(--shadow); }
  .chart-box h3 { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem; }

  /* ── TOTALES ── */
  .totals-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.75rem; }
  .total-chip { background: var(--surface2); border: 1px solid var(--border); border-radius: 4px; padding: 0.45rem 0.9rem; font-size: 0.82rem; }
  .total-chip span { color: var(--gold-light); font-weight: 500; }

  /* ── EMPTY / LOADING ── */
  .empty { padding: 2.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem; }

  /* ──────────────────────────────────────
     CHAT WEB
     Panel de chat lateral que conecta con
     el mismo intérprete del bot de WhatsApp.
     ────────────────────────────────────── */
  .chat-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    display: flex; flex-direction: column;
    height: calc(100vh - 100px);
    position: sticky; top: 80px;
    box-shadow: 0 2px 12px var(--shadow);
    overflow: hidden;
  }
  .chat-header {
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--border);
    background: var(--surface2);
    display: flex; align-items: center; gap: 0.5rem;
  }
  .chat-header h3 { font-size: 0.85rem; color: var(--text); font-weight: 500; }
  .chat-header p { font-size: 0.72rem; color: var(--text-muted); margin-top: 0.1rem; }
  .chat-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; flex-shrink: 0; }

  .chat-messages {
    flex: 1; overflow-y: auto; padding: 1rem;
    display: flex; flex-direction: column; gap: 0.75rem;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar { width: 4px; }
  .chat-messages::-webkit-scrollbar-track { background: transparent; }
  .chat-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* Burbuja de mensaje */
  .msg { max-width: 88%; display: flex; flex-direction: column; gap: 0.2rem; }
  .msg.user { align-self: flex-end; align-items: flex-end; }
  .msg.bot { align-self: flex-start; align-items: flex-start; }

  .msg-bubble {
    padding: 0.6rem 0.85rem; border-radius: 12px;
    font-size: 0.83rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word;
  }
  .msg.user .msg-bubble { background: var(--gold); color: #fff; border-bottom-right-radius: 3px; }
  .msg.bot .msg-bubble { background: var(--surface2); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 3px; }

  .msg-time { font-size: 0.65rem; color: var(--text-muted); padding: 0 0.2rem; }

  /* Indicador de escritura */
  .typing { display: none; align-self: flex-start; }
  .typing.visible { display: flex; }
  .typing-bubble { background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; border-bottom-left-radius: 3px; padding: 0.6rem 0.85rem; display: flex; gap: 4px; align-items: center; }
  .typing-dot { width: 6px; height: 6px; background: var(--text-muted); border-radius: 50%; animation: bounce 1.2s infinite; }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%,60%,100% { transform: translateY(0); } 30% { transform: translateY(-5px); } }

  .chat-input-area {
    padding: 0.75rem;
    border-top: 1px solid var(--border);
    display: flex; gap: 0.5rem;
    background: var(--surface);
  }
  .chat-input {
    flex: 1; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 0.55rem 0.85rem;
    border-radius: 20px; font-family: 'DM Sans', sans-serif; font-size: 0.85rem;
    outline: none; resize: none; max-height: 100px;
    transition: border-color 0.2s;
  }
  .chat-input:focus { border-color: var(--gold); }
  .chat-send {
    background: var(--gold); color: #fff; border: none;
    border-radius: 50%; width: 36px; height: 36px; flex-shrink: 0;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    font-size: 1rem; transition: background 0.15s; align-self: flex-end;
  }
  .chat-send:hover { background: var(--gold-light); }
  .chat-send:disabled { background: var(--border); cursor: not-allowed; }

  .chat-hint { font-size: 0.7rem; color: var(--text-muted); padding: 0 0.75rem 0.4rem; line-height: 1.4; }

  /* Sección title */
  .section-title {
    font-family: 'Playfair Display', serif; font-size: 0.95rem; color: var(--gold-light);
    margin-bottom: 0.9rem; display: flex; align-items: center; gap: 0.5rem;
  }
  .section-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }
  .section { margin-bottom: 1.75rem; }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <span style="font-size:1.4rem">♟️</span>
    <h1>Ajedrez Dashboard</h1>
  </div>
  <div class="header-right">
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

    <!-- Selector de tema -->
    <div class="theme-group" title="Cambiar tema">
      <button class="theme-btn active" onclick="setTheme('light', this)" title="Claro">☀️</button>
      <button class="theme-btn" onclick="setTheme('dark', this)" title="Oscuro">🌙</button>
      <button class="theme-btn" onclick="setTheme('navy', this)" title="Azul marino">🌊</button>
    </div>

    <button class="btn" onclick="cargarTodo()">↻ Actualizar</button>
    <a href="/dashboard/logout"><button class="btn">Salir</button></a>
  </div>
</header>

<main>
  <!-- MÉTRICAS -->
  <div class="metrics" id="metrics">
    <div class="metric"><div class="metric-label">Alumnos activos</div><div class="metric-value" id="m-alumnos">—</div></div>
    <div class="metric"><div class="metric-label">Clases agendadas</div><div class="metric-value" id="m-clases">—</div></div>
    <div class="metric"><div class="metric-label">Canceladas</div><div class="metric-value red" id="m-canceladas">—</div></div>
    <div class="metric"><div class="metric-label">Cobrado USD 💵</div><div class="metric-value green" id="m-usd">—</div></div>
    <div class="metric"><div class="metric-label">Cobrado £</div><div class="metric-value green" id="m-gbp">—</div></div>
    <div class="metric"><div class="metric-label">Cobrado ARS</div><div class="metric-value green" id="m-ars">—</div></div>
  </div>

  <!-- LAYOUT PRINCIPAL: datos + chat -->
  <div class="main-layout">

    <!-- COLUMNA IZQUIERDA: datos -->
    <div>
      <div class="tabs">
        <button class="tab-btn active" onclick="showTab('clases', this)">📅 Clases</button>
        <button class="tab-btn" onclick="showTab('pagos', this)">💰 Pagos</button>
        <button class="tab-btn" onclick="showTab('deuda', this)">❌ Deuda</button>
        <button class="tab-btn" onclick="showTab('alumnos', this)">👥 Alumnos</button>
        <button class="tab-btn" onclick="showTab('graficos', this)">📈 Gráficos</button>
      </div>

      <!-- CLASES -->
      <div class="tab-panel active" id="tab-clases">
        <div class="filters">
          <input type="text" placeholder="🔍 Buscar alumno..." oninput="filtrarTabla('t-clases', this.value)">
          <select id="filtro-estado" onchange="cargarClases()">
            <option value="">Todos los estados</option>
            <option value="agendada">Agendada</option>
            <option value="cancelada">Cancelada</option>
          </select>
        </div>
        <div class="table-wrap">
          <table><thead><tr><th>Fecha</th><th>Hora</th><th>Alumno</th><th>Estado</th><th>Origen</th><th>País</th></tr></thead>
          <tbody id="t-clases"><tr><td colspan="6" class="empty">Cargando...</td></tr></tbody></table>
        </div>
      </div>

      <!-- PAGOS -->
      <div class="tab-panel" id="tab-pagos">
        <div class="section">
          <div class="section-title">Pagos registrados</div>
          <div class="filters">
            <input type="text" placeholder="🔍 Buscar..." oninput="filtrarTabla('t-pagos', this.value)">
          </div>
          <div class="table-wrap">
            <table><thead><tr><th>Fecha</th><th>Alumno</th><th>Monto</th><th>Moneda</th><th>Método</th><th>Notas</th></tr></thead>
            <tbody id="t-pagos"><tr><td colspan="6" class="empty">Cargando...</td></tr></tbody></table>
          </div>
          <div class="totals-row" id="totales-pagos"></div>
        </div>
      </div>

      <!-- DEUDA -->
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

      <!-- ALUMNOS -->
      <div class="tab-panel" id="tab-alumnos">
        <div class="filters">
          <input type="text" placeholder="🔍 Buscar nombre o representante..." oninput="filtrarTabla('t-alumnos', this.value)">
        </div>
        <div class="table-wrap">
          <table><thead><tr><th>Nombre</th><th>Representante</th><th>País</th><th>Moneda</th><th>Método</th><th>Modalidad</th><th>Clases mes</th><th>Pagó</th></tr></thead>
          <tbody id="t-alumnos"><tr><td colspan="8" class="empty">Cargando...</td></tr></tbody></table>
        </div>
      </div>

      <!-- GRÁFICOS -->
      <div class="tab-panel" id="tab-graficos">
        <div class="grid-2">
          <div class="chart-box"><h3>Clases por alumno</h3><canvas id="chart-alumnos" height="280"></canvas></div>
          <div class="chart-box"><h3>Distribución por país</h3><canvas id="chart-paises" height="280"></canvas></div>
        </div>
      </div>
    </div>

    <!-- COLUMNA DERECHA: CHAT WEB -->
    <div class="chat-panel">
      <div class="chat-header">
        <div class="chat-dot"></div>
        <div>
          <h3>Asistente ♟️</h3>
          <p>Mismo bot que WhatsApp</p>
        </div>
      </div>

      <div class="chat-messages" id="chat-messages">
        <div class="msg bot">
          <div class="msg-bubble">¡Hola! Soy el mismo bot de WhatsApp. Puedo registrar pagos, clases, consultar deudas... lo que necesites 🙂</div>
          <div class="msg-time">ahora</div>
        </div>
      </div>

      <div class="typing" id="typing">
        <div class="typing-bubble">
          <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
        </div>
      </div>

      <p class="chat-hint">Ejemplos: "pagó Grace $100 dólares por Wise", "di clase con Lucas hoy", "quién debe este mes"</p>

      <div class="chat-input-area">
        <textarea class="chat-input" id="chat-input" placeholder="Escribí tu mensaje..." rows="1"
          onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault();enviarMensaje()}"
          oninput="autoResize(this)"></textarea>
        <button class="chat-send" id="chat-send" onclick="enviarMensaje()">➤</button>
      </div>
    </div>

  </div><!-- /main-layout -->
</main>

<script>
{% raw %}
// ════════════════════════════════════════════
// TEMA
// ════════════════════════════════════════════
function setTheme(tema, btn) {
  document.documentElement.setAttribute('data-theme', tema);
  localStorage.setItem('dashboard-theme', tema);
  document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  // Regenerar gráficos con colores del tema nuevo
  if (document.getElementById('tab-graficos').classList.contains('active')) {
    cargarGraficos();
  }
}

// Aplicar tema guardado al cargar
(function() {
  const saved = localStorage.getItem('dashboard-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  const btns = { light: 0, dark: 1, navy: 2 };
  const btn = document.querySelectorAll('.theme-btn')[btns[saved]];
  if (btn) btn.classList.add('active');
  else document.querySelectorAll('.theme-btn')[0].classList.add('active');
})();


// ════════════════════════════════════════════
// ESTADO
// ════════════════════════════════════════════
let mes = new Date().getMonth() + 1;
let anio = new Date().getFullYear();
let charts = {};
let chatHistorial = [];

document.getElementById('sel-mes').value = mes;
document.getElementById('sel-anio').value = anio;
document.getElementById('sel-mes').addEventListener('change', () => { mes = +document.getElementById('sel-mes').value; cargarTodo(); });
document.getElementById('sel-anio').addEventListener('change', () => { anio = +document.getElementById('sel-anio').value; cargarTodo(); });


// ════════════════════════════════════════════
// CHAT
// ════════════════════════════════════════════
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function ahora() {
  return new Date().toLocaleTimeString('es-AR', {hour:'2-digit', minute:'2-digit'});
}

function agregarMensaje(texto, tipo) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `msg ${tipo}`;
  div.innerHTML = `<div class="msg-bubble">${texto.replace(/\n/g,'<br>')}</div><div class="msg-time">${ahora()}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

async function enviarMensaje() {
  const input = document.getElementById('chat-input');
  const texto = input.value.trim();
  if (!texto) return;

  agregarMensaje(texto, 'user');
  chatHistorial.push({role: 'user', content: texto});
  input.value = '';
  input.style.height = 'auto';

  // Mostrar indicador de escritura
  const typing = document.getElementById('typing');
  const container = document.getElementById('chat-messages');
  typing.classList.add('visible');
  container.appendChild(typing);
  container.scrollTop = container.scrollHeight;

  const btn = document.getElementById('chat-send');
  btn.disabled = true;

  try {
    const res = await fetch('/dashboard/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mensaje: texto, historial: chatHistorial.slice(-10)})
    });
    const data = await res.json();
    typing.classList.remove('visible');
    agregarMensaje(data.respuesta, 'bot');
    chatHistorial.push({role: 'assistant', content: data.respuesta});

    // Si el bot modificó datos, refrescamos las métricas automáticamente
    const palabrasAccion = ['registré','pagó','agendé','cancelé','actualicé','borré','agregué'];
    if (palabrasAccion.some(p => data.respuesta.toLowerCase().includes(p))) {
      setTimeout(cargarTodo, 800);
    }
  } catch(e) {
    typing.classList.remove('visible');
    agregarMensaje('Error de conexión. Intentá de nuevo.', 'bot');
  }

  btn.disabled = false;
  input.focus();
}


// ════════════════════════════════════════════
// API HELPERS
// ════════════════════════════════════════════
async function api(ruta) {
  const res = await fetch(`/dashboard/api/${ruta}?mes=${mes}&anio=${anio}`);
  return res.json();
}

function fmt(n) { return Number(n).toLocaleString('es-AR'); }

function estadoBadge(e) {
  const m = {
    'agendada': '<span class="badge badge-gold">Agendada</span>',
    'cancelada_con_anticipacion': '<span class="badge badge-gray">Cancelada ✓</span>',
    'cancelada_sin_anticipacion': '<span class="badge badge-red">Cancelada ✗</span>',
    'cancelada_por_profesora': '<span class="badge badge-gray">Cancelada (prof)</span>',
    'dada': '<span class="badge badge-green">Dada</span>'
  };
  return m[e] || e;
}


// ════════════════════════════════════════════
// CARGAR DATOS
// ════════════════════════════════════════════
function cargarTodo() {
  cargarResumen();
  cargarClases();
  cargarPagos();
  cargarDeudores();
  cargarAlumnos();
}

async function cargarResumen() {
  const d = await api('resumen');
  document.getElementById('m-alumnos').textContent = d.total_alumnos;
  document.getElementById('m-clases').textContent = d.clases_agendadas;
  document.getElementById('m-canceladas').textContent = d.clases_canceladas;
  document.getElementById('m-usd').textContent = d.pagos['Dólar'] ? '$' + fmt(d.pagos['Dólar']) : '—';
  document.getElementById('m-gbp').textContent = d.pagos['Libra Esterlina'] ? '£' + fmt(d.pagos['Libra Esterlina']) : '—';
  document.getElementById('m-ars').textContent = d.pagos['Pesos'] ? '$' + fmt(d.pagos['Pesos']) : '—';
}

async function cargarClases() {
  const estadoFiltro = document.getElementById('filtro-estado').value;
  let datos = await api('clases');
  if (estadoFiltro) datos = datos.filter(c => c.estado.includes(estadoFiltro));
  const html = datos.length ? datos.map(c => `<tr>
    <td>${c.fecha}</td><td>${c.hora||'—'}</td>
    <td><strong>${c.nombre}</strong></td>
    <td>${estadoBadge(c.estado)}</td>
    <td style="color:var(--text-muted);font-size:0.78rem">${c.origen}</td>
    <td>${c.pais||'—'}</td></tr>`).join('')
    : '<tr><td colspan="6" class="empty">Sin clases en este período</td></tr>';
  document.getElementById('t-clases').innerHTML = html;
}

async function cargarPagos() {
  const datos = await api('pagos');
  const monedas = {};
  const html = datos.length ? datos.map(p => {
    monedas[p.moneda] = (monedas[p.moneda]||0) + p.monto;
    const sim = p.moneda==='Dólar'?'$':p.moneda==='Libra Esterlina'?'£':'$';
    return `<tr>
      <td>${p.fecha}</td>
      <td><strong>${p.nombre}</strong>${p.representante&&p.representante!=='-'?`<br><span style="color:var(--text-muted);font-size:0.75rem">${p.representante}</span>`:''}</td>
      <td>${sim}${fmt(p.monto)}</td>
      <td><span class="badge badge-gold">${p.moneda}</span></td>
      <td>${p.metodo||'—'}</td>
      <td style="color:var(--text-muted);font-size:0.78rem">${p.notas||'—'}</td></tr>`;
  }).join('') : '<tr><td colspan="6" class="empty">Sin pagos registrados</td></tr>';
  document.getElementById('t-pagos').innerHTML = html;
  document.getElementById('totales-pagos').innerHTML = Object.entries(monedas).map(([m,t]) => {
    const s = m==='Dólar'?'$':m==='Libra Esterlina'?'£':'$';
    return `<div class="total-chip">Total ${m}: <span>${s}${fmt(t)}</span></div>`;
  }).join('');
}

async function cargarDeudores() {
  const datos = await api('deudores');
  const porCobrar = {};
  const html = datos.length ? datos.map(d => {
    if(d.total&&d.moneda) porCobrar[d.moneda]=(porCobrar[d.moneda]||0)+d.total;
    const sim = d.moneda==='Dólar'?'$':d.moneda==='Libra Esterlina'?'£':'$';
    return `<tr>
      <td><strong>${d.nombre}</strong></td><td>${d.representante}</td>
      <td>${d.clases}</td>
      <td>${d.precio_unitario?sim+fmt(d.precio_unitario):'—'}</td>
      <td>${d.total?'<strong>'+sim+fmt(d.total)+'</strong>':'—'}</td>
      <td><span class="badge badge-gold">${d.moneda}</span></td></tr>`;
  }).join('') : '<tr><td colspan="6" class="empty" style="color:var(--green)">🎉 Todos pagaron este mes</td></tr>';
  document.getElementById('t-deuda').innerHTML = html;
  document.getElementById('totales-deuda').innerHTML = Object.entries(porCobrar).map(([m,t]) => {
    const s = m==='Dólar'?'$':m==='Libra Esterlina'?'£':'$';
    return `<div class="total-chip">Por cobrar ${m}: <span>${s}${fmt(t)}</span></div>`;
  }).join('') || '<span style="color:var(--text-muted);font-size:0.82rem">Sin deuda pendiente</span>';
}

async function cargarAlumnos() {
  const datos = await api('alumnos');
  const html = datos.map(a => `<tr>
    <td><strong>${a.nombre}</strong></td>
    <td>${a.representante||'—'}</td>
    <td>${a.pais||'—'}</td>
    <td><span class="badge badge-gold">${a.moneda||'—'}</span></td>
    <td style="font-size:0.78rem;color:var(--text-muted)">${a.metodo_pago||'—'}</td>
    <td style="font-size:0.78rem;color:var(--text-muted)">${a.modalidad||'—'}</td>
    <td style="text-align:center">${a.clases_mes}</td>
    <td style="text-align:center">${a.pago_este_mes?'<span class="badge badge-green">✓</span>':'<span class="badge badge-red">✗</span>'}</td>
  </tr>`).join('');
  document.getElementById('t-alumnos').innerHTML = html || '<tr><td colspan="8" class="empty">Sin alumnos</td></tr>';
}

async function cargarGraficos() {
  const datos = await api('grafico_clases');
  const clases = await api('clases');

  const isDark = ['dark','navy'].includes(document.documentElement.getAttribute('data-theme'));
  const tickColor = isDark ? '#7a6f62' : '#9a8a78';
  const gridColor = isDark ? '#1e1c1a' : '#ece6d8';

  if (charts.alumnos) charts.alumnos.destroy();
  charts.alumnos = new Chart(document.getElementById('chart-alumnos').getContext('2d'), {
    type: 'bar',
    data: {
      labels: datos.map(d => d.nombre),
      datasets: [{ data: datos.map(d => d.total), backgroundColor: 'rgba(180,140,80,0.55)', borderColor: '#b48c50', borderWidth: 1, borderRadius: 3 }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: tickColor }, grid: { color: gridColor } },
        y: { ticks: { color: tickColor }, grid: { display: false } }
      }
    }
  });

  const paises = {};
  clases.filter(c => c.estado==='agendada').forEach(c => {
    const p = c.pais||'Sin datos'; paises[p]=(paises[p]||0)+1;
  });
  if (charts.paises) charts.paises.destroy();
  charts.paises = new Chart(document.getElementById('chart-paises').getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(paises),
      datasets: [{ data: Object.values(paises), backgroundColor: ['#b48c50','#4a9e7a','#c0524a','#5b8db8','#9b7fc8','#d4a853'], borderWidth: 0 }]
    },
    options: {
      plugins: { legend: { labels: { color: tickColor, font: { size: 11 } } } },
      cutout: '58%'
    }
  });
}

// ════════════════════════════════════════════
// TABS
// ════════════════════════════════════════════
function showTab(id, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  if (btn) btn.classList.add('active');
  if (id === 'graficos') cargarGraficos();
}

// ════════════════════════════════════════════
// FILTRO EN TIEMPO REAL
// ════════════════════════════════════════════
function filtrarTabla(tablaId, texto) {
  document.querySelectorAll(`#${tablaId} tr`).forEach(f => {
    f.style.display = f.textContent.toLowerCase().includes(texto.toLowerCase()) ? '' : 'none';
  });
}

// ════════════════════════════════════════════
// INICIO
// ════════════════════════════════════════════
cargarTodo();
setInterval(cargarTodo, 60000);
{% endraw %}
</script>
</body>
</html>'''