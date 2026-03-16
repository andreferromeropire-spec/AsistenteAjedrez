import os
import json
from datetime import datetime, date

import requests
from flask import Blueprint, Response, request, session, redirect

from database import get_connection
from calendar_google import crear_flow_google


portal_bp = Blueprint("portal", __name__)


def portal_login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("portal_alumno_id"):
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


def _buscar_alumno_por_lichess(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM alumnos WHERE lower(lichess_username) = lower(?) AND activo = 1",
        (username,),
    ).fetchone()
    conn.close()
    return row


def _buscar_alumno_por_mail(mail):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM alumnos WHERE lower(mail) = lower(?) AND activo = 1",
        (mail,),
    ).fetchone()
    conn.close()
    return row


def _pagina_no_autorizado():
    html = PORTAL_HTML_UNAUTHORIZED
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal")
def portal_login():
    if session.get("portal_alumno_id"):
        return redirect("/portal/home")
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", PORTAL_LOGIN_CONTENT)
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal/auth/lichess")
def portal_auth_lichess():
    client_id = os.environ.get("LICHESS_CLIENT_ID")
    if not client_id:
        return _pagina_no_autorizado()
    state = os.urandom(16).hex()
    session["portal_lichess_state"] = state
    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/lichess/callback"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
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

    client_id = os.environ.get("LICHESS_CLIENT_ID")
    client_secret = os.environ.get("LICHESS_CLIENT_SECRET")
    redirect_uri = "https://asistenteajedrez-production.up.railway.app/portal/auth/lichess/callback"

    try:
        token_resp = requests.post(
            "https://lichess.org/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
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

        alumno = _buscar_alumno_por_lichess(username)
        if not alumno:
            return _pagina_no_autorizado()

        session["portal_alumno_id"] = alumno["id"]
        session["portal_nombre"] = alumno["nombre"]
        _crear_sesion_portal(alumno["id"], username)
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

        alumno = _buscar_alumno_por_mail(email)
        if not alumno:
            return _pagina_no_autorizado()

        session["portal_alumno_id"] = alumno["id"]
        session["portal_nombre"] = alumno["nombre"]
        _crear_sesion_portal(alumno["id"], None)
        return redirect("/portal/home")
    except Exception:
        return _pagina_no_autorizado()


@portal_bp.route("/portal/home")
@portal_login_required
def portal_home():
    alumno_id = session.get("portal_alumno_id")
    nombre = session.get("portal_nombre", "")
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    hoy = date.today()
    mes = hoy.month
    anio = hoy.year

    clases = conn.execute(
        """
        SELECT fecha, hora, estado
        FROM clases
        WHERE alumno_id = ?
          AND substr(fecha, 1, 7) = ?
        ORDER BY fecha, hora
        """,
        (alumno_id, f"{anio:04d}-{mes:02d}"),
    ).fetchall()

    pago = conn.execute(
        """
        SELECT 1 FROM pagos
        WHERE alumno_id = ?
          AND strftime('%m', fecha) = ?
          AND strftime('%Y', fecha) = ?
        LIMIT 1
        """,
        (alumno_id, f"{mes:02d}", f"{anio:04d}"),
    ).fetchone()

    conn.close()

    estado_pago = "al_dia" if pago else "pendiente"
    _marcar_sesion_activa(alumno_id)

    clases_items = []
    for c in clases:
        clases_items.append(
            {
                "fecha": c["fecha"],
                "hora": c["hora"] or "",
                "estado": c["estado"],
            }
        )

    contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)
    contenido = contenido.replace("{CLASES_JSON}", json.dumps(clases_items))
    contenido = contenido.replace("{ESTADO_PAGO}", estado_pago)
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal/logout")
def portal_logout():
    session.pop("portal_alumno_id", None)
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
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:15px}
body{font-family:'DM Sans',sans-serif;background:#0c1018;color:#d0dce8;min-height:100vh}
header{display:flex;align-items:center;justify-content:space-between;padding:0.9rem 1.5rem;background:#161e28;border-bottom:1px solid #253040;box-shadow:0 2px 12px rgba(0,0,0,0.4)}
.header-left{display:flex;align-items:center;gap:0.7rem}
.header-left h1{font-family:'Playfair Display',serif;font-size:1.05rem;color:#4d8fd4}
.lang-toggle{display:flex;align-items:center;gap:0.3rem;font-size:0.8rem}
.lang-toggle button{background:#1c2530;border:1px solid #253040;color:#d0dce8;padding:0.25rem 0.6rem;border-radius:4px;cursor:pointer;font-size:0.78rem}
.lang-toggle button.active{border-color:#4d8fd4;background:rgba(77,143,212,0.12)}
main{padding:1.5rem 1.5rem;max-width:720px;margin:0 auto}
.card{background:#161e28;border:1px solid #253040;border-radius:8px;padding:1.25rem 1.4rem;box-shadow:0 2px 10px rgba(0,0,0,0.4);margin-bottom:1rem}
.card h2{font-family:'Playfair Display',serif;font-size:1.15rem;margin-bottom:0.5rem;color:#4d8fd4}
.card p{font-size:0.9rem;color:#b8ccdf;margin-bottom:0.4rem}
.btn-row{display:flex;gap:0.6rem;margin-top:0.8rem;flex-wrap:wrap}
.btn{background:#1c2530;border:1px solid #253040;color:#d0dce8;padding:0.45rem 0.9rem;border-radius:4px;cursor:pointer;font-size:0.82rem;display:inline-flex;align-items:center;gap:0.4rem;text-decoration:none}
.btn:hover{border-color:#4d8fd4}
.status-ok{color:#4a9e7a}
.status-bad{color:#c0524a}
.clases-list{margin-top:0.5rem;font-size:0.85rem}
.clase-item{display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid #1a2438}
.clase-item:last-child{border-bottom:none}
.clase-meta{font-size:0.8rem;color:#6a8faa}
.unauth-msg{font-size:0.9rem;color:#b8ccdf;line-height:1.5}
.unauth-msg strong{color:#4d8fd4}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <span style="font-size:1.4rem">&#9823;</span>
    <h1 id="portal-title">Alumno Portal</h1>
  </div>
  <div class="lang-toggle">
    <span id="lang-label">Idioma:</span>
    <button type="button" id="btn-es" class="active">ES</button>
    <button type="button" id="btn-en">EN</button>
  </div>
</header>
<main>
  {PORTAL_CONTENT}
</main>
<script>
(function(){
  var lang = localStorage.getItem('portal_lang') || 'es';
  function setLang(l){
    lang = l;
    localStorage.setItem('portal_lang', l);
    var esBtn = document.getElementById('btn-es');
    var enBtn = document.getElementById('btn-en');
    if(esBtn && enBtn){
      if(l === 'es'){ esBtn.classList.add('active'); enBtn.classList.remove('active'); }
      else{ enBtn.classList.add('active'); esBtn.classList.remove('active'); }
    }
    var el;
    el = document.getElementById('portal-title');
    if(el){ el.textContent = (l === 'es') ? 'Alumno Portal' : 'Student Portal'; }
    el = document.getElementById('login-subtitle');
    if(el){ el.textContent = (l === 'es') ? 'Acceso para alumnos' : 'Student access'; }
    el = document.getElementById('login-btn-lichess');
    if(el){ el.textContent = (l === 'es') ? 'Entrar con Lichess' : 'Sign in with Lichess'; }
    el = document.getElementById('login-btn-google');
    if(el){ el.textContent = (l === 'es') ? 'Entrar con Google' : 'Sign in with Google'; }
    el = document.getElementById('home-saludo');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('home-estado');
    if(el){ el.textContent = (l === 'es') ? el.getAttribute('data-es') : el.getAttribute('data-en'); }
    el = document.getElementById('home-clases-titulo');
    if(el){ el.textContent = (l === 'es') ? 'Clases del mes' : 'This month lessons'; }
    el = document.getElementById('home-logout');
    if(el){ el.textContent = (l === 'es') ? 'Salir' : 'Logout'; }
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
  <h2 id="login-title">Alumno Portal</h2>
  <p id="login-subtitle">Acceso para alumnos</p>
  <div class="btn-row">
    <a href="/portal/auth/lichess" class="btn" id="login-btn-lichess">Entrar con Lichess</a>
    <a href="/portal/auth/google" class="btn" id="login-btn-google">Entrar con Google</a>
  </div>
</div>
"""


PORTAL_HOME_CONTENT = """
<div class="card">
  <h2 id="home-saludo" data-es="Hola, {NOMBRE}" data-en="Hi, {NOMBRE}">Hola, {NOMBRE}</h2>
  <p id="home-estado" data-es="" data-en=""></p>
  <div class="clases-list" id="home-clases"></div>
  <div style="margin-top:0.8rem">
    <a href="/portal/logout" class="btn" id="home-logout">Salir</a>
  </div>
</div>
<script>
(function(){
  var clases = {CLASES_JSON};
  var estado = '{ESTADO_PAGO}';
  var estadoEl = document.getElementById('home-estado');
  if(estadoEl){
    if(estado === 'al_dia'){
      estadoEl.setAttribute('data-es', 'Estado de pagos: Al d\\u00eda \\u2713');
      estadoEl.setAttribute('data-en', 'Payments: Up to date \\u2713');
    } else {
      estadoEl.setAttribute('data-es', 'Estado de pagos: Pendiente \\u2717');
      estadoEl.setAttribute('data-en', 'Payments: Pending \\u2717');
    }
  }
  var cont = document.getElementById('home-clases');
  if(cont){
    if(!clases || clases.length === 0){
      cont.textContent = 'No hay clases registradas este mes.';
    } else {
      for(var i=0;i<clases.length;i++){
        var c = clases[i];
        var row = document.createElement('div');
        row.className = 'clase-item';
        var left = document.createElement('div');
        left.textContent = c.fecha + ' ' + (c.hora || '');
        var right = document.createElement('div');
        right.className = 'clase-meta';
        right.textContent = c.estado;
        row.appendChild(left);
        row.appendChild(right);
        cont.appendChild(row);
      }
    }
  }
})();
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

