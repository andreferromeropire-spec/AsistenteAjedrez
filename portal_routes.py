import os
import json
import hashlib
import base64
from datetime import datetime, date

import requests
from flask import Blueprint, Response, request, session, redirect

from database import get_connection
from calendar_google import crear_flow_google
from dashboard_routes import SHARED_CSS


portal_bp = Blueprint("portal", __name__)


def portal_login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("portal_alumno_ids"):
            return redirect("/portal")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def _crear_sesion_portal(alumno_id, lichess_username=None):
    conn = get_connection()
    ahora = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO portal_sessions (alumno_id, lichess_username, created_at, last_seen) VALUES (?,?,?,?)",
        (alumno_id, lichess_username, ahora, ahora),
    )
    conn.commit()
    conn.close()


def _marcar_sesion_activa(alumno_id):
    conn = get_connection()
    ahora = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE portal_sessions SET last_seen = ? WHERE alumno_id = ?",
        (ahora, alumno_id),
    )
    conn.commit()
    conn.close()


def _buscar_accesos_por_lichess(username):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT pa.id, pa.lichess_username, pa.alumno_id, pa.notas,
               a.nombre, a.representante
        FROM portal_accesos pa
        JOIN alumnos a ON a.id = pa.alumno_id
        WHERE lower(pa.lichess_username) = lower(?)
          AND a.activo = 1
        """,
        (username,),
    ).fetchall()
    conn.close()
    return rows


def _buscar_alumnos_por_mail(mail):
    conn = get_connection()
    alumnos = conn.execute(
        "SELECT * FROM alumnos WHERE lower(mail) = lower(?) AND activo = 1",
        (mail,),
    ).fetchall()
    conn.close()
    # Por ahora, solo consideramos alumnos cuyo mail coincide exactamente.
    # La expansión por representante se hará en el futuro cuando exista una tabla de responsables con ID propio.
    return alumnos
    conn.close()
    return row


def _pagina_no_autorizado():
    html = PORTAL_HTML_UNAUTHORIZED
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal")
def portal_login():
    if session.get("portal_alumno_ids"):
        return redirect("/portal/home")
    return redirect("/login")


@portal_bp.route("/portal/auth/lichess")
def portal_auth_lichess():
    client_id = os.environ.get("LICHESS_CLIENT_ID") or "asistente-ajedrez-portal"
    state = os.urandom(16).hex()
    session["portal_lichess_state"] = state
    # PKCE: generar code_verifier y code_challenge (S256)
    raw_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8").rstrip("=")
    code_verifier = raw_verifier[:64]
    session["portal_lichess_verifier"] = code_verifier
    sha = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(sha).decode("utf-8").rstrip("=")

    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/lichess/callback"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query = "&".join([key + "=" + requests.utils.quote(str(value)) for key, value in params.items()])
    url = "https://lichess.org/oauth?" + query
    return redirect(url)


@portal_bp.route("/portal/auth/lichess/callback")
def portal_auth_lichess_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state or state != session.get("portal_lichess_state"):
        return _pagina_no_autorizado()
    session.pop("portal_lichess_state", None)
    code_verifier = session.get("portal_lichess_verifier")
    session.pop("portal_lichess_verifier", None)
    if not code_verifier:
        return _pagina_no_autorizado()

    client_id = os.environ.get("LICHESS_CLIENT_ID") or "asistente-ajedrez-portal"
    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/lichess/callback"

    try:
        token_resp = requests.post(
            "https://lichess.org/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
            },
            timeout=10,
        )
        data = token_resp.json()
        access_token = data.get("access_token")
        if not access_token:
            return _pagina_no_autorizado()

        perfil_resp = requests.get(
            "https://lichess.org/api/account",
            headers={"Authorization": "Bearer " + access_token},
            timeout=10,
        )
        perfil = perfil_resp.json()
        username = perfil.get("username")
        if not username:
            return _pagina_no_autorizado()

        accesos = _buscar_accesos_por_lichess(username)
        if not accesos:
            return _pagina_no_autorizado()

        alumno_ids = [r["alumno_id"] for r in accesos]
        nombres = [r["nombre"] for r in accesos]
        reps = [r["representante"] for r in accesos if r["representante"]]
        nombre_header = nombres[0]
        if reps and len(set(reps)) == 1:
            nombre_header = reps[0]

        session["portal_alumno_ids"] = alumno_ids
        session["portal_nombre"] = nombre_header
        if alumno_ids:
            _crear_sesion_portal(alumno_ids[0], username)
        return redirect("/portal/home")
    except Exception:
        return _pagina_no_autorizado()


@portal_bp.route("/portal/auth/google")
def portal_auth_google():
    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/google/callback"
    try:
        flow = crear_flow_google(redirect_uri)
    except Exception:
        return _pagina_no_autorizado()
    auth_url, state = flow.authorization_url(access_type="online", prompt="consent")
    session["portal_google_state"] = state
    session["portal_google_redirect_uri"] = redirect_uri
    session["portal_google_flow_config"] = os.environ.get("GOOGLE_CREDENTIALS") or ""
    return redirect(auth_url)


@portal_bp.route("/portal/auth/google/callback")
def portal_auth_google_callback():
    state = request.args.get("state")
    if not state or state != session.get("portal_google_state"):
        return _pagina_no_autorizado()
    code = request.args.get("code")
    if not code:
        return _pagina_no_autorizado()

    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/google/callback"
    try:
        flow = crear_flow_google(redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials
        token = getattr(creds, "token", None)
        if not token:
            return _pagina_no_autorizado()

        resp = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
            headers={"Authorization": "Bearer " + token},
            timeout=10,
        )
        info = resp.json()
        email = info.get("email")
        if not email:
            return _pagina_no_autorizado()

        alumnos = _buscar_alumnos_por_mail(email)
        if not alumnos:
            return _pagina_no_autorizado()

        alumno_ids = [a["id"] for a in alumnos]
        reps = [a["representante"] for a in alumnos if a["representante"]]
        nombre_header = alumnos[0]["nombre"]
        if reps and len(set(reps)) == 1:
            nombre_header = reps[0]

        session["portal_alumno_ids"] = alumno_ids
        session["portal_nombre"] = nombre_header
        if alumno_ids:
            _crear_sesion_portal(alumno_ids[0], None)
        return redirect("/portal/home")
    except Exception:
        return _pagina_no_autorizado()


@portal_bp.route("/portal/home")
@portal_login_required
def portal_home():
    alumno_ids = session.get("portal_alumno_ids") or []
    nombre = session.get("portal_nombre", "")
    if not alumno_ids:
        return redirect("/portal")

    conn = get_connection()
    hoy = date.today()
    mes = hoy.month
    anio = hoy.year

    # Mail del responsable (del primer alumno)
    mail_responsable = ""
    if alumno_ids:
        row_mail = conn.execute(
            "SELECT mail FROM alumnos WHERE id = ? AND mail IS NOT NULL AND mail != ''",
            (alumno_ids[0],),
        ).fetchone()
        if row_mail:
            mail_responsable = row_mail["mail"]

    resumen = []
    for aid in alumno_ids:
        # Clases del mes actual (para la tabla)
        clases = conn.execute(
            """
            SELECT fecha, hora, estado, ausente, pago_id
            FROM clases
            WHERE alumno_id = ?
              AND substr(fecha, 1, 7) = ?
            ORDER BY fecha, hora
            """,
            (aid, f"{anio:04d}-{mes:02d}"),
        ).fetchall()

        # Próxima clase futura agendada
        proxima = conn.execute(
            """
            SELECT fecha, hora
            FROM clases
            WHERE alumno_id = ?
              AND estado = 'agendada'
              AND fecha >= date('now')
            ORDER BY fecha ASC, hora ASC
            LIMIT 1
            """,
            (aid,),
        ).fetchone()

        # Contadores del mes actual
        contadores = conn.execute(
            """
            SELECT
              COUNT(CASE WHEN estado='agendada'
                         AND substr(fecha,1,7)=?
                    THEN 1 END) AS clases_agendadas,
              COUNT(CASE WHEN estado IN ('agendada','dada')
                         AND substr(fecha,1,7)=?
                         AND fecha <= date('now')
                    THEN 1 END) AS clases_dadas,
              COUNT(CASE WHEN pago_id IS NOT NULL
                         AND estado IN ('agendada','dada')
                         AND substr(fecha,1,7)=?
                    THEN 1 END) AS clases_pagas
            FROM clases
            WHERE alumno_id = ?
            """,
            (
                f"{anio:04d}-{mes:02d}",
                f"{anio:04d}-{mes:02d}",
                f"{anio:04d}-{mes:02d}",
                aid,
            ),
        ).fetchone()

        clases_agendadas = contadores["clases_agendadas"] or 0
        clases_dadas = contadores["clases_dadas"] or 0
        clases_pagas = contadores["clases_pagas"] or 0
        clases_restantes = max(clases_pagas - clases_dadas, 0)
        al_dia = clases_pagas >= clases_dadas
        clases_sin_pagar = 0 if al_dia else (clases_dadas - clases_pagas)

        info_alumno = conn.execute(
            "SELECT nombre FROM alumnos WHERE id = ?", (aid,)
        ).fetchone()

        # Progreso de entrenamiento de patrones
        prog = conn.execute(
            """
            SELECT
              COUNT(*) AS ejercicios,
              AVG(rating_cambio) AS rating_prom,
              MAX(fecha) AS ultima_fecha
            FROM progreso_entrenamiento
            WHERE alumno_id = ?
            """,
            (aid,),
        ).fetchone()
        entrenamiento = {
            "ejercicios": prog["ejercicios"] or 0 if prog else 0,
            "rating_prom": prog["rating_prom"] or 0.0 if prog else 0.0,
            "ultima_fecha": prog["ultima_fecha"] or "" if prog else "",
        }

        clases_items = []
        for c in clases:
            clases_items.append(
                {
                    "fecha": c["fecha"],
                    "hora": c["hora"] or "",
                    "estado": c["estado"],
                    "ausente": c["ausente"] or 0,
                }
            )

        # Historial de últimos 3 meses anteriores
        historial = []
        for offset in range(1, 4):
            m = mes - offset
            y = anio
            if m <= 0:
                m += 12
                y -= 1
            etiqueta = f"{y:04d}-{m:02d}"
            datos_hist = conn.execute(
                """
                SELECT
                  COUNT(CASE WHEN estado IN ('agendada','dada') THEN 1 END) AS clases_dadas,
                  COUNT(CASE WHEN pago_id IS NOT NULL AND estado IN ('agendada','dada') THEN 1 END) AS clases_pagas
                FROM clases
                WHERE alumno_id = ? AND substr(fecha,1,7) = ?
                """,
                (aid, etiqueta),
            ).fetchone()
            if datos_hist and (datos_hist["clases_dadas"] or datos_hist["clases_pagas"]):
                historial.append(
                    {
                        "mes": m,
                        "anio": y,
                        "clases_dadas": datos_hist["clases_dadas"] or 0,
                        "clases_pagas": datos_hist["clases_pagas"] or 0,
                    }
                )

        resumen.append(
            {
                "id": aid,
                "nombre": info_alumno["nombre"] if info_alumno else "",
                "proxima_clase": {
                    "fecha": proxima["fecha"],
                    "hora": proxima["hora"] or "",
                }
                if proxima
                else None,
                "clases_agendadas": clases_agendadas,
                "clases_dadas": clases_dadas,
                "clases_pagas": clases_pagas,
                "clases_restantes": clases_restantes,
                "al_dia": al_dia,
                "clases_sin_pagar": clases_sin_pagar,
                "clases_mes": clases_items,
                "historial": historial,
                "mail_responsable": mail_responsable,
                "entrenamiento": entrenamiento,
            }
        )

    conn.close()

    if alumno_ids:
        _marcar_sesion_activa(alumno_ids[0])

    contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)
    contenido = contenido.replace("{RESUMEN_JSON}", json.dumps(resumen))
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal/api/recordatorios")
@portal_login_required
def api_portal_recordatorios():
    alumno_ids = session.get("portal_alumno_ids") or []
    if not alumno_ids:
        return Response(json.dumps([]), mimetype="application/json")
    alumno_id = alumno_ids[0]
    conn = get_connection()
    recs = conn.execute(
        """
        SELECT id, minutos_antes, alcance, canal, mail_destino, activo, creado
        FROM recordatorios
        WHERE alumno_id = ? AND activo = 1 AND canal = 'mail'
        ORDER BY minutos_antes
        """,
        (alumno_id,),
    ).fetchall()
    conn.close()
    return Response(
        json.dumps(
            [
                {
                    "id": r["id"],
                    "minutos_antes": r["minutos_antes"],
                    "alcance": r["alcance"],
                    "canal": r["canal"],
                    "mail_destino": r["mail_destino"] or "",
                    "creado": r["creado"],
                }
                for r in recs
            ]
        ),
        mimetype="application/json",
    )


@portal_bp.route("/portal/api/recordatorios", methods=["POST"])
@portal_login_required
def api_portal_recordatorios_crear():
    alumno_ids = session.get("portal_alumno_ids") or []
    if not alumno_ids:
        return Response(json.dumps({"ok": False, "error": "No hay alumno en sesión"}), mimetype="application/json", status=400)
    alumno_id = alumno_ids[0]
    data = request.get_json() or {}
    minutos_antes = int(data.get("minutos_antes") or 0)
    alcance = (data.get("alcance") or "todas").strip()
    canal = (data.get("canal") or "mail").strip()
    mail_destino = (data.get("mail_destino") or "").strip()
    clase_id = data.get("clase_id")
    if canal != "mail":
        return Response(json.dumps({"ok": False, "error": "Canal no soportado"}), mimetype="application/json", status=400)
    if minutos_antes <= 0:
        return Response(json.dumps({"ok": False, "error": "Tiempo antes inválido"}), mimetype="application/json", status=400)
    conn = get_connection()
    cant_activos = conn.execute(
        "SELECT COUNT(*) as n FROM recordatorios WHERE alumno_id = ? AND activo = 1",
        (alumno_id,),
    ).fetchone()["n"]
    if cant_activos >= 3:
        conn.close()
        return Response(json.dumps({"ok": False, "error": "Límite de recordatorios activos alcanzado (3)"}), mimetype="application/json", status=400)
    conn.execute(
        "INSERT INTO recordatorios (alumno_id, minutos_antes, alcance, canal, mail_destino, clase_id, activo, creado) VALUES (?,?,?,?,?,?,1,datetime('now'))",
        (alumno_id, minutos_antes, alcance, canal, mail_destino, clase_id),
    )
    conn.commit()
    conn.close()
    return Response(json.dumps({"ok": True}), mimetype="application/json")


@portal_bp.route("/portal/api/recordatorios/<int:rec_id>", methods=["DELETE"])
@portal_login_required
def api_portal_recordatorios_borrar(rec_id):
    alumno_ids = session.get("portal_alumno_ids") or []
    if not alumno_ids:
        return Response(json.dumps({"ok": False, "error": "No hay alumno en sesión"}), mimetype="application/json", status=400)
    alumno_id = alumno_ids[0]
    conn = get_connection()
    conn.execute(
        "DELETE FROM recordatorios WHERE id = ? AND alumno_id = ?",
        (rec_id, alumno_id),
    )
    conn.commit()
    conn.close()
    return Response(json.dumps({"ok": True}), mimetype="application/json")


@portal_bp.route("/portal/api/puzzle_diario")
def api_portal_puzzle_diario():
    try:
        resp = requests.get(
            "https://lichess.org/api/puzzle/daily",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.status_code != 200:
            return Response(json.dumps({"error": "no disponible"}), mimetype="application/json", status=200)
        data = resp.json()
        return Response(json.dumps(data), mimetype="application/json", status=200)
    except Exception:
        return Response(json.dumps({"error": "no disponible"}), mimetype="application/json", status=200)


@portal_bp.route("/portal/entrenamiento")
@portal_login_required
def portal_entrenamiento():
    alumno_ids = session.get("portal_alumno_ids") or []
    if not alumno_ids:
        return redirect("/portal")
    conn = get_connection()
    placeholders = ",".join(["?"] * len(alumno_ids))
    rows = conn.execute(
        f"""
        SELECT a.id, a.nombre,
               COUNT(p.id) AS ejercicios,
               COALESCE(AVG(p.rating_cambio), 0.0) AS rating_prom,
               MAX(p.fecha) AS ultima_fecha
        FROM alumnos a
        LEFT JOIN progreso_entrenamiento p ON p.alumno_id = a.id
        WHERE a.id IN ({placeholders})
        GROUP BY a.id, a.nombre
        ORDER BY a.nombre
        """,
        alumno_ids,
    ).fetchall()
    conn.close()
    # HTML sencillo reutilizando estilos del portal
    filas = []
    for r in rows:
        filas.append(
            "<tr>"
            + "<td>" + (r["nombre"] or "") + "</td>"
            + "<td>" + str(r["ejercicios"] or 0) + "</td>"
            + "<td>" + ("{:.1f}".format(r["rating_prom"]) if r["rating_prom"] is not None else "0.0") + "</td>"
            + "<td>" + (r["ultima_fecha"] or "-") + "</td>"
            + "</tr>"
        )
    cuerpo = "".join(filas) if filas else '<tr><td colspan="4" style="text-align:center;padding:1rem;color:var(--text-muted)">Sin ejercicios registrados todavía.</td></tr>'
    contenido = """
<div class="card">
  <h2 style="font-family:'Playfair Display',serif;font-size:1.4rem;color:var(--gold-light);margin-bottom:0.75rem">Progreso de entrenamiento</h2>
  <p style="font-size:0.9rem;color:var(--text-muted);margin-bottom:0.75rem">
    Resumen de los ejercicios de patrones resueltos por cada alumno asociado a esta cuenta.
  </p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Alumno</th><th>Ejercicios</th><th>Rating medio</th><th>Última actividad</th></tr>
      </thead>
      <tbody>""" + cuerpo + """</tbody>
    </table>
  </div>
  <div style="margin-top:0.75rem">
    <a href="/portal/home" class="btn">Volver al portal</a>
  </div>
</div>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal/logout")
def portal_logout():
    session.pop("portal_alumno_ids", None)
    session.pop("portal_nombre", None)
    return redirect("/portal")


PORTAL_HTML = """<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alumno Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
""" + SHARED_CSS + """
main{padding:1.5rem 1.75rem;max-width:1440px;margin:0 auto}
.portal-header-sub{font-size:0.8rem;color:var(--text-muted);}
.btn-row{display:flex;gap:0.6rem;margin-top:0.8rem;flex-wrap:wrap}
.unauth-msg{font-size:0.9rem;line-height:1.5}
.portal-layout{display:grid;grid-template-columns:2fr 1fr;gap:1.25rem;align-items:flex-start}
@media(max-width:768px){.portal-layout{grid-template-columns:1fr}.portal-side{order:-1}}
.puzzle-img{width:100%;border-radius:4px;border:1px solid var(--border);background:var(--surface2)}
.chip{display:inline-block;padding:0.18rem 0.45rem;border-radius:999px;background:var(--surface2);border:1px solid var(--border);font-size:0.7rem;color:var(--text-dim);margin:0 0.25rem 0.25rem 0}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <span style="font-size:1.4rem">&#9823;</span>
    <div>
      <h1 id="portal-title" data-es="Portal de alumnos" data-en="Student Portal">Portal de alumnos</h1>
      <div class="portal-header-sub" id="portal-subtitle" data-es="Acceso para alumnos" data-en="Student access">Acceso para alumnos</div>
    </div>
  </div>
  <div class="header-right">
    <div class="theme-group">
      <button class="theme-btn active" onclick="setTheme('light',this)">&#9728;</button>
      <button class="theme-btn" onclick="setTheme('dark',this)">&#9790;</button>
      <button class="theme-btn" onclick="setTheme('navy',this)">&#127754;</button>
    </div>
    <div class="lang-toggle">
      <span id="lang-label">Idioma:</span>
      <button type="button" class="btn" id="btn-es">ES</button>
      <button type="button" class="btn" id="btn-en">EN</button>
    </div>
  </div>
</header>
<main>
  {PORTAL_CONTENT}
</main>
<script>
function setTheme(tema, btn) {
  document.documentElement.setAttribute('data-theme', tema);
  try { localStorage.setItem('dashboard-theme', tema); } catch(e) {}
  var btns = document.querySelectorAll('.theme-btn');
  var i;
  for (i = 0; i < btns.length; i++) { btns[i].classList.remove('active'); }
  if (btn) { btn.classList.add('active'); }
}
(function() {
  var saved;
  try { saved = localStorage.getItem('dashboard-theme') || 'light'; } catch(e) { saved = 'light'; }
  document.documentElement.setAttribute('data-theme', saved);
  var idxMap = {light:0, dark:1, navy:2};
  var idx = idxMap[saved];
  if (idx === undefined) { idx = 0; }
  var btns = document.querySelectorAll('.theme-btn');
  var i;
  for (i = 0; i < btns.length; i++) { btns[i].classList.remove('active'); }
  if (btns[idx]) { btns[idx].classList.add('active'); }
})();
(function(){
  var lang;
  try { lang = localStorage.getItem('portal_lang') || 'es'; } catch(e) { lang = 'es'; }
  function setLang(l){
    lang = l;
    try { localStorage.setItem('portal_lang', l); } catch(e) {}
    var esBtn = document.getElementById('btn-es');
    var enBtn = document.getElementById('btn-en');
    if(esBtn && enBtn){
      if(l === 'es'){ esBtn.classList.add('active'); enBtn.classList.remove('active'); }
      else{ enBtn.classList.add('active'); esBtn.classList.remove('active'); }
    }
    var el;
    el = document.getElementById('portal-title');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('portal-subtitle');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('login-subtitle');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('login-btn-lichess');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('login-btn-google');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('home-saludo');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    var estados = document.querySelectorAll('.estado-pago');
    var i;
    for (i = 0; i < estados.length; i++) {
      var e = estados[i];
      var esTxt = e.getAttribute('data-es');
      var enTxt = e.getAttribute('data-en');
      e.textContent = (l === 'es') ? esTxt : enTxt;
    }
    var badges = document.querySelectorAll('.badge-estado-clase');
    for (i = 0; i < badges.length; i++) {
      var b = badges[i];
      var esT = b.getAttribute('data-es');
      var enT = b.getAttribute('data-en');
      b.textContent = (l === 'es') ? esT : enT;
    }
    el = document.getElementById('unauth-title');
    if(el){ el.textContent = (l === 'es') ? 'Acceso no autorizado' : 'Access not allowed'; }
    el = document.getElementById('unauth-text');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
  }
  var esBtn = document.getElementById('btn-es');
  var enBtn = document.getElementById('btn-en');
  if(esBtn){ esBtn.addEventListener('click', function(){ setLang('es'); }); }
  if(enBtn){ enBtn.addEventListener('click', function(){ setLang('en'); }); }
  setLang(lang);
})();
</script>
</body>
</html>
"""


PORTAL_LOGIN_CONTENT = """
<div class="card">
  <div class="logo">
    <div class="piece">&#9823;</div>
    <h2 id="login-title" data-es="Portal de alumnos" data-en="Student Portal">Portal de alumnos</h2>
    <p id="login-subtitle" data-es="Acceso para alumnos" data-en="Student access">Acceso para alumnos</p>
  </div>
  <div class="btn-row">
    <a href="/portal/auth/lichess" class="btn" id="login-btn-lichess" data-es="Entrar con Lichess" data-en="Sign in with Lichess">Entrar con Lichess</a>
    <a href="/portal/auth/google" class="btn" id="login-btn-google" data-es="Entrar con Google" data-en="Sign in with Google">Entrar con Google</a>
  </div>
</div>
"""


PORTAL_HOME_CONTENT = """
<div class="portal-layout">
  <div class="portal-main">
    <div class="card">
      <h2 id="home-saludo" data-es="Hola, {NOMBRE}" data-en="Hi, {NOMBRE}" style="font-family:\\"Playfair Display\\",serif;font-size:1.6rem;color:var(--gold-light);margin-bottom:1rem">Hola, {NOMBRE}</h2>
      <div id="home-alumnos"></div>
      <div>
        <a href="/portal/logout" class="btn" id="home-logout" style="display:inline-block;margin-top:1rem">Salir</a>
      </div>
    </div>
  </div>
  <div class="portal-side">
    <div class="card" id="puzzle-card">
      <h3 style="font-size:0.95rem;margin-bottom:0.5rem" id="puzzle-title" data-es="Puzzle del día ♟" data-en="Daily Puzzle ♟">Puzzle del día ♟</h3>
      <div id="puzzle-content" style="font-size:0.85rem;color:var(--text-muted)">Cargando...</div>
    </div>
    <div class="card" id="recordatorios-card">
      <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Recordatorios</h3>
      <div id="recordatorios-lista"></div>
      <div id="recordatorios-form" style="margin-top:0.6rem"></div>
    </div>
    <div class="card" id="trainer-card">
      <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Entrenamiento de patrones</h3>
      <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:0.6rem">
        Practicá tácticas y patrones típicos en el tablero interactivo.
      </p>
      <div style="display:flex;flex-direction:column;gap:0.4rem">
        <a href="/trainer" class="btn" style="width:100%;justify-content:center">Entrar al entrenamiento</a>
        <a href="/portal/entrenamiento" class="btn" style="width:100%;justify-content:center">Ver mi progreso</a>
      </div>
    </div>
  </div>
</div>
<script>
(function(){
  var resumen = {RESUMEN_JSON};
  var cont = document.getElementById('home-alumnos');
  if(!cont){ return; }
  if(!resumen || resumen.length === 0){
    var p = document.createElement('p');
    p.textContent = 'No hay clases registradas este mes.';
    cont.appendChild(p);
    return;
  }
  for(var i=0;i<resumen.length;i++){
    var r = resumen[i];
    var clasesMes = r.clases_mes || [];
    if (clasesMes.length === 0) {
      var sinDiv = document.createElement('div');
      sinDiv.style.marginTop = '0.75rem';
      var st = document.createElement('p');
      st.textContent = 'No hay clases registradas este mes para ' + (r.nombre || '');
      sinDiv.appendChild(st);
      cont.appendChild(sinDiv);
      continue;
    }
    var bloque = document.createElement('div');
    bloque.style.marginTop = '0.75rem';
    var titulo = document.createElement('h3');
    titulo.style.fontSize = '0.95rem';
    titulo.style.marginBottom = '0.4rem';
    titulo.textContent = r.nombre;

    // Métricas tipo dashboard
    var metrics = document.createElement('div');
    metrics.className = 'metrics';
    var m1 = document.createElement('div'); m1.className = 'metric';
    var l1 = document.createElement('div'); l1.className = 'metric-label'; l1.textContent = 'Próxima clase';
    var v1 = document.createElement('div'); v1.className = 'metric-value';
    if (r.proxima_clase && r.proxima_clase.fecha) {
      var fParts = r.proxima_clase.fecha.split('-');
      var fechaTxt = r.proxima_clase.fecha;
      if (fParts.length === 3) {
        var anio = parseInt(fParts[0],10);
        var mes = parseInt(fParts[1],10)-1;
        var dia = parseInt(fParts[2],10);
        var d = new Date(anio, mes, dia);
        var dias = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
        var meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
        fechaTxt = dias[d.getDay()] + ' ' + (dia<10?'0'+dia:dia) + ' ' + meses[mes] + ' · ' + (r.proxima_clase.hora || '');
      }
      v1.textContent = fechaTxt;
    } else {
      v1.textContent = 'Sin clases agendadas';
    }
    m1.appendChild(l1); m1.appendChild(v1);

    var m2 = document.createElement('div'); m2.className = 'metric';
    var l2 = document.createElement('div'); l2.className = 'metric-label'; l2.textContent = 'Clases este mes';
    var v2 = document.createElement('div'); v2.className = 'metric-value'; v2.textContent = r.clases_agendadas || 0;
    m2.appendChild(l2); m2.appendChild(v2);

    var m3 = document.createElement('div'); m3.className = 'metric';
    var l3 = document.createElement('div'); l3.className = 'metric-label'; l3.textContent = 'Dadas';
    var v3 = document.createElement('div'); v3.className = 'metric-value'; v3.textContent = r.clases_dadas || 0;
    m3.appendChild(l3); m3.appendChild(v3);

    var m4 = document.createElement('div'); m4.className = 'metric';
    var l4 = document.createElement('div'); l4.className = 'metric-label'; l4.setAttribute('data-es','AL D\\u00cdA'); l4.setAttribute('data-en','UP TO DATE'); l4.textContent = 'AL D\\u00cdA';
    var v4 = document.createElement('div'); v4.className = 'metric-value'; v4.textContent = r.clases_pagas || 0;
    m4.appendChild(l4); m4.appendChild(v4);

    var m5 = document.createElement('div'); m5.className = 'metric';
    var l5 = document.createElement('div'); l5.className = 'metric-label'; l5.textContent = 'Clases restantes';
    var v5 = document.createElement('div'); v5.className = 'metric-value'; v5.textContent = r.clases_restantes || 0;
    if ((r.clases_restantes || 0) > 0) { v5.className += ' green'; }
    m5.appendChild(l5); m5.appendChild(v5);

    metrics.appendChild(m1);
    metrics.appendChild(m2);
    metrics.appendChild(m3);
    metrics.appendChild(m4);
    metrics.appendChild(m5);

    // Resumen simple de entrenamiento (si hay datos)
    if (r.entrenamiento && r.entrenamiento.ejercicios) {
      var m6 = document.createElement('div'); m6.className = 'metric';
      var l6 = document.createElement('div'); l6.className = 'metric-label'; l6.textContent = 'Ejercicios trainer';
      var v6 = document.createElement('div'); v6.className = 'metric-value'; v6.textContent = r.entrenamiento.ejercicios || 0;
      m6.appendChild(l6); m6.appendChild(v6);
      metrics.appendChild(m6);
    }

    var estado = document.createElement('span');
    estado.className = 'badge estado-pago';
    var esOk = r.al_dia === true;
    var restantes = r.clases_restantes || 0;
    var sinPagar = r.clases_sin_pagar || 0;
    if (esOk && restantes === 0) {
      estado.setAttribute('data-es', 'Al d\\u00eda \\u2713');
      estado.setAttribute('data-en', 'Up to date \\u2713');
    } else if (esOk && restantes > 0) {
      estado.setAttribute('data-es', 'Al d\\u00eda \\u2713 · ' + restantes + ' clases a favor');
      estado.setAttribute('data-en', 'Up to date \\u2713 · ' + restantes + ' classes ahead');
    } else {
      estado.setAttribute('data-es', (sinPagar || 0) + ' clases sin pagar');
      estado.setAttribute('data-en', (sinPagar || 0) + ' unpaid classes');
    }
    if(esOk){ estado.className += ' badge-green'; } else { estado.className += ' badge-red'; }
    var lista = document.createElement('div');
    lista.className = 'clases-list';
    if(!r.clases_mes || r.clases_mes.length === 0){
      var vacio = document.createElement('div');
      vacio.textContent = 'No hay clases registradas este mes.';
      lista.appendChild(vacio);
    } else {
      var tabla = document.createElement('table');
      var thead = document.createElement('thead');
      var trh = document.createElement('tr');
      var th1 = document.createElement('th'); th1.textContent = 'Fecha';
      var th2 = document.createElement('th'); th2.textContent = 'Hora';
      var th3 = document.createElement('th'); th3.textContent = 'Estado';
      trh.appendChild(th1); trh.appendChild(th2); trh.appendChild(th3);
      thead.appendChild(trh);
      var tbody = document.createElement('tbody');
      for(var j=0;j<r.clases_mes.length;j++){
        var c = r.clases_mes[j];
        var row = document.createElement('tr');
        var fParts = c.fecha ? c.fecha.split('-') : null;
        var fechaTxt = c.fecha;
        if(fParts && fParts.length === 3){
          var anio = parseInt(fParts[0],10);
          var mes = parseInt(fParts[1],10)-1;
          var dia = parseInt(fParts[2],10);
          var d = new Date(anio, mes, dia);
          var dias = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
          var meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
          fechaTxt = dias[d.getDay()] + ' ' + (dia<10?'0'+dia:dia) + ' ' + meses[mes];
        }
        var tdF = document.createElement('td');
        tdF.textContent = fechaTxt;
        var tdH = document.createElement('td');
        tdH.textContent = c.hora || '';
        var tdE = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge badge-estado-clase';
        if(c.estado === 'agendada'){ badge.className += ' badge-gold'; badge.setAttribute('data-es','Agendada'); badge.setAttribute('data-en','Scheduled'); }
        else if(c.estado === 'dada'){ badge.className += ' badge-green'; badge.setAttribute('data-es','Dada'); badge.setAttribute('data-en','Done'); }
        else { badge.className += ' badge-red'; badge.setAttribute('data-es','Cancelada'); badge.setAttribute('data-en','Cancelled'); }
        tdE.appendChild(badge);
        row.appendChild(tdF);
        row.appendChild(tdH);
        row.appendChild(tdE);
        tbody.appendChild(row);
      }
      tabla.appendChild(thead);
      tabla.appendChild(tbody);
      lista.appendChild(tabla);
    }

    // Historial (colapsable)
    var historial = r.historial || [];
    var histContainer = document.createElement('div');
    histContainer.style.marginTop = '0.6rem';
    if (historial.length > 0) {
      var toggle = document.createElement('a');
      toggle.href = 'javascript:void(0)';
      toggle.style.fontSize = '0.8rem';
      toggle.style.display = 'inline-block';
      toggle.style.marginBottom = '0.3rem';
      toggle.setAttribute('data-es', 'Ver historial');
      toggle.setAttribute('data-en', 'View history');
      toggle.textContent = 'Ver historial';
      var panel = document.createElement('div');
      panel.style.display = 'none';
      panel.style.fontSize = '0.8rem';
      var mesesNombres = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
      for (var h = 0; h < historial.length; h++) {
        var item = historial[h];
        var p = document.createElement('p');
        var nombreMes = mesesNombres[item.mes] || item.mes;
        var texto = nombreMes + ' ' + item.anio + ' — ' + item.clases_dadas + ' clases dadas, ' + item.clases_pagas + ' pagas';
        if (item.clases_dadas === item.clases_pagas) {
          texto += ' ✓';
        }
        p.textContent = texto;
        panel.appendChild(p);
      }
      toggle.addEventListener('click', function(){
        panel.style.display = (panel.style.display === 'none' || panel.style.display === '') ? 'block' : 'none';
      });
      histContainer.appendChild(toggle);
      histContainer.appendChild(panel);
    }

    bloque.appendChild(titulo);
    bloque.appendChild(metrics);
    bloque.appendChild(estado);
    bloque.appendChild(lista);
    bloque.appendChild(histContainer);
    cont.appendChild(bloque);
  }

  // Puzzle diario (desde backend para evitar CORS)
  var puzzleCont = document.getElementById('puzzle-content');
  if (puzzleCont) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/portal/api/puzzle_diario');
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== 4) return;
      if (xhr.status !== 200) {
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      var data;
      try {
        data = JSON.parse(xhr.responseText || '{}');
      } catch (e) {
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      if (!data || data.error) {
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      var puzzle = data.puzzle || {};
      var game = data.game || {};
      var container = document.createElement('div');
      container.style.display = 'flex';
      container.style.flexDirection = 'column';
      container.style.gap = '0.5rem';

      if (game.id) {
        var img = document.createElement('img');
        img.src = 'https://lichess1.org/game/export/gif/thumbnail/' + game.id + '.gif';
        img.className = 'puzzle-img';
        img.alt = 'Puzzle del dia';
        container.appendChild(img);
      }

      var meta = document.createElement('div');
      meta.style.fontSize = '0.8rem';

      if (puzzle.rating) {
        var diff = document.createElement('div');
        diff.textContent = 'Elo ' + puzzle.rating;
        meta.appendChild(diff);
      }

      if (puzzle.themes && puzzle.themes.length) {
        var themes = document.createElement('div');
        themes.textContent = 'Temas: ' + puzzle.themes.join(', ');
        meta.appendChild(themes);
      }

      container.appendChild(meta);

      console.log('puzzle data:', JSON.stringify(data));
      if (puzzle.id) {
        var link = document.createElement('a');
        link.href = 'https://lichess.org/training/daily';
        link.setAttribute('data-es', 'Ver puzzle del día en Lichess');
        link.setAttribute('data-en', 'View daily puzzle on Lichess');
        link.target = '_blank';
        link.className = 'btn';
        link.style.marginTop = '0.5rem';
        link.textContent = 'Ver puzzle del día en Lichess';
        container.appendChild(link);
      }

      puzzleCont.innerHTML = '';
      puzzleCont.appendChild(container);
    };
    xhr.send();
  }

  // Cargar recordatorios (simple, para el primer alumno en sesión)
  var contRecLista = document.getElementById('recordatorios-lista');
  var contRecForm = document.getElementById('recordatorios-form');
  if (contRecLista && contRecForm) {
    fetch('/portal/api/recordatorios').then(function(r){ return r.json(); }).then(function(datos){
      if (!datos || !datos.length) {
        contRecLista.innerHTML = '<p style="font-size:0.82rem;color:var(--text-muted)">Sin recordatorios configurados.</p>';
      } else {
        var html = '<ul style="list-style:none;padding-left:0;font-size:0.82rem">';
        for (var i=0;i<datos.length;i++) {
          var d = datos[i];
          var textoTiempo = minutosATexto(d.minutos_antes || 0);
          var desc = textoTiempo + ' antes — ' + d.alcance + ' — ' + d.canal + (d.mail_destino ? ' ('+d.mail_destino+')' : '');
          html += '<li style="margin-bottom:0.25rem">'+desc+' <button class="btn" style="padding:0.1rem 0.4rem;font-size:0.75rem" onclick="borrarRecordatorio('+d.id+')">X</button></li>';
        }
        html += '</ul>';
        contRecLista.innerHTML = html;
      }
      var activos = (datos || []).length;
      if (activos >= 3) {
        contRecForm.innerHTML = '<p style="font-size:0.82rem;color:var(--text-muted)">Límite alcanzado (3).</p>';
        return;
      }
      var mailDefault = '';
      if (resumen && resumen.length > 0 && resumen[0].mail_responsable) {
        mailDefault = resumen[0].mail_responsable;
      }
      var fhtml = '';
      fhtml += '<div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:flex-end">';
      fhtml += '<div><label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.2rem">Tiempo antes</label>';
      fhtml += '<select id="rec-tiempo" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.4rem 0.6rem;border-radius:4px;font-size:0.82rem">';
      fhtml += '<option value="30">30 min</option><option value="60">1 hora</option><option value="120">2 horas</option><option value="1440">24 horas</option></select></div>';
      fhtml += '<div><label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.2rem">Alcance</label>';
      fhtml += '<select id="rec-alcance" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.4rem 0.6rem;border-radius:4px;font-size:0.82rem"><option value="todas">Todas mis clases futuras</option><option value="proxima">Solo la próxima clase</option></select></div>';
      fhtml += '<div><label style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;display:block;margin-bottom:0.2rem">Mail</label>';
      fhtml += '<input id="rec-mail" type="email" value="'+mailDefault+'" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:0.4rem 0.6rem;border-radius:4px;font-size:0.82rem;min-width:220px"></div>';
      fhtml += '<button class="btn" type="button" onclick="crearRecordatorio()">Guardar recordatorio</button>';
      fhtml += '</div>';
      contRecForm.innerHTML = fhtml;
    }).catch(function(){});
  }
})();

function minutosATexto(min) {
  if (min < 60) return min + ' min';
  if (min === 60) return '1 hora';
  if (min < 1440) return (min/60) + ' horas';
  if (min === 1440) return '24 horas';
  return (min/60) + ' horas';
}

function crearRecordatorio() {
  var selT = document.getElementById('rec-tiempo');
  var selA = document.getElementById('rec-alcance');
  var mailEl = document.getElementById('rec-mail');
  if (!selT || !selA || !mailEl) return;
  var minutos = parseInt(selT.value, 10);
  var alcance = selA.value;
  var mail = mailEl.value.trim();
  if (!mail) { alert('Ingresá un mail destino.'); return; }
  fetch('/portal/api/recordatorios', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({minutos_antes: minutos, alcance: alcance, canal: 'mail', mail_destino: mail})
  }).then(function(r){ return r.json(); }).then(function(res){
    if (!res.ok) {
      alert('Error: ' + (res.error || 'No se pudo guardar el recordatorio'));
    } else {
      location.reload();
    }
  }).catch(function(){
    alert('Error de conexión.');
  });
}

function borrarRecordatorio(id) {
  if (!confirm('¿Borrar este recordatorio?')) return;
  fetch('/portal/api/recordatorios/' + id, {method: 'DELETE'}).then(function(r){ return r.json(); }).then(function(res){
    if (!res.ok) {
      alert('Error: ' + (res.error || 'No se pudo borrar el recordatorio'));
    } else {
      location.reload();
    }
  }).catch(function(){
    alert('Error de conexión.');
  });
}
</script>
"""


PORTAL_HTML_UNAUTHORIZED = PORTAL_HTML.replace(
    "{PORTAL_CONTENT}",
    """
<div class="card">
  <h2 id="unauth-title">Acceso no autorizado</h2>
  <p class="unauth-msg" id="unauth-text"
     data-es="Tu cuenta no est\\u00e1 asociada a ning\\u00fan alumno. Si cre\\u00e9s que esto es un error, escribinos por WhatsApp."
     data-en="Your account is not linked to any student. If you think this is a mistake, please contact us via WhatsApp.">
    Tu cuenta no est\\u00e1 asociada a ning\\u00fan alumno. Si cre\\u00e9s que esto es un error, escribinos por WhatsApp.
  </p>
</div>
""",
)

