import os
import json
import hashlib
import base64
from datetime import datetime, date

import requests
from flask import Blueprint, Response, request, session, redirect

from database import get_connection
from calendar_google import crear_flow_google


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

    # Para el trainer, tomamos por ahora el primer alumno como contexto principal
    if alumno_ids:
        session["trainer_alumno_id"] = alumno_ids[0]

    # Para el trainer, tomamos por ahora el primer alumno como contexto principal
    if alumno_ids:
        session["trainer_alumno_id"] = alumno_ids[0]

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
            "SELECT nombre, lichess_study_url FROM alumnos WHERE id = ?", (aid,)
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
                "lichess_study_url": info_alumno["lichess_study_url"] if info_alumno else None,
            }
        )

    conn.close()

    if alumno_ids:
        _marcar_sesion_activa(alumno_ids[0])

    contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)
    contenido = contenido.replace("{RESUMEN_JSON}", json.dumps(resumen))
    contenido = contenido.replace("PORTAL_NOMBRE_JSON", json.dumps(nombre))
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


# @portal_bp.route("/trainer")
#@portal_login_required
#def portal_trainer():
    # Placeholder simple hasta integrar la UI completa del trainer
    #contenido = """
    #<div class="card">
    #<h2 style="font-family:'Playfair Display',serif;font-size:1.4rem;color:var(--gold-light);margin-bottom:0.75rem">Entrenamiento de patrones</h2>
    #<p style="font-size:0.9rem;color:var(--text-muted);margin-bottom:0.75rem">
  #  Próximamente vas a poder resolver ejercicios tácticos interactivos directamente desde este portal.
  #</p>
    #<p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.75rem">
    #Por ahora, podés ver tu resumen de progreso en la sección <strong>Progreso de entrenamiento</strong>.
    #</p>
  #<div style="margin-top:0.75rem">
    #<a href="/portal/entrenamiento" class="btn">Ver mi progreso</a>
  #</div>
#</div>
    #"""
    #html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    #return Response(html, mimetype="text/html; charset=utf-8")


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
               MAX(p.fecha) AS ultima_fecha,
               SUM(CASE WHEN p.resultado = 'correcto' THEN 1 ELSE 0 END) AS correctos,
               SUM(CASE WHEN p.resultado = 'incorrecto' THEN 1 ELSE 0 END) AS incorrectos,
               COALESCE(AVG(p.tiempo_segundos), 0.0) AS tiempo_promedio
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
    mejor_record = None
    for r in rows:
        ejercicios = r["ejercicios"] or 0
        correctos = r["correctos"] or 0
        incorrectos = r["incorrectos"] or 0
        porc = (100.0 * correctos / ejercicios) if ejercicios else 0.0
        tiempo_prom = float(r["tiempo_promedio"] or 0.0)
        if ejercicios:
            ratio = correctos / float(ejercicios)
            if mejor_record is None or ratio > mejor_record["ratio"]:
                mejor_record = {
                    "nombre": r["nombre"],
                    "correctos": correctos,
                    "ejercicios": ejercicios,
                    "porc": porc,
                    "ratio": ratio,
                }
        filas.append(
            "<tr>"
            + "<td>" + (r["nombre"] or "") + "</td>"
            + "<td>" + str(ejercicios) + "</td>"
            + "<td>" + "{:.0f}%".format(porc) + "</td>"
            + "<td>" + "{:.1f}s".format(tiempo_prom) + "</td>"
            + "<td>" + ("{:.1f}".format(r["rating_prom"]) if r["rating_prom"] is not None else "0.0") + "</td>"
            + "<td>" + (r["ultima_fecha"] or "-") + "</td>"
            + "</tr>"
        )
    cuerpo = "".join(filas) if filas else '<tr><td colspan="6" class="empty">Sin ejercicios registrados todavía.</td></tr>'

    resumen_record = ""
    if mejor_record:
        resumen_record = (
            '<div class="next-class">'
            '<div class="next-class__icon">♛</div>'
            '<div><div class="next-class__eyebrow">Mejor registro</div>'
            '<div class="next-class__value">{nombre} — {correctos}/{ejercicios} aciertos ({porc:.0f}%)</div></div>'
            '</div>'
        ).format(
            nombre=mejor_record["nombre"],
            correctos=mejor_record["correctos"],
            ejercicios=mejor_record["ejercicios"],
            porc=mejor_record["porc"],
        )
    contenido = """
<div class="card">
  <span class="eyebrow">Entrenamiento</span>
  <div class="hero-greet">
    <h2>Progreso de patrones</h2>
  </div>
  <p style="font-size:0.9rem;color:var(--text-dim);margin:0.6rem 0 1.1rem">
    Resumen de los ejercicios resueltos por cada alumno asociado a esta cuenta.
  </p>
  """ + resumen_record + """
  <div class="table-wrap" style="margin-top:1rem">
    <table>
      <thead>
        <tr><th>Alumno</th><th>Ejercicios</th><th>% acierto</th><th>Tiempo medio</th><th>Rating medio</th><th>Última actividad</th></tr>
      </thead>
      <tbody>""" + cuerpo + """</tbody>
    </table>
  </div>
  <div class="btn-row">
    <a href="/portal/home" class="btn btn-sm">← Volver al portal</a>
  </div>
</div>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


@portal_bp.route("/portal/logout")
def portal_logout():
    session.pop("portal_alumno_ids", None)
    session.pop("portal_nombre", None)
    return redirect("/login")


PORTAL_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --paper:#EDE6D3;--ink:#211D16;--ink-soft:#4A4437;--ink-faint:#8A8069;
  --accent:#6B4226;--accent-deep:#4A2E18;--accent-pale:#E7CB9C;
  --rust:#B0552B;--rust-deep:#8C4220;--rust-bg:rgba(176,85,43,0.12);
  --green:#3F6B45;--green-bg:rgba(63,107,69,0.13);
  --gold:#A6863F;--gold-bg:rgba(166,134,63,0.14);
  --bg:#F3EEE1;--bg2:#E9E0CB;--surface:#FDFBF5;--surface2:#F1E9D6;
  --line:rgba(33,29,22,0.14);--shadow:rgba(33,29,22,0.10);
  --text:var(--ink);--text-dim:var(--ink-soft);--text-muted:var(--ink-faint);
  --radius-sm:6px;--radius-md:10px;--radius-lg:16px;--radius-pill:999px;
}
[data-theme="dark"]{
  --bg:#1D140C;--bg2:#241A10;--surface:#2A1E14;--surface2:#33251A;
  --line:rgba(237,230,211,0.14);--shadow:rgba(0,0,0,0.35);
  --text:#EDE6D3;--text-dim:#C9BFA9;--text-muted:#93876F;
  --accent:#D8A46C;--accent-deep:#A6863F;--accent-pale:rgba(216,164,108,0.18);
  --rust:#D98A5E;--rust-deep:#B0552B;--rust-bg:rgba(217,138,94,0.16);
  --green:#7FB48A;--green-bg:rgba(127,180,138,0.16);
  --gold:#D3B15C;--gold-bg:rgba(211,177,92,0.16);
}
[data-theme="navy"]{
  --bg:#121620;--bg2:#171C28;--surface:#1B2130;--surface2:#222A3A;
  --line:rgba(214,224,240,0.12);--shadow:rgba(0,0,0,0.45);
  --text:#E7EAF2;--text-dim:#AEB6C8;--text-muted:#6C7488;
  --accent:#C9A54B;--accent-deep:#A6863F;--accent-pale:rgba(201,165,75,0.16);
  --rust:#D98A5E;--rust-deep:#B0552B;--rust-bg:rgba(217,138,94,0.15);
  --green:#7FB48A;--green-bg:rgba(127,180,138,0.15);
  --gold:#C9A54B;--gold-bg:rgba(201,165,75,0.15);
}
html{font-size:16px}
body{font-family:'IBM Plex Sans',-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.55;transition:background .3s ease,color .3s ease;-webkit-font-smoothing:antialiased}
.portal-shell{min-height:100vh;display:flex;flex-direction:column}
h1,h2,h3{font-family:'Fraunces',Georgia,serif;font-weight:600;letter-spacing:-0.01em;line-height:1.12;color:var(--text)}
a{color:inherit;text-decoration:none}
::selection{background:var(--rust);color:var(--paper)}
:focus-visible{outline:2px solid var(--rust);outline-offset:2px;border-radius:3px}

header{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.75rem;background:var(--surface);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:100;box-shadow:0 2px 14px var(--shadow);flex-wrap:wrap}
.header-left{display:flex;align-items:center;gap:0.85rem}
.brand-mark{font-size:1.7rem;color:var(--accent);line-height:1}
.header-left h1{font-size:1.15rem}
.portal-header-sub{font-size:0.78rem;color:var(--text-muted);font-family:'IBM Plex Mono',monospace;letter-spacing:0.02em}
.header-right{display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap}
.theme-group,.lang-toggle{display:flex;border:1px solid var(--line);border-radius:var(--radius-pill);overflow:hidden;background:var(--surface2)}
.theme-btn,.lang-btn{background:transparent;border:none;color:var(--text-dim);padding:0.4rem 0.7rem;cursor:pointer;font-size:0.85rem;font-family:'IBM Plex Mono',monospace;transition:background .15s,color .15s}
.lang-btn{font-size:0.72rem;letter-spacing:0.05em;padding:0.4rem 0.65rem}
.theme-btn.active,.lang-btn.active{background:var(--accent);color:var(--surface)}
.theme-btn:hover:not(.active),.lang-btn:hover:not(.active){background:var(--bg2)}

main{padding:2rem 1.75rem 3rem;max-width:1320px;margin:0 auto;width:100%;flex:1}
.portal-footer{text-align:center;padding:1.5rem;font-size:0.75rem;color:var(--text-muted);font-family:'IBM Plex Mono',monospace}
.portal-footer .dot{margin:0 0.5em;opacity:0.5}

.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:0.72rem;letter-spacing:0.09em;text-transform:uppercase;color:var(--accent);display:inline-flex;align-items:center;gap:0.5em}
[data-theme="navy"] .eyebrow,[data-theme="dark"] .eyebrow{color:var(--gold)}

.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:1.5rem 1.6rem;box-shadow:0 1px 3px var(--shadow);margin-bottom:1.25rem}
.card:last-child{margin-bottom:0}

.hero-greet{margin-bottom:0.4rem}
.hero-greet h2{font-size:clamp(1.6rem,1.3rem + 1.4vw,2.15rem);font-style:italic;font-weight:500;margin-top:0.35rem}
.hero-date{font-size:0.85rem;color:var(--text-muted);margin-top:0.5rem}

.portal-layout{display:grid;grid-template-columns:2fr 1fr;gap:1.5rem;align-items:flex-start;margin-top:1.5rem}
@media(max-width:860px){.portal-layout{grid-template-columns:1fr}.portal-side{order:-1}main{padding:1.25rem 1rem 2.5rem}}

.alumno-block{padding-top:1.4rem;border-top:1px solid var(--line)}
.alumno-block:first-of-type{padding-top:0;border-top:none}
.alumno-cabecera{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}
.alumno-nombre{display:flex;align-items:center;gap:0.7rem}
.study-link{display:inline-block;margin-top:0.15rem;font-size:0.72rem;font-family:'IBM Plex Mono',monospace;color:var(--text-muted)}
.study-link:hover{color:var(--accent)}
.avatar{width:2.35rem;height:2.35rem;border-radius:50%;background:var(--accent-pale);color:var(--accent-deep);display:flex;align-items:center;justify-content:center;font-family:'Fraunces',serif;font-weight:600;font-size:1rem;flex-shrink:0}
.alumno-nombre h3{font-size:1.15rem}

.badge{display:inline-flex;align-items:center;gap:0.4em;padding:0.32rem 0.75rem;border-radius:var(--radius-pill);font-size:0.72rem;font-weight:500;font-family:'IBM Plex Mono',monospace;letter-spacing:0.03em}
.badge::before{content:'';width:0.4em;height:0.4em;border-radius:50%;background:currentColor;flex-shrink:0}
.badge-green{background:var(--green-bg);color:var(--green)}
.badge-red{background:var(--rust-bg);color:var(--rust-deep)}
.badge-gold{background:var(--gold-bg);color:var(--gold)}
.badge-gray{background:var(--bg2);color:var(--text-dim)}
.badge-estado-clase{padding:0.22rem 0.6rem;font-size:0.68rem;text-transform:uppercase}

.next-class{display:flex;align-items:center;gap:1rem;background:var(--accent-pale);border-radius:var(--radius-md);padding:1rem 1.25rem;margin-bottom:1.1rem}
[data-theme="dark"] .next-class,[data-theme="navy"] .next-class{background:var(--surface2);border:1px solid var(--line)}
.next-class__icon{font-size:1.5rem;flex-shrink:0}
.next-class__eyebrow{font-family:'IBM Plex Mono',monospace;font-size:0.68rem;letter-spacing:0.08em;text-transform:uppercase;color:var(--accent-deep);opacity:0.85}
[data-theme="dark"] .next-class__eyebrow,[data-theme="navy"] .next-class__eyebrow{color:var(--text-muted)}
.next-class__value{font-family:'Fraunces',serif;font-size:1.15rem;font-weight:600;margin-top:0.15rem}
.next-class__chip{margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:0.7rem;padding:0.3rem 0.7rem;border-radius:var(--radius-pill);background:var(--surface);color:var(--text-dim);white-space:nowrap}

.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0.7rem;margin-bottom:1.1rem}
.metric{background:var(--surface2);border:1px solid var(--line);border-radius:var(--radius-md);padding:0.85rem 1rem}
.metric-label{font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.09em;font-family:'IBM Plex Mono',monospace;margin-bottom:0.35rem}
.metric-value{font-size:1.4rem;font-weight:500;font-family:'Fraunces',serif;color:var(--text);line-height:1}
.metric-value.green{color:var(--green)}
.metric-value.red{color:var(--rust-deep)}

.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius-md)}
table{width:100%;border-collapse:collapse;font-size:0.85rem}
thead{background:var(--surface2)}
th{padding:0.6rem 0.9rem;text-align:left;font-size:0.66rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--line)}
td{padding:0.6rem 0.9rem;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--surface2)}

.historial-toggle{display:inline-flex;align-items:center;gap:0.3em;font-size:0.8rem;color:var(--accent-deep);cursor:pointer;margin-top:0.85rem}
[data-theme="dark"] .historial-toggle,[data-theme="navy"] .historial-toggle{color:var(--accent)}
.historial-toggle .chevron{display:inline-block;transition:transform .18s ease;font-size:0.75em}
.historial-toggle.open .chevron{transform:rotate(90deg)}
.historial-panel{display:none;margin-top:0.6rem;padding-top:0.6rem;border-top:1px solid var(--line);font-size:0.82rem;color:var(--text-dim)}
.historial-panel p{padding:0.15rem 0}
.historial-panel.open{display:block}

.empty{padding:2rem 1rem;text-align:center;color:var(--text-muted);font-size:0.88rem}

#puzzle-content{font-size:0.85rem;color:var(--text-muted)}
.puzzle-img{width:100%;border-radius:var(--radius-md);border:1px solid var(--line);background:var(--surface2);box-shadow:0 1px 3px var(--shadow)}
.puzzle-board-wrap{background:var(--accent-deep);padding:8px;border-radius:var(--radius-md);box-shadow:0 1px 3px var(--shadow);display:flex;justify-content:center;margin-bottom:0.75rem}
.puzzle-status{font-size:0.82rem;color:var(--text-dim);min-height:1.3em;margin-bottom:0.6rem;font-weight:500}
.puzzle-status--ok{color:var(--green)}
.puzzle-status--error{color:var(--rust-deep)}
.puzzle-turn{font-family:'IBM Plex Mono',monospace;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:0.6rem}
.chip{display:inline-block;padding:0.22rem 0.65rem;border-radius:var(--radius-pill);background:var(--surface2);border:1px solid var(--line);font-size:0.68rem;font-family:'IBM Plex Mono',monospace;color:var(--text-dim);margin:0 0.3rem 0.3rem 0}

.side-card h3{font-size:0.95rem;margin-bottom:0.65rem;display:flex;align-items:center;gap:0.4em}
.practicar-intro{font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem}
.practicar-divider{height:1px;background:var(--line);margin:1.1rem 0}
.practicar-links{display:flex;flex-direction:column;gap:0.5rem}
.practicar-row{display:flex;align-items:flex-start;gap:0.7rem;padding:0.6rem;border-radius:var(--radius-md);transition:background .15s}
.practicar-row:hover{background:var(--surface2)}
.practicar-row__icon{font-size:1.1rem;color:var(--accent);flex-shrink:0;line-height:1.3}
[data-theme="dark"] .practicar-row__icon,[data-theme="navy"] .practicar-row__icon{color:var(--gold)}
.practicar-row__body{display:flex;flex-direction:column;gap:0.15rem}
.practicar-row__title{font-size:0.87rem;font-weight:500;color:var(--text)}
.practicar-row__desc{font-size:0.76rem;color:var(--text-muted)}
.cta-card{background:var(--accent-pale);border:none}
[data-theme="dark"] .cta-card,[data-theme="navy"] .cta-card{background:var(--surface2);border:1px solid var(--accent-deep)}
.cta-card h3{color:var(--accent-deep)}
[data-theme="dark"] .cta-card h3,[data-theme="navy"] .cta-card h3{color:var(--accent)}
.cta-card p{font-size:0.82rem;color:var(--text-dim);margin-bottom:0.85rem}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:0.4em;background:var(--surface2);border:1px solid var(--line);color:var(--text);padding:0.55rem 1rem;border-radius:var(--radius-sm);font-family:'IBM Plex Sans',sans-serif;font-size:0.85rem;font-weight:500;cursor:pointer;transition:border-color .15s,background .15s,transform .1s;text-align:center}
.btn:hover{border-color:var(--accent);background:var(--bg2)}
.btn:active{transform:translateY(1px)}
.btn-primary{background:var(--accent);border-color:var(--accent);color:var(--surface)}
.btn-primary:hover{background:var(--accent-deep);border-color:var(--accent-deep)}
.btn-block{width:100%}
.btn-row{display:flex;gap:0.6rem;margin-top:0.8rem;flex-wrap:wrap}
.btn-sm{padding:0.3rem 0.55rem;font-size:0.75rem}

.field-label{font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-family:'IBM Plex Mono',monospace;display:block;margin-bottom:0.3rem}
.field-input{background:var(--surface2);border:1px solid var(--line);color:var(--text);padding:0.5rem 0.75rem;border-radius:var(--radius-sm);font-family:'IBM Plex Sans',sans-serif;font-size:0.83rem;outline:none;transition:border-color .15s}
.field-input:focus{border-color:var(--accent)}

.rec-item{display:flex;align-items:center;justify-content:space-between;gap:0.6rem;padding:0.5rem 0;border-bottom:1px solid var(--line);font-size:0.82rem}
.rec-item:last-child{border-bottom:none}
.rec-item__text{color:var(--text-dim)}

.unauth-msg{font-size:0.92rem;line-height:1.6;color:var(--text-dim)}

.logo{text-align:center;padding:0.5rem 0 1rem}
.logo .piece{font-size:2.2rem;color:var(--accent);margin-bottom:0.5rem}
.logo h2{font-size:1.3rem}
.logo p{font-size:0.85rem;color:var(--text-muted);margin-top:0.3rem}
"""


PORTAL_HTML = """<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portal de alumnos · Quiet Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,450;0,9..144,600;0,9..144,700;1,9..144,500;1,9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
<style>
""" + PORTAL_CSS + """
</style>
</head>
<body>
<div class="portal-shell">
<header>
  <div class="header-left">
    <span class="brand-mark" aria-hidden="true">&#9823;</span>
    <div>
      <h1 id="portal-title" data-es="Portal de alumnos" data-en="Student Portal">Portal de alumnos</h1>
      <div class="portal-header-sub" id="portal-subtitle" data-es="Quiet Center &mdash; clases de ajedrez" data-en="Quiet Center &mdash; chess lessons">Quiet Center &mdash; clases de ajedrez</div>
    </div>
  </div>
  <div class="header-right">
    <div class="theme-group" role="group" aria-label="Tema">
      <button class="theme-btn active" onclick="setTheme('light',this)" title="Claro" aria-label="Tema claro">&#9728;</button>
      <button class="theme-btn" onclick="setTheme('dark',this)" title="Oscuro" aria-label="Tema oscuro">&#9789;</button>
      <button class="theme-btn" onclick="setTheme('navy',this)" title="Noche" aria-label="Tema noche">&#10022;</button>
    </div>
    <div class="lang-toggle" role="group" aria-label="Idioma">
      <button type="button" class="lang-btn active" id="btn-es">ES</button>
      <button type="button" class="lang-btn" id="btn-en">EN</button>
    </div>
  </div>
</header>
<main>
  {PORTAL_CONTENT}
</main>
<footer class="portal-footer">
  <span>Quiet Center</span><span class="dot">&middot;</span><span id="footer-tagline" data-es="clases de ajedrez, en serio y con calma" data-en="chess lessons, taken seriously and calmly">clases de ajedrez, en serio y con calma</span>
</footer>
</div>
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
      <span class="eyebrow">Tu portal</span>
      <div class="hero-greet">
        <h2 id="home-saludo" data-es="Hola, {NOMBRE}" data-en="Hi, {NOMBRE}">Hola, {NOMBRE}</h2>
      </div>
      <div id="home-alumnos"></div>
      <div class="btn-row">
        <a href="/portal/logout" class="btn btn-sm" id="home-logout">Salir</a>
      </div>
    </div>
  </div>
  <div class="portal-side">
    <div class="card side-card" id="practicar-card">
      <h3>♟ Practicá</h3>
      <p class="practicar-intro">Reforzá lo que vemos en clase.</p>
      <div class="eyebrow" id="puzzle-title" data-es="Puzzle del día" data-en="Daily puzzle">Puzzle del día</div>
      <div id="puzzle-content">Cargando&hellip;</div>
      <div class="practicar-divider"></div>
      <div class="practicar-links">
        <a class="practicar-row" href="/trainer">
          <span class="practicar-row__icon">♞</span>
          <span class="practicar-row__body">
            <span class="practicar-row__title">Ver piezas colgadas</span>
            <span class="practicar-row__desc">Detectá amenazas después de la jugada del rival.</span>
          </span>
        </a>
        <a class="practicar-row" href="/portal/position-check">
          <span class="practicar-row__icon">♛</span>
          <span class="practicar-row__body">
            <span class="practicar-row__title">Analizar una posición</span>
            <span class="practicar-row__desc">Escribí tu análisis y recibí una devolución guiada.</span>
          </span>
        </a>
        <a class="practicar-row" href="/portal/entrenamiento">
          <span class="practicar-row__icon">✦</span>
          <span class="practicar-row__body">
            <span class="practicar-row__title">Mi progreso</span>
            <span class="practicar-row__desc">Ejercicios resueltos y rendimiento.</span>
          </span>
        </a>
      </div>
    </div>
    <div class="card side-card" id="recordatorios-card">
      <h3>♜ Recordatorios</h3>
      <div id="recordatorios-lista"></div>
      <div id="recordatorios-form" style="margin-top:0.75rem"></div>
    </div>
  </div>
</div>
<script>
(function(){
  var resumen = {RESUMEN_JSON};
  var portalNombre = PORTAL_NOMBRE_JSON;
  try {
    if (portalNombre) {
      localStorage.setItem('portal_nombre', portalNombre);
    }
  } catch(e) {}
  var cont = document.getElementById('home-alumnos');
  if(!cont){ return; }
  if(!resumen || resumen.length === 0){
    var p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'No hay clases registradas este mes.';
    cont.appendChild(p);
    return;
  }
  for(var i=0;i<resumen.length;i++){
    var r = resumen[i];
    var clasesMes = r.clases_mes || [];
    var inicial = (r.nombre || '?').trim().charAt(0).toUpperCase();
    if (clasesMes.length === 0) {
      var sinDiv = document.createElement('div');
      sinDiv.className = 'alumno-block';
      var cab0 = document.createElement('div'); cab0.className = 'alumno-cabecera';
      var nw0 = document.createElement('div'); nw0.className = 'alumno-nombre';
      var av0 = document.createElement('div'); av0.className = 'avatar'; av0.textContent = inicial;
      var t0 = document.createElement('h3'); t0.textContent = r.nombre;
      nw0.appendChild(av0); nw0.appendChild(t0);
      cab0.appendChild(nw0);
      sinDiv.appendChild(cab0);
      var st = document.createElement('p');
      st.className = 'empty';
      st.textContent = 'No hay clases registradas este mes.';
      sinDiv.appendChild(st);
      cont.appendChild(sinDiv);
      continue;
    }
    var bloque = document.createElement('div');
    bloque.className = 'alumno-block';

    var cabecera = document.createElement('div'); cabecera.className = 'alumno-cabecera';
    var nombreWrap = document.createElement('div'); nombreWrap.className = 'alumno-nombre';
    var avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.textContent = inicial;
    var nameCol = document.createElement('div');
    var titulo = document.createElement('h3');
    titulo.textContent = r.nombre;
    nameCol.appendChild(titulo);
    if (r.lichess_study_url) {
      var studyLink = document.createElement('a');
      studyLink.className = 'study-link';
      studyLink.href = r.lichess_study_url;
      studyLink.target = '_blank';
      studyLink.rel = 'noopener';
      studyLink.textContent = '♜ Ver estudio en Lichess ↗';
      nameCol.appendChild(studyLink);
    }
    nombreWrap.appendChild(avatar);
    nombreWrap.appendChild(nameCol);
    cabecera.appendChild(nombreWrap);

    // Próxima clase, como banner propio (lo primero que se ve tras el estado)
    var nextBanner = document.createElement('div');
    nextBanner.className = 'next-class';
    var ncIcon = document.createElement('div'); ncIcon.className = 'next-class__icon'; ncIcon.textContent = '♞';
    var ncBody = document.createElement('div');
    var ncEye = document.createElement('div'); ncEye.className = 'next-class__eyebrow'; ncEye.textContent = 'Próxima clase';
    var ncVal = document.createElement('div'); ncVal.className = 'next-class__value';
    ncBody.appendChild(ncEye);
    ncBody.appendChild(ncVal);
    nextBanner.appendChild(ncIcon);
    nextBanner.appendChild(ncBody);
    if (r.proxima_clase && r.proxima_clase.fecha) {
      var fParts = r.proxima_clase.fecha.split('-');
      var fechaTxt = r.proxima_clase.fecha;
      var diasTxt = '';
      if (fParts.length === 3) {
        var anio = parseInt(fParts[0],10);
        var mes = parseInt(fParts[1],10)-1;
        var dia = parseInt(fParts[2],10);
        var d = new Date(anio, mes, dia);
        var dias = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
        var meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
        fechaTxt = dias[d.getDay()] + ' ' + (dia<10?'0'+dia:dia) + ' ' + meses[mes] + ' · ' + (r.proxima_clase.hora || '');
        var hoyDate = new Date(); hoyDate.setHours(0,0,0,0);
        var diffDays = Math.round((d - hoyDate) / 86400000);
        if (diffDays === 0) { diasTxt = 'Hoy'; }
        else if (diffDays === 1) { diasTxt = 'Mañana'; }
        else if (diffDays > 1) { diasTxt = 'En ' + diffDays + ' días'; }
      }
      ncVal.textContent = fechaTxt;
      if (diasTxt) {
        var ncChip = document.createElement('div');
        ncChip.className = 'next-class__chip';
        ncChip.textContent = diasTxt;
        nextBanner.appendChild(ncChip);
      }
    } else {
      ncVal.textContent = 'Sin clases agendadas';
    }

    // Métricas tipo dashboard
    var metrics = document.createElement('div');
    metrics.className = 'metrics';
    var m2 = document.createElement('div'); m2.className = 'metric';
    var l2 = document.createElement('div'); l2.className = 'metric-label'; l2.textContent = 'Clases este mes';
    var v2 = document.createElement('div'); v2.className = 'metric-value'; v2.textContent = r.clases_agendadas || 0;
    m2.appendChild(l2); m2.appendChild(v2);

    var m3 = document.createElement('div'); m3.className = 'metric';
    var l3 = document.createElement('div'); l3.className = 'metric-label'; l3.textContent = 'Dadas';
    var v3 = document.createElement('div'); v3.className = 'metric-value'; v3.textContent = r.clases_dadas || 0;
    m3.appendChild(l3); m3.appendChild(v3);

    var m4 = document.createElement('div'); m4.className = 'metric';
    var l4 = document.createElement('div'); l4.className = 'metric-label'; l4.textContent = 'Clases pagadas';
    var v4 = document.createElement('div'); v4.className = 'metric-value'; v4.textContent = r.clases_pagas || 0;
    m4.appendChild(l4); m4.appendChild(v4);

    var m5 = document.createElement('div'); m5.className = 'metric';
    var l5 = document.createElement('div'); l5.className = 'metric-label'; l5.textContent = 'Clases restantes';
    var v5 = document.createElement('div'); v5.className = 'metric-value'; v5.textContent = r.clases_restantes || 0;
    if ((r.clases_restantes || 0) > 0) { v5.className += ' green'; }
    m5.appendChild(l5); m5.appendChild(v5);

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
    cabecera.appendChild(estado);
    var lista;
    if(!r.clases_mes || r.clases_mes.length === 0){
      lista = document.createElement('p');
      lista.className = 'empty';
      lista.textContent = 'No hay clases registradas este mes.';
    } else {
      lista = document.createElement('div');
      lista.className = 'table-wrap';
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
      toggle.className = 'historial-toggle';
      var toggleLabel = document.createElement('span');
      toggleLabel.textContent = 'Ver historial';
      var toggleChevron = document.createElement('span');
      toggleChevron.className = 'chevron';
      toggleChevron.textContent = '›';
      toggle.appendChild(toggleLabel);
      toggle.appendChild(toggleChevron);
      var panel = document.createElement('div');
      panel.className = 'historial-panel';
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
      (function(t, p){
        t.addEventListener('click', function(){
          t.classList.toggle('open');
          p.classList.toggle('open');
        });
      })(toggle, panel);
      histContainer.appendChild(toggle);
      histContainer.appendChild(panel);
    }

    bloque.appendChild(cabecera);
    bloque.appendChild(nextBanner);
    bloque.appendChild(metrics);
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
        puzzleCont.className = 'empty';
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      var data;
      try {
        data = JSON.parse(xhr.responseText || '{}');
      } catch (e) {
        puzzleCont.className = 'empty';
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      if (!data || data.error) {
        puzzleCont.className = 'empty';
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      var puzzle = data.puzzle || {};
      if (!puzzle.fen || !puzzle.solution || !puzzle.solution.length) {
        puzzleCont.className = 'empty';
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }
      if (typeof Chess === 'undefined' || typeof Chessboard === 'undefined') {
        puzzleCont.className = 'empty';
        puzzleCont.textContent = 'Puzzle no disponible hoy';
        return;
      }

      var container = document.createElement('div');

      var meta = document.createElement('div');
      meta.style.marginBottom = '0.6rem';
      if (puzzle.rating) {
        var diff = document.createElement('span');
        diff.className = 'chip';
        diff.textContent = 'Elo ' + puzzle.rating;
        meta.appendChild(diff);
      }
      if (puzzle.themes && puzzle.themes.length) {
        for (var ti = 0; ti < Math.min(3, puzzle.themes.length); ti++) {
          var themeChip = document.createElement('span');
          themeChip.className = 'chip';
          themeChip.textContent = puzzle.themes[ti];
          meta.appendChild(themeChip);
        }
      }
      container.appendChild(meta);

      var turnLabel = document.createElement('div');
      turnLabel.className = 'puzzle-turn';
      container.appendChild(turnLabel);

      var boardWrap = document.createElement('div');
      boardWrap.className = 'puzzle-board-wrap';
      var boardEl = document.createElement('div');
      boardEl.id = 'lichess-puzzle-board';
      boardWrap.appendChild(boardEl);
      container.appendChild(boardWrap);

      var status = document.createElement('div');
      status.className = 'puzzle-status';
      container.appendChild(status);

      var actions = document.createElement('div');
      actions.className = 'btn-row';
      var btnRetry = document.createElement('button');
      btnRetry.type = 'button';
      btnRetry.className = 'btn btn-sm';
      btnRetry.textContent = 'Reiniciar';
      var linkLichess = document.createElement('a');
      linkLichess.href = 'https://lichess.org/training/' + (puzzle.id || '');
      linkLichess.target = '_blank';
      linkLichess.rel = 'noopener';
      linkLichess.className = 'btn btn-sm';
      linkLichess.textContent = 'Ver en Lichess ↗';
      actions.appendChild(btnRetry);
      actions.appendChild(linkLichess);
      container.appendChild(actions);

      puzzleCont.innerHTML = '';
      puzzleCont.appendChild(container);

      // Motor del puzzle: puzzle.fen es la posición ya lista para que juegue
      // el alumno; puzzle.solution alterna jugada-del-alumno (índices pares)
      // y respuesta automática del rival (índices impares).
      var chessGame = new Chess(puzzle.fen);
      var solution = puzzle.solution;
      var solveIndex = 0;
      var puzzleSolved = false;
      var awaitingReply = false;
      var studentColor = chessGame.turn();
      var chessBoard = null;

      function setStatus(texto, tipo) {
        status.className = 'puzzle-status' + (tipo ? ' puzzle-status--' + tipo : '');
        status.textContent = texto;
      }

      function updateTurnLabel() {
        if (puzzleSolved) { turnLabel.textContent = ''; return; }
        turnLabel.textContent = (studentColor === 'w') ? 'Jugás con blancas' : 'Jugás con negras';
      }

      function jugarRespuestaRival() {
        var replyUci = solution[solveIndex];
        var replyMove = { from: replyUci.slice(0, 2), to: replyUci.slice(2, 4) };
        if (replyUci.length > 4) { replyMove.promotion = replyUci.slice(4); }
        chessGame.move(replyMove);
        chessBoard.position(chessGame.fen());
        solveIndex++;
        awaitingReply = false;
        if (solveIndex >= solution.length) {
          puzzleSolved = true;
          setStatus('¡Resuelto! 🎉', 'ok');
        } else {
          setStatus('Tu turno.', '');
        }
        updateTurnLabel();
      }

      function onDragStart(source, piece) {
        if (puzzleSolved || awaitingReply) { return false; }
        if (chessGame.game_over()) { return false; }
        if ((studentColor === 'w' && piece.search(/^b/) !== -1) ||
            (studentColor === 'b' && piece.search(/^w/) !== -1)) {
          return false;
        }
        if (chessGame.turn() !== studentColor) { return false; }
      }

      function onDrop(source, target) {
        var moveObj = chessGame.move({ from: source, to: target, promotion: 'q' });
        if (moveObj === null) { return 'snapback'; }
        var uciMove = source + target + (moveObj.promotion ? moveObj.promotion : '');
        var esperado = solution[solveIndex];
        if (uciMove !== esperado) {
          chessGame.undo();
          setStatus('Esa no es la jugada. Probá de nuevo.', 'error');
          return 'snapback';
        }
        solveIndex++;
        if (solveIndex >= solution.length) {
          puzzleSolved = true;
          setStatus('¡Resuelto! 🎉', 'ok');
          updateTurnLabel();
        } else {
          setStatus('¡Bien! El rival responde…', 'ok');
          awaitingReply = true;
          setTimeout(jugarRespuestaRival, 550);
        }
      }

      function onSnapEnd() {
        chessBoard.position(chessGame.fen());
      }

      var boardSize = Math.min(320, window.innerWidth - 64);
      boardWrap.style.width = boardSize + 'px';
      // chessboard.js necesita que el contenedor ya esté en el DOM con su
      // tamaño final antes de inicializarse (mismo patrón que trainer.js
      // initBoard) — si se llama en el mismo tick que el appendChild, mide
      // mal el ancho y las piezas quedan amontonadas sin cuadrícula.
      setTimeout(function() {
        chessBoard = Chessboard('lichess-puzzle-board', {
          position: puzzle.fen,
          orientation: (studentColor === 'w') ? 'white' : 'black',
          draggable: true,
          pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
          width: boardSize,
          onDragStart: onDragStart,
          onDrop: onDrop,
          onSnapEnd: onSnapEnd
        });
        updateTurnLabel();
        setStatus('Tu turno.', '');
      }, 50);

      btnRetry.addEventListener('click', function() {
        chessGame = new Chess(puzzle.fen);
        solveIndex = 0;
        puzzleSolved = false;
        awaitingReply = false;
        chessBoard.position(puzzle.fen);
        updateTurnLabel();
        setStatus('Tu turno.', '');
      });
    };
    xhr.send();
  }

  // Cargar recordatorios (simple, para el primer alumno en sesión)
  var contRecLista = document.getElementById('recordatorios-lista');
  var contRecForm = document.getElementById('recordatorios-form');
  if (contRecLista && contRecForm) {
    fetch('/portal/api/recordatorios').then(function(r){ return r.json(); }).then(function(datos){
      if (!datos || !datos.length) {
        contRecLista.innerHTML = '<p class="empty">Sin recordatorios configurados.</p>';
      } else {
        var html = '';
        for (var i=0;i<datos.length;i++) {
          var d = datos[i];
          var textoTiempo = minutosATexto(d.minutos_antes || 0);
          var desc = textoTiempo + ' antes — ' + d.alcance + ' — ' + d.canal + (d.mail_destino ? ' ('+d.mail_destino+')' : '');
          html += '<div class="rec-item"><span class="rec-item__text">'+desc+'</span><button class="btn btn-sm" onclick="borrarRecordatorio('+d.id+')">&times;</button></div>';
        }
        contRecLista.innerHTML = html;
      }
      var activos = (datos || []).length;
      if (activos >= 3) {
        contRecForm.innerHTML = '<p class="empty">Límite alcanzado (3).</p>';
        return;
      }
      var mailDefault = '';
      if (resumen && resumen.length > 0 && resumen[0].mail_responsable) {
        mailDefault = resumen[0].mail_responsable;
      }
      var mailDefaultAttr = String(mailDefault).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
      var fhtml = '';
      fhtml += '<div style="display:flex;flex-wrap:wrap;gap:0.75rem;align-items:flex-end">';
      fhtml += '<div><label class="field-label">Tiempo antes</label>';
      fhtml += '<select id="rec-tiempo" class="field-input">';
      fhtml += '<option value="30">30 min</option><option value="60">1 hora</option><option value="120">2 horas</option><option value="1440">24 horas</option></select></div>';
      fhtml += '<div><label class="field-label">Alcance</label>';
      fhtml += '<select id="rec-alcance" class="field-input"><option value="todas">Todas mis clases futuras</option><option value="proxima">Solo la próxima clase</option></select></div>';
      fhtml += '<div><label class="field-label">Mail</label>';
      fhtml += '<input id="rec-mail" type="email" value="'+mailDefaultAttr+'" class="field-input" style="min-width:200px"></div>';
      fhtml += '<button class="btn btn-primary" type="button" onclick="crearRecordatorio()">Guardar recordatorio</button>';
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

