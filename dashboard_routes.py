"""
dashboard_routes.py
===================
Rutas del dashboard web para Flask.
Se importa en bot.py con: from dashboard_routes import dashboard_bp

Acceso: https://tu-bot.railway.app/dashboard
Sin contraseña — la URL de Railway ya es suficiente protección.
"""

from flask import Blueprint, render_template_string, request, jsonify
from datetime import date
import os

from database import get_connection

dashboard_bp = Blueprint('dashboard', __name__)


# ─────────────────────────────────────────────
# RUTA PRINCIPAL DEL DASHBOARD
# ─────────────────────────────────────────────
@dashboard_bp.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@dashboard_bp.route('/dashboard/api/resumen')
def api_resumen():
    """Métricas generales del mes seleccionado."""
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))

    conn = get_connection()

    # Total alumnos activos
    total_alumnos = conn.execute("SELECT COUNT(*) FROM alumnos WHERE activo=1").fetchone()[0]

    # Clases del mes
    clases = conn.execute("""
        SELECT estado, COUNT(*) as n FROM clases
        WHERE strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        GROUP BY estado
    """, (f"{mes:02d}", str(anio))).fetchall()
    clases_dict = {r['estado']: r['n'] for r in clases}

    # Pagos del mes
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
def api_alumnos():
    """Lista de alumnos activos con sus clases del mes."""
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
def api_clases():
    """Clases del mes con filtros opcionales."""
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
def api_pagos():
    """Pagos del mes."""
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
def api_deudores():
    """Alumnos mensuales que no pagaron este mes, con monto calculado."""
    mes = int(request.args.get('mes', date.today().month))
    anio = int(request.args.get('anio', date.today().year))

    conn = get_connection()

    # Alumnos mensuales que NO pagaron
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
        # Contar clases del mes
        clases = conn.execute("""
            SELECT COUNT(*) FROM clases
            WHERE alumno_id=? AND estado='agendada'
            AND strftime('%m',fecha)=? AND strftime('%Y',fecha)=?
        """, (d['id'], f"{mes:02d}", str(anio))).fetchone()[0]

        # Buscar promo correspondiente
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
def api_grafico_clases():
    """Datos para el gráfico de clases por alumno."""
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
# HTML DE LA PÁGINA DE LOGIN
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# HTML DEL DASHBOARD
# ─────────────────────────────────────────────
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Ajedrez</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --gold: #b48c50;
    --gold-light: #e8d5a3;
    --gold-dim: rgba(180,140,80,0.15);
    --bg: #0d0d0d;
    --surface: #141414;
    --surface2: #1a1a1a;
    --border: #242424;
    --text: #d4c5a0;
    --text-dim: #666;
    --text-muted: #444;
    --green: #4caf87;
    --red: #c0624a;
  }

  html { font-size: 15px; }
  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* HEADER */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 2rem;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    position: sticky; top: 0; z-index: 100;
  }
  .header-left { display: flex; align-items: center; gap: 0.75rem; }
  .header-left .piece { font-size: 1.5rem; }
  .header-left h1 {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    color: var(--gold-light);
    letter-spacing: 0.03em;
  }
  .header-right { display: flex; align-items: center; gap: 1rem; }

  /* SELECTORES */
  select {
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 0.75rem;
    border-radius: 3px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    cursor: pointer;
    outline: none;
  }
  select:focus { border-color: var(--gold); }

  .btn-logout {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    padding: 0.4rem 0.9rem;
    border-radius: 3px;
    font-size: 0.8rem;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.05em;
    transition: all 0.2s;
  }
  .btn-logout:hover { border-color: var(--gold); color: var(--gold); }

  /* LAYOUT PRINCIPAL */
  main { padding: 2rem; max-width: 1400px; margin: 0 auto; }

  /* MÉTRICAS */
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; margin-bottom: 2rem; }
  .metric {
    background: var(--surface);
    padding: 1.25rem 1.5rem;
    display: flex; flex-direction: column; gap: 0.3rem;
  }
  .metric-label { font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.12em; }
  .metric-value { font-size: 1.75rem; font-weight: 300; color: var(--gold-light); line-height: 1; }
  .metric-value.green { color: var(--green); }
  .metric-value.red { color: var(--red); }
  .metric-sub { font-size: 0.75rem; color: var(--text-muted); }

  /* TABS */
  .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 2rem; }
  .tab-btn {
    background: none; border: none; color: var(--text-dim);
    padding: 0.75rem 1.25rem;
    font-family: 'DM Sans', sans-serif; font-size: 0.85rem;
    cursor: pointer; letter-spacing: 0.05em;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--gold-light); border-bottom-color: var(--gold); }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* TABLAS */
  .table-wrapper { overflow-x: auto; border: 1px solid var(--border); border-radius: 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  thead { background: var(--surface2); }
  th {
    padding: 0.75rem 1rem; text-align: left;
    font-size: 0.7rem; color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 0.1em;
    font-weight: 500; white-space: nowrap;
    border-bottom: 1px solid var(--border);
  }
  td { padding: 0.7rem 1rem; border-bottom: 1px solid #1a1a1a; color: var(--text); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(180,140,80,0.04); }

  /* BADGES */
  .badge {
    display: inline-block; padding: 0.2rem 0.55rem;
    border-radius: 2px; font-size: 0.7rem; font-weight: 500;
    letter-spacing: 0.05em; text-transform: uppercase;
  }
  .badge-green { background: rgba(76,175,135,0.15); color: var(--green); }
  .badge-red { background: rgba(192,98,74,0.15); color: var(--red); }
  .badge-gold { background: var(--gold-dim); color: var(--gold); }
  .badge-gray { background: rgba(255,255,255,0.06); color: var(--text-dim); }

  /* GRID 2 COLUMNAS */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }

  /* SECCIÓN */
  .section { margin-bottom: 2rem; }
  .section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1rem; color: var(--gold-light);
    margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;
  }
  .section-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }

  /* GRÁFICO */
  .chart-box {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; padding: 1.5rem;
  }
  .chart-box h3 { font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1.25rem; }

  /* LOADING */
  .loading { color: var(--text-muted); font-size: 0.85rem; padding: 2rem; text-align: center; }

  /* FILTROS */
  .filters { display: flex; gap: 0.75rem; margin-bottom: 1.25rem; flex-wrap: wrap; align-items: center; }
  .filters input[type=text] {
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 0.4rem 0.75rem;
    border-radius: 3px; font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem; outline: none; width: 220px;
  }
  .filters input:focus { border-color: var(--gold); }
  .filter-label { font-size: 0.75rem; color: var(--text-dim); }

  /* TOTALES */
  .totals-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; }
  .total-chip {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 3px; padding: 0.5rem 1rem;
    font-size: 0.85rem;
  }
  .total-chip span { color: var(--gold); font-weight: 500; }

  /* EMPTY STATE */
  .empty { padding: 3rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <span class="piece">♟️</span>
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
    <a href="/dashboard/logout"><button class="btn-logout">Salir</button></a>
  </div>
</header>

<main>

  <!-- MÉTRICAS -->
  <div class="metrics" id="metrics">
    <div class="metric"><span class="metric-label">Alumnos activos</span><span class="metric-value" id="m-alumnos">—</span></div>
    <div class="metric"><span class="metric-label">Clases agendadas</span><span class="metric-value" id="m-clases">—</span></div>
    <div class="metric"><span class="metric-label">Canceladas</span><span class="metric-value red" id="m-canceladas">—</span></div>
    <div class="metric"><span class="metric-label">Cobrado USD 💵</span><span class="metric-value green" id="m-usd">—</span><span class="metric-sub" id="m-usd-sub"></span></div>
    <div class="metric"><span class="metric-label">Cobrado £</span><span class="metric-value green" id="m-gbp">—</span></div>
    <div class="metric"><span class="metric-label">Cobrado ARS</span><span class="metric-value green" id="m-ars">—</span></div>
  </div>

  <!-- TABS -->
  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('clases')">📅 Clases</button>
    <button class="tab-btn" onclick="showTab('pagos')">💰 Pagos</button>
    <button class="tab-btn" onclick="showTab('deuda')">❌ Deuda</button>
    <button class="tab-btn" onclick="showTab('alumnos')">👥 Alumnos</button>
    <button class="tab-btn" onclick="showTab('graficos')">📈 Gráficos</button>
  </div>

  <!-- TAB: CLASES -->
  <div class="tab-panel active" id="tab-clases">
    <div class="filters">
      <span class="filter-label">Filtrar:</span>
      <input type="text" id="filtro-clases" placeholder="Buscar alumno..." oninput="filtrarTabla('tabla-clases', this.value)">
      <select id="filtro-estado" onchange="cargarClases()">
        <option value="">Todos los estados</option>
        <option value="agendada">Agendada</option>
        <option value="cancelada">Cancelada</option>
      </select>
    </div>
    <div class="table-wrapper">
      <table>
        <thead><tr>
          <th>Fecha</th><th>Hora</th><th>Alumno</th><th>Estado</th><th>Origen</th><th>País</th>
        </tr></thead>
        <tbody id="tabla-clases"><tr><td colspan="6" class="loading">Cargando...</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- TAB: PAGOS -->
  <div class="tab-panel" id="tab-pagos">
    <div class="section">
      <div class="section-title">Pagos registrados</div>
      <div class="filters">
        <input type="text" id="filtro-pagos" placeholder="Buscar alumno..." oninput="filtrarTabla('tabla-pagos', this.value)">
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Fecha</th><th>Alumno</th><th>Monto</th><th>Moneda</th><th>Método</th><th>Notas</th></tr></thead>
          <tbody id="tabla-pagos"><tr><td colspan="6" class="loading">Cargando...</td></tr></tbody>
        </table>
      </div>
      <div class="totales-row" id="totales-pagos"></div>
    </div>
  </div>

  <!-- TAB: DEUDA -->
  <div class="tab-panel" id="tab-deuda">
    <div class="section">
      <div class="section-title">Alumnos mensuales sin pago</div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Alumno</th><th>Representante</th><th>Clases</th><th>$/clase</th><th>Total</th><th>Moneda</th></tr></thead>
          <tbody id="tabla-deuda"><tr><td colspan="6" class="loading">Cargando...</td></tr></tbody>
        </table>
      </div>
      <div id="totales-deuda" class="totals-row"></div>
    </div>
  </div>

  <!-- TAB: ALUMNOS -->
  <div class="tab-panel" id="tab-alumnos">
    <div class="filters">
      <input type="text" id="filtro-alumnos" placeholder="Buscar nombre o representante..." oninput="filtrarTabla('tabla-alumnos', this.value)">
    </div>
    <div class="table-wrapper">
      <table>
        <thead><tr>
          <th>Nombre</th><th>Representante</th><th>País</th><th>Moneda</th>
          <th>Método</th><th>Modalidad</th><th>Clases mes</th><th>Pagó</th>
        </tr></thead>
        <tbody id="tabla-alumnos"><tr><td colspan="8" class="loading">Cargando...</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- TAB: GRÁFICOS -->
  <div class="tab-panel" id="tab-graficos">
    <div class="grid-2">
      <div class="chart-box">
        <h3>Clases agendadas por alumno</h3>
        <canvas id="chart-alumnos" height="300"></canvas>
      </div>
      <div class="chart-box">
        <h3>Distribución por país</h3>
        <canvas id="chart-paises" height="300"></canvas>
      </div>
    </div>
  </div>

</main>

<script>
// ─────────────────────────────────────────────
// ESTADO GLOBAL
// ─────────────────────────────────────────────
let mes = new Date().getMonth() + 1;
let anio = new Date().getFullYear();
let charts = {};

// Sincronizar selectores con el mes/año actual
document.getElementById('sel-mes').value = mes;
document.getElementById('sel-anio').value = anio;

document.getElementById('sel-mes').addEventListener('change', () => { mes = +document.getElementById('sel-mes').value; cargarTodo(); });
document.getElementById('sel-anio').addEventListener('change', () => { anio = +document.getElementById('sel-anio').value; cargarTodo(); });

// ─────────────────────────────────────────────
// TABS
// ─────────────────────────────────────────────
function showTab(id) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
  if (id === 'graficos') cargarGraficos();
}

// ─────────────────────────────────────────────
// FETCH HELPER
// ─────────────────────────────────────────────
async function api(ruta) {
  const res = await fetch(`/dashboard/api/${ruta}&mes=${mes}&anio=${anio}`);
  return res.json();
}

// ─────────────────────────────────────────────
// CARGAR TODO
// ─────────────────────────────────────────────
function cargarTodo() {
  cargarResumen();
  cargarClases();
  cargarPagos();
  cargarDeudores();
  cargarAlumnos();
}

// ─────────────────────────────────────────────
// RESUMEN (métricas)
// ─────────────────────────────────────────────
async function cargarResumen() {
  const d = await api('resumen?x=1');
  document.getElementById('m-alumnos').textContent = d.total_alumnos;
  document.getElementById('m-clases').textContent = d.clases_agendadas;
  document.getElementById('m-canceladas').textContent = d.clases_canceladas;
  document.getElementById('m-usd').textContent = d.pagos['Dólar'] ? '$' + fmt(d.pagos['Dólar']) : '—';
  document.getElementById('m-gbp').textContent = d.pagos['Libra Esterlina'] ? '£' + fmt(d.pagos['Libra Esterlina']) : '—';
  document.getElementById('m-ars').textContent = d.pagos['Pesos'] ? '$' + fmt(d.pagos['Pesos']) : '—';
}

// ─────────────────────────────────────────────
// CLASES
// ─────────────────────────────────────────────
async function cargarClases() {
  const estadoFiltro = document.getElementById('filtro-estado').value;
  let datos = await api('clases?x=1');
  if (estadoFiltro) datos = datos.filter(c => c.estado.includes(estadoFiltro));

  const estados = {
    'agendada': '<span class="badge badge-gold">Agendada</span>',
    'cancelada_con_anticipacion': '<span class="badge badge-gray">Cancelada ✓</span>',
    'cancelada_sin_anticipacion': '<span class="badge badge-red">Cancelada ✗</span>',
    'cancelada_por_profesora': '<span class="badge badge-gray">Cancelada (prof)</span>',
    'dada': '<span class="badge badge-green">Dada</span>'
  };

  const html = datos.length ? datos.map(c => `
    <tr>
      <td>${c.fecha}</td>
      <td>${c.hora || '—'}</td>
      <td><strong>${c.nombre}</strong></td>
      <td>${estados[c.estado] || c.estado}</td>
      <td><span style="color:var(--text-dim);font-size:0.8rem">${c.origen}</span></td>
      <td>${c.pais || '—'}</td>
    </tr>`).join('') : '<tr><td colspan="6" class="empty">Sin clases en este período</td></tr>';

  document.getElementById('tabla-clases').innerHTML = html;
}

// ─────────────────────────────────────────────
// PAGOS
// ─────────────────────────────────────────────
async function cargarPagos() {
  const datos = await api('pagos?x=1');
  const monedas = {};

  const html = datos.length ? datos.map(p => {
    monedas[p.moneda] = (monedas[p.moneda] || 0) + p.monto;
    const sim = p.moneda === 'Dólar' ? '$' : p.moneda === 'Libra Esterlina' ? '£' : '$';
    return `<tr>
      <td>${p.fecha}</td>
      <td><strong>${p.nombre}</strong>${p.representante && p.representante !== '-' ? `<br><span style="color:var(--text-muted);font-size:0.75rem">${p.representante}</span>` : ''}</td>
      <td>${sim}${fmt(p.monto)}</td>
      <td><span class="badge badge-gold">${p.moneda}</span></td>
      <td>${p.metodo || '—'}</td>
      <td style="color:var(--text-dim);font-size:0.8rem">${p.notas || '—'}</td>
    </tr>`;
  }).join('') : '<tr><td colspan="6" class="empty">Sin pagos registrados</td></tr>';

  document.getElementById('tabla-pagos').innerHTML = html;

  const totalesHtml = Object.entries(monedas).map(([mon, tot]) => {
    const sim = mon === 'Dólar' ? '$' : mon === 'Libra Esterlina' ? '£' : '$';
    return `<div class="total-chip">Total ${mon}: <span>${sim}${fmt(tot)}</span></div>`;
  }).join('');
  document.getElementById('totales-pagos').innerHTML = totalesHtml;
}

// ─────────────────────────────────────────────
// DEUDORES
// ─────────────────────────────────────────────
async function cargarDeudores() {
  const datos = await api('deudores?x=1');
  const porCobrar = {};

  const html = datos.length ? datos.map(d => {
    if (d.total && d.moneda) porCobrar[d.moneda] = (porCobrar[d.moneda] || 0) + d.total;
    const sim = d.moneda === 'Dólar' ? '$' : d.moneda === 'Libra Esterlina' ? '£' : '$';
    return `<tr>
      <td><strong>${d.nombre}</strong></td>
      <td>${d.representante}</td>
      <td>${d.clases}</td>
      <td>${d.precio_unitario ? sim + fmt(d.precio_unitario) : '—'}</td>
      <td>${d.total ? '<strong>' + sim + fmt(d.total) + '</strong>' : '—'}</td>
      <td><span class="badge badge-gold">${d.moneda}</span></td>
    </tr>`;
  }).join('') : '<tr><td colspan="6" class="empty" style="color:var(--green)">🎉 Todos los alumnos mensuales pagaron</td></tr>';

  document.getElementById('tabla-deuda').innerHTML = html;

  const totalesHtml = Object.entries(porCobrar).map(([mon, tot]) => {
    const sim = mon === 'Dólar' ? '$' : mon === 'Libra Esterlina' ? '£' : '$';
    return `<div class="total-chip">Por cobrar ${mon}: <span>${sim}${fmt(tot)}</span></div>`;
  }).join('');
  document.getElementById('totales-deuda').innerHTML = totalesHtml || '<div style="color:var(--text-muted);font-size:0.85rem;padding:0.5rem 0">Sin deuda pendiente</div>';
}

// ─────────────────────────────────────────────
// ALUMNOS
// ─────────────────────────────────────────────
async function cargarAlumnos() {
  const datos = await api('alumnos?x=1');
  const html = datos.map(a => `
    <tr>
      <td><strong>${a.nombre}</strong></td>
      <td>${a.representante || '—'}</td>
      <td>${a.pais || '—'}</td>
      <td><span class="badge badge-gold">${a.moneda || '—'}</span></td>
      <td style="font-size:0.8rem;color:var(--text-dim)">${a.metodo_pago || '—'}</td>
      <td style="font-size:0.8rem;color:var(--text-dim)">${a.modalidad || '—'}</td>
      <td style="text-align:center">${a.clases_mes}</td>
      <td style="text-align:center">${a.pago_este_mes ? '<span class="badge badge-green">✓</span>' : '<span class="badge badge-red">✗</span>'}</td>
    </tr>`).join('');
  document.getElementById('tabla-alumnos').innerHTML = html || '<tr><td colspan="8" class="empty">Sin alumnos</td></tr>';
}

// ─────────────────────────────────────────────
// GRÁFICOS
// ─────────────────────────────────────────────
async function cargarGraficos() {
  const datos = await api('grafico_clases?x=1');
  const clases = await api('clases?x=1');

  // Gráfico de barras: clases por alumno
  if (charts.alumnos) charts.alumnos.destroy();
  const ctx1 = document.getElementById('chart-alumnos').getContext('2d');
  charts.alumnos = new Chart(ctx1, {
    type: 'bar',
    data: {
      labels: datos.map(d => d.nombre),
      datasets: [{
        data: datos.map(d => d.total),
        backgroundColor: 'rgba(180,140,80,0.6)',
        borderColor: 'rgba(180,140,80,1)',
        borderWidth: 1,
        borderRadius: 3
      }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#666' }, grid: { color: '#1a1a1a' } },
        y: { ticks: { color: '#aaa' }, grid: { display: false } }
      }
    }
  });

  // Gráfico de torta: distribución por país
  const paises = {};
  clases.filter(c => c.estado === 'agendada').forEach(c => {
    const p = c.pais || 'Sin datos';
    paises[p] = (paises[p] || 0) + 1;
  });
  if (charts.paises) charts.paises.destroy();
  const ctx2 = document.getElementById('chart-paises').getContext('2d');
  charts.paises = new Chart(ctx2, {
    type: 'doughnut',
    data: {
      labels: Object.keys(paises),
      datasets: [{ data: Object.values(paises), backgroundColor: ['#b48c50','#4caf87','#c0624a','#5b8db8','#9b7fc8'], borderWidth: 0 }]
    },
    options: {
      plugins: { legend: { labels: { color: '#888', font: { size: 12 } } } },
      cutout: '60%'
    }
  });
}

// ─────────────────────────────────────────────
// FILTRO DE TABLA (búsqueda en tiempo real)
// ─────────────────────────────────────────────
function filtrarTabla(tablaId, texto) {
  const tbody = document.getElementById(tablaId);
  const filas = tbody.querySelectorAll('tr');
  const q = texto.toLowerCase();
  filas.forEach(f => {
    f.style.display = f.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

// ─────────────────────────────────────────────
// UTILIDADES
// ─────────────────────────────────────────────
function fmt(n) { return Number(n).toLocaleString('es-AR'); }

// ─────────────────────────────────────────────
// INICIO
// ─────────────────────────────────────────────
cargarTodo();

// Auto-refresco cada 60 segundos
setInterval(cargarTodo, 60000);
</script>
</body>
</html>'''