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
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", PORTAL_LOGIN_CONTENT)
    return Response(html, mimetype="text/html; charset=utf-8")


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

    resumen = []
    for aid in alumno_ids:
        clases = conn.execute(
            """
            SELECT fecha, hora, estado
            FROM clases
            WHERE alumno_id = ?
              AND substr(fecha, 1, 7) = ?
            ORDER BY fecha, hora
            """,
            (aid, f"{anio:04d}-{mes:02d}"),
        ).fetchall()

        pago = conn.execute(
            """
            SELECT 1 FROM pagos
            WHERE alumno_id = ?
              AND strftime('%m', fecha) = ?
              AND strftime('%Y', fecha) = ?
            LIMIT 1
            """,
            (aid, f"{mes:02d}", f"{anio:04d}"),
        ).fetchone()

        info_alumno = conn.execute(
            "SELECT nombre FROM alumnos WHERE id = ?", (aid,)
        ).fetchone()

        clases_items = []
        for c in clases:
            clases_items.append(
                {
                    "fecha": c["fecha"],
                    "hora": c["hora"] or "",
                    "estado": c["estado"],
                }
            )
        resumen.append(
            {
                "id": aid,
                "nombre": info_alumno["nombre"] if info_alumno else "",
                "clases": clases_items,
                "estado_pago": "al_dia" if pago else "pendiente",
            }
        )

    conn.close()

    if alumno_ids:
        _marcar_sesion_activa(alumno_ids[0])

    contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)
    contenido = contenido.replace("{RESUMEN_JSON}", json.dumps(resumen))
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
main{padding:1.5rem 1.75rem;max-width:960px;margin:0 auto}
.portal-header-sub{font-size:0.8rem;color:var(--text-muted);}
.btn-row{display:flex;gap:0.6rem;margin-top:0.8rem;flex-wrap:wrap}
.unauth-msg{font-size:0.9rem;line-height:1.5}
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
<div class="card">
  <h2 id="home-saludo" data-es="Hola, {NOMBRE}" data-en="Hi, {NOMBRE}">Hola, {NOMBRE}</h2>
  <div id="home-alumnos"></div>
  <div style="margin-top:0.8rem">
    <a href="/portal/logout" class="btn" id="home-logout">Salir</a>
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
    var bloque = document.createElement('div');
    bloque.style.marginTop = '0.75rem';
    var titulo = document.createElement('p');
    titulo.style.fontWeight = '600';
    titulo.textContent = r.nombre;
    var estado = document.createElement('span');
    estado.className = 'badge estado-pago';
    var esOk = r.estado_pago === 'al_dia';
    estado.setAttribute('data-es', esOk ? 'Al d\\u00eda \\u2713' : 'Pendiente');
    estado.setAttribute('data-en', esOk ? 'Up to date \\u2713' : 'Pending');
    if(esOk){ estado.className += ' badge-green'; } else { estado.className += ' badge-red'; }
    var lista = document.createElement('div');
    lista.className = 'clases-list';
    if(!r.clases || r.clases.length === 0){
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
      for(var j=0;j<r.clases.length;j++){
        var c = r.clases[j];
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
    bloque.appendChild(titulo);
    bloque.appendChild(estado);
    bloque.appendChild(lista);
    cont.appendChild(bloque);
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

