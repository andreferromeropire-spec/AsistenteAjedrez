import json
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, Response, request, session, jsonify, redirect

from portal_routes import portal_login_required
from database import get_connection
from position_check_ia import generar_feedback, MAX_TURNOS, CHECKLIST

position_check_bp = Blueprint("position_check", __name__)


def _escape(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _alumno_actual():
    alumno_ids = session.get("portal_alumno_ids") or []
    # Igual que en portal_home/trainer: tomamos el primer alumno como contexto
    # principal hasta que exista un selector de hijo para representantes con
    # varios alumnos vinculados a la misma cuenta.
    return alumno_ids[0] if alumno_ids else None


def _nombre_alumno(conn, alumno_id):
    row = conn.execute("SELECT nombre FROM alumnos WHERE id = ?", (alumno_id,)).fetchone()
    return row["nombre"] if row else ""


def _posicion_aleatoria(conn):
    return conn.execute("SELECT id, fen FROM posiciones ORDER BY RANDOM() LIMIT 1").fetchone()


def _posicion_por_id(conn, posicion_id):
    return conn.execute("SELECT id, fen FROM posiciones WHERE id = ?", (posicion_id,)).fetchone()


def _posicion_para_sesion(conn, intento):
    """Posición que le corresponde a este alumno ahora mismo: la del intento
    en curso si hay uno; si no, la que ya se sorteó y quedó en sesión (para
    que la página y el envío del primer mensaje usen siempre la misma); si
    no hay ninguna todavía, sortea una nueva y la deja guardada en sesión."""
    if intento:
        posicion = _posicion_por_id(conn, intento["posicion_id"])
        if posicion:
            return posicion
        session.pop("pc_intento_id", None)

    posicion_id = session.get("pc_posicion_id")
    posicion = _posicion_por_id(conn, posicion_id) if posicion_id else None
    if posicion:
        return posicion

    posicion = _posicion_aleatoria(conn)
    if posicion:
        session["pc_posicion_id"] = posicion["id"]
    else:
        session.pop("pc_posicion_id", None)
    return posicion


def _cargar_intento(conn, intento_id, alumno_id):
    return conn.execute(
        "SELECT * FROM position_check_intentos WHERE id = ? AND alumno_id = ?",
        (intento_id, alumno_id),
    ).fetchone()


def _render_turno(turno):
    if turno["tipo"] == "alumno":
        texto = _escape(turno["texto"]).replace("\n", "<br>")
        return f'<div class="pc-turno pc-turno--alumno"><div class="pc-turno__label"><span class="pc-turno__icono">&#9823;</span>Vos</div><div class="pc-turno__texto">{texto}</div></div>'

    partes = []
    reconocido = turno.get("reconocido") or []
    omitido = turno.get("omitido") or []
    if reconocido:
        items = "".join(f"<li>{_escape(r)}</li>" for r in reconocido)
        partes.append(f'<p class="pc-bien">Viste bien:</p><ul>{items}</ul>')
    if omitido:
        items = "".join(f"<li>{_escape(o)}</li>" for o in omitido)
        partes.append(f'<p class="pc-falta">Todavía no consideraste:</p><ul>{items}</ul>')
    if turno.get("pregunta_seguimiento"):
        partes.append(f'<p class="pc-pregunta">{_escape(turno["pregunta_seguimiento"])}</p>')
    if turno.get("cierre"):
        partes.append(f'<p class="pull-quote">{_escape(turno["cierre"])}</p>')
    cuerpo = "".join(partes)
    return f'<div class="pc-turno pc-turno--ia"><div class="pc-turno__label"><span class="pc-turno__icono">&#9816;</span>Entrenador</div><div class="pc-turno__texto">{cuerpo}</div></div>'


QC_CSS = """
:root {
  --qc-paper: #EDE6D3; --qc-paper-dim: #E4DBC4; --qc-ink: #211D16; --qc-ink-soft: #4A4437;
  --qc-ink-faint: #8A8069; --qc-board: #1D140C; --qc-olive: #6B4226; --qc-olive-deep: #4A2E18;
  --qc-rust: #B0552B; --qc-rust-deep: #8C4220; --qc-brass: #A6863F; --qc-line: rgba(33,29,22,0.14);
}
* { box-sizing: border-box; }
body {
  background: var(--qc-paper); color: var(--qc-ink);
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; margin: 0;
}
h1 { font-family: "Fraunces", Georgia, serif; font-weight: 600; }
a { color: var(--qc-olive); }
"""

EXTRA_CSS = """
.pc-wrap { max-width: 980px; margin: 0 auto; padding: 32px 24px 64px; }
.pc-back { font-size: 0.9rem; color: var(--qc-ink-faint); text-decoration: none; }
.pc-back:hover { color: var(--qc-olive); }
.pc-wordmark { display: flex; align-items: center; gap: 10px; margin-top: 16px; }
.pc-wordmark__mark { width: 22px; height: 33px; flex-shrink: 0; }
.pc-wordmark__texto { font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--qc-ink-faint); }
.pc-title { margin: 6px 0 4px; font-size: 1.9rem; }
.pc-intro { color: var(--qc-ink-soft); max-width: 60ch; margin-bottom: 24px; }
.pc-layout { display: block; }
.pc-board-col { margin-bottom: 24px; }
.pc-board { max-width: 380px; margin: 0 auto; background: var(--qc-board); padding: 10px; border-radius: 8px; }
.pc-board img { width: 100%; display: block; border-radius: 4px; }
.pc-chat-col { min-width: 0; }
@media (min-width: 880px) {
  .pc-layout { display: grid; grid-template-columns: 380px 1fr; gap: 32px; align-items: start; }
  .pc-board-col { position: sticky; top: 24px; margin-bottom: 0; }
}
.pc-turno { margin-bottom: 16px; padding: 14px 18px; border-radius: 8px; line-height: 1.5; }
.pc-turno--alumno { background: var(--qc-paper-dim); border: 1px solid var(--qc-line); }
.pc-turno--ia { background: #fff; border: 1px solid var(--qc-line); }
.pc-turno__label { font-family: "IBM Plex Mono", monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--qc-ink-faint); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.pc-turno__icono { font-size: 1rem; color: var(--qc-olive); }
.pc-turno--alumno .pc-turno__icono { color: var(--qc-rust); }
.pc-bien { color: var(--qc-olive-deep); font-weight: 600; margin: 10px 0 2px; }
.pc-falta { color: var(--qc-rust-deep); font-weight: 600; margin: 10px 0 2px; }
.pc-turno--ia ul { margin: 4px 0 0; padding-left: 20px; }
.pc-pregunta { font-style: italic; margin-top: 10px; }
.pull-quote { border-left: 2px solid var(--qc-rust); padding-left: 14px; font-family: "Fraunces", Georgia, serif; font-size: 1.15rem; font-style: italic; font-weight: 500; line-height: 1.35; color: var(--qc-ink); margin: 12px 0 0; }
.pc-turno--loading .pc-turno__texto { color: var(--qc-ink-faint); display: flex; align-items: center; gap: 8px; }
.pc-spinner { width: 14px; height: 14px; border: 2px solid var(--qc-line); border-top-color: var(--qc-olive); border-radius: 50%; animation: pc-spin 0.7s linear infinite; display: inline-block; }
@keyframes pc-spin { to { transform: rotate(360deg); } }
.pc-input-row { position: relative; }
#pc-input { width: 100%; box-sizing: border-box; padding: 12px 44px 12px 12px; font-family: inherit; font-size: 1rem; border: 1px solid var(--qc-line); border-radius: 6px; background: #fff; color: var(--qc-ink); resize: vertical; }
#pc-input:focus { outline: 2px solid var(--qc-rust); outline-offset: 1px; }
.pc-mic { position: absolute; right: 8px; top: 8px; width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--qc-line); background: #fff; cursor: pointer; font-size: 1rem; line-height: 1; }
.pc-mic--activo { background: var(--qc-rust); border-color: var(--qc-rust-deep); }
.pc-actions { margin-top: 10px; display: flex; gap: 12px; align-items: center; }
#pc-enviar { background: var(--qc-olive); color: var(--qc-paper); border: none; padding: 10px 20px; border-radius: 6px; font-size: 1rem; cursor: pointer; }
#pc-enviar:disabled { opacity: 0.5; cursor: default; }
#pc-enviar:hover:not(:disabled) { background: var(--qc-olive-deep); }
.pc-error { color: var(--qc-rust-deep); }
.pc-terminado { background: #fff; border: 1px solid var(--qc-line); border-radius: 8px; padding: 18px; }
.pc-checklist { margin-top: 18px; background: #fff; border: 1px solid var(--qc-line); border-radius: 8px; padding: 14px 16px; }
.pc-checklist__titulo { font-family: "IBM Plex Mono", monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--qc-ink-faint); margin: 0 0 8px; }
.pc-checklist ol { margin: 0; padding-left: 20px; font-size: 0.88rem; }
.pc-checklist li { margin-bottom: 8px; }
.pc-checklist li strong { color: var(--qc-olive-deep); }
.pc-checklist__fuente { font-size: 0.72rem; color: var(--qc-ink-faint); margin-top: 10px; }
"""


def _checklist_html():
    items = "".join(
        f'<li><strong>{_escape(c["nombre"])}</strong> — {_escape(c["detalle"])}</li>'
        for c in CHECKLIST
    )
    return (
        '<div class="pc-checklist"><p class="pc-checklist__titulo">Qué revisar</p>'
        f'<ol>{items}</ol>'
        '<p class="pc-checklist__fuente">Adaptado de los desequilibrios de Jeremy Silman '
        '(<em>How to Reassess Your Chess</em>).</p></div>'
    )


WORDMARK_HTML = (
    '<div class="pc-wordmark">'
    '<svg class="pc-wordmark__mark" viewBox="0 0 1024 1536" aria-hidden="true">'
    '<rect width="1024" height="1536" fill="var(--qc-board)"/>'
    '<g transform="translate(0,1536) scale(0.1,-0.1)" fill="var(--qc-paper)" stroke="none">'
    '<path d="M6487 14807 c-636 -326 -1447 -857 -2042 -1338 -66 -53 -149 -121 -185 -150 -356 -287 -814 -741 -1082 -1069 -586 -719 -922 -1440 -1019 -2190 -16 -126 -17 -487 -1 -625 64 -544 280 -1036 670 -1526 269 -339 518 -572 1287 -1210 986 -819 1425 -1262 1847 -1869 221 -318 399 -728 477 -1100 52 -245 67 -596 36 -833 -67 -511 -283 -1002 -649 -1472 -271 -349 -604 -657 -983 -911 -64 -42 -89 -64 -75 -64 77 0 499 108 687 176 140 50 296 113 310 124 6 4 48 24 94 43 177 77 505 273 726 435 487 358 911 847 1150 1327 209 421 305 822 307 1290 1 283 -29 535 -93 790 -176 705 -552 1337 -1173 1973 -320 327 -552 534 -1261 1127 -711 593 -945 849 -1110 1211 -92 202 -129 376 -129 609 -1 259 37 418 163 680 137 284 380 600 638 827 101 90 279 228 294 228 10 0 19 -39 19 -84 0 -65 49 -284 83 -376 50 -132 112 -232 206 -332 164 -174 319 -249 611 -298 336 -55 470 -100 644 -214 147 -98 320 -279 413 -436 38 -63 124 -240 147 -301 l23 -61 70 94 c95 128 208 291 339 493 154 236 197 312 188 327 -12 22 -123 177 -194 273 -37 50 -80 108 -96 131 -16 22 -51 71 -79 109 -89 120 -227 308 -366 496 -280 380 -667 910 -857 1174 -32 44 -89 123 -127 175 -132 183 -273 386 -290 420 -72 140 -100 327 -75 505 47 324 268 831 612 1400 61 101 72 125 57 125 -6 0 -101 -46 -212 -103z"/>'
    '<path d="M3512 6493 c128 -260 197 -463 235 -683 22 -135 22 -398 -1 -515 -63 -323 -220 -614 -520 -965 -56 -64 -148 -171 -207 -236 -362 -408 -574 -727 -713 -1075 -335 -840 -32 -1744 759 -2257 247 -161 516 -264 819 -317 124 -21 126 -20 61 26 -247 173 -439 454 -512 748 -25 101 -30 382 -9 496 49 261 194 562 410 848 113 151 131 173 321 391 213 246 246 284 318 373 157 193 293 430 356 620 54 165 65 240 66 443 0 208 -10 268 -76 475 -127 399 -492 913 -1014 1428 -114 113 -338 317 -347 317 -2 0 22 -53 54 -117z"/>'
    "</g></svg>"
    '<span class="pc-wordmark__texto">Quiet Center</span>'
    "</div>"
)

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&'
    'family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" '
    'rel="stylesheet">'
)


def _pagina_html(nombre, fen, turnos, terminado, sin_posicion=False):
    if sin_posicion:
        cuerpo = "<p>Todavía no hay una posición cargada para Position Check. Avisale a Andrea.</p>"
        return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Position Check</title>
{FONTS_LINK}
<style>{QC_CSS}{EXTRA_CSS}</style></head><body>
<div class="pc-wrap" style="max-width:640px;">
{WORDMARK_HTML}
<h1 class="pc-title">Position Check</h1>{cuerpo}
<p><a class="pc-back" href="/portal/home">&larr; Volver al portal</a></p>
</div></body></html>"""

    board_url = "https://lichess1.org/export/fen.gif?" + urlencode(
        {"fen": fen, "theme": "brown", "piece": "cburnett"}
    )
    turnos_html = "".join(_render_turno(t) for t in turnos)
    saludo = "Hola" + (", " + _escape(nombre) if nombre else "")

    mic_boton = '<button type="button" id="pc-mic" class="pc-mic" title="Dictar por voz" hidden>&#127908;</button>'

    if not turnos:
        placeholder = (
            "Material, seguridad de los reyes, centro, actividad de las piezas, "
            "estructura de peones, amenazas del rival, planes, jugadas candidatas..."
        )
        formulario = f"""
<div class="pc-input-row"><textarea id="pc-input" rows="8" placeholder="{placeholder}"></textarea>{mic_boton}</div>
<div class="pc-actions"><button id="pc-enviar">Enviar análisis</button></div>
<p id="pc-error" class="pc-error" hidden></p>"""
    elif terminado:
        formulario = """
<div class="pc-terminado"><p><strong>Este intento terminó.</strong></p>
<p><a href="/portal/position-check/nuevo">Empezar de nuevo</a></p></div>"""
    else:
        formulario = f"""
<div class="pc-input-row"><textarea id="pc-input" rows="5" placeholder="Tu respuesta..."></textarea>{mic_boton}</div>
<div class="pc-actions"><button id="pc-enviar">Responder</button></div>
<p id="pc-error" class="pc-error" hidden></p>"""

    script = "" if terminado else """
<script>
(function () {
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function renderIaTurno(datos) {
    var partes = [];
    if (datos.reconocido && datos.reconocido.length) {
      partes.push('<p class="pc-bien">Viste bien:</p><ul>' + datos.reconocido.map(function (r) { return "<li>" + escapeHtml(r) + "</li>"; }).join("") + "</ul>");
    }
    if (datos.omitido && datos.omitido.length) {
      partes.push('<p class="pc-falta">Todavía no consideraste:</p><ul>' + datos.omitido.map(function (o) { return "<li>" + escapeHtml(o) + "</li>"; }).join("") + "</ul>");
    }
    if (datos.pregunta_seguimiento) {
      partes.push('<p class="pc-pregunta">' + escapeHtml(datos.pregunta_seguimiento) + "</p>");
    }
    if (datos.cierre) {
      partes.push('<p class="pull-quote">' + escapeHtml(datos.cierre) + "</p>");
    }
    return '<div class="pc-turno pc-turno--ia"><div class="pc-turno__label"><span class="pc-turno__icono">&#9816;</span>Entrenador</div><div class="pc-turno__texto">' + partes.join("") + "</div></div>";
  }
  function enviar() {
    var input = document.getElementById("pc-input");
    var boton = document.getElementById("pc-enviar");
    var error = document.getElementById("pc-error");
    var texto = input.value.trim();
    if (!texto) return;
    boton.disabled = true;
    error.hidden = true;
    var turnos = document.getElementById("pc-turnos");
    turnos.insertAdjacentHTML("beforeend", '<div class="pc-turno pc-turno--alumno"><div class="pc-turno__label"><span class="pc-turno__icono">&#9823;</span>Vos</div><div class="pc-turno__texto">' + escapeHtml(texto).replace(/\\n/g, "<br>") + "</div></div>");
    // Limpiar el textarea de inmediato: si queda el texto tal cual mientras
    // se espera la respuesta, parece que el envío no hizo nada (se ve
    // "duplicado" con el turno que se acaba de agregar arriba).
    input.value = "";
    input.placeholder = "Pensando la respuesta...";
    turnos.insertAdjacentHTML("beforeend", '<div class="pc-turno pc-turno--ia pc-turno--loading" id="pc-loading"><div class="pc-turno__label"><span class="pc-turno__icono">&#9816;</span>Entrenador</div><div class="pc-turno__texto"><span class="pc-spinner"></span>Pensando...</div></div>');
    fetch("/portal/position-check/enviar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto: texto })
    }).then(function (res) {
      if (!res.ok) throw new Error("Error del servidor");
      return res.json();
    }).then(function (datos) {
      var loading = document.getElementById("pc-loading");
      if (loading) loading.remove();
      turnos.insertAdjacentHTML("beforeend", renderIaTurno(datos));
      var formulario = document.getElementById("pc-formulario");
      if (datos.terminado) {
        formulario.innerHTML = '<div class="pc-terminado"><p><strong>Este intento terminó.</strong></p><p><a href="/portal/position-check/nuevo">Empezar de nuevo</a></p></div>';
      } else {
        input.placeholder = "Tu respuesta...";
        boton.disabled = false;
      }
    }).catch(function () {
      var loading = document.getElementById("pc-loading");
      if (loading) loading.remove();
      error.textContent = "Hubo un problema enviando tu respuesta. Probá de nuevo.";
      error.hidden = false;
      boton.disabled = false;
      input.placeholder = "Tu respuesta...";
    });
  }
  document.addEventListener("click", function (ev) {
    if (ev.target && ev.target.id === "pc-enviar") enviar();
  });

  // Dictado por voz: API nativa del navegador, sin IA de por medio. Si el
  // navegador no la soporta, el botón queda oculto (arranca hidden en el HTML).
  var micBtn = document.getElementById("pc-mic");
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (micBtn && SR) {
    micBtn.hidden = false;
    var escuchando = false;
    var recognition = null;
    micBtn.addEventListener("click", function () {
      var input = document.getElementById("pc-input");
      if (escuchando) {
        if (recognition) recognition.stop();
        return;
      }
      recognition = new SR();
      recognition.lang = "es-AR";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = function () {
        escuchando = true;
        micBtn.classList.add("pc-mic--activo");
      };
      recognition.onresult = function (ev) {
        var texto = ev.results[0][0].transcript;
        input.value = (input.value ? input.value + " " : "") + texto;
      };
      recognition.onerror = function () {
        escuchando = false;
        micBtn.classList.remove("pc-mic--activo");
      };
      recognition.onend = function () {
        escuchando = false;
        micBtn.classList.remove("pc-mic--activo");
      };
      recognition.start();
    });
  }
})();
</script>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Position Check</title>
{FONTS_LINK}
<style>{QC_CSS}{EXTRA_CSS}</style>
</head>
<body>
<div class="pc-wrap">
  <p><a class="pc-back" href="/portal/home">&larr; Volver al portal</a></p>
  {WORDMARK_HTML}
  <h1 class="pc-title">Position Check</h1>
  <p class="pc-intro">{saludo} — analizá la posición por escrito antes de pensar en la jugada. Material, reyes, centro, piezas, estructura, amenazas, planes, candidatas.</p>
  <div class="pc-layout">
    <div class="pc-board-col">
      <div class="pc-board"><img src="{board_url}" alt="Posición a analizar" width="380" height="380"></div>
      {_checklist_html()}
    </div>
    <div class="pc-chat-col">
      <div id="pc-turnos">{turnos_html}</div>
      <div id="pc-formulario">{formulario}</div>
    </div>
  </div>
</div>
{script}
</body>
</html>"""


@position_check_bp.route("/portal/position-check")
@portal_login_required
def position_check_home():
    alumno_id = _alumno_actual()
    conn = get_connection()

    intento_id = session.get("pc_intento_id")
    intento = _cargar_intento(conn, intento_id, alumno_id) if intento_id else None
    posicion = _posicion_para_sesion(conn, intento)
    if intento and (not posicion or posicion["id"] != intento["posicion_id"]):
        intento = None

    if not posicion:
        conn.close()
        return Response(_pagina_html("", "", [], False, sin_posicion=True), mimetype="text/html")

    nombre = _nombre_alumno(conn, alumno_id)
    turnos = []
    terminado = False
    if intento:
        data = json.loads(intento["feedback_ia_json"] or "{}")
        turnos = data.get("turnos", [])
        terminado = bool(turnos) and turnos[-1].get("tipo") == "ia" and bool(turnos[-1].get("cierre"))
    conn.close()

    html = _pagina_html(nombre, posicion["fen"], turnos, terminado)
    return Response(html, mimetype="text/html")


@position_check_bp.route("/portal/position-check/enviar", methods=["POST"])
@portal_login_required
def position_check_enviar():
    alumno_id = _alumno_actual()
    if not alumno_id:
        return jsonify({"error": "Sesión inválida"}), 401

    body = request.get_json(silent=True) or {}
    texto = (body.get("texto") or "").strip()
    if not texto:
        return jsonify({"error": "Falta el texto"}), 400

    conn = get_connection()

    # Misma regla que en position_check_home: si ya hay un intento en curso,
    # la posición es la del intento; si no, la que ya quedó guardada en
    # sesión para que la página y este envío coincidan siempre.
    intento_id = session.get("pc_intento_id")
    intento = _cargar_intento(conn, intento_id, alumno_id) if intento_id else None
    posicion = _posicion_para_sesion(conn, intento)
    if intento and (not posicion or posicion["id"] != intento["posicion_id"]):
        intento = None
    if not posicion:
        conn.close()
        return jsonify({"error": "No hay posición cargada"}), 400

    if intento:
        data = json.loads(intento["feedback_ia_json"] or "{}")
        turnos = data.get("turnos", [])
        historial_claude = data.get("historial_claude", [])
    else:
        turnos = []
        historial_claude = []

    turno_actual = len([t for t in turnos if t["tipo"] == "alumno"]) + 1
    if turno_actual > MAX_TURNOS:
        conn.close()
        return jsonify({"error": "Este intento ya terminó"}), 400

    turnos.append({"tipo": "alumno", "texto": texto})
    historial_claude.append({"rol": "alumno", "texto": texto})

    datos, texto_ia = generar_feedback(posicion["fen"], historial_claude, turno_actual)

    turnos.append({"tipo": "ia", **datos})
    historial_claude.append({"rol": "ia", "texto": texto_ia})

    feedback_json = json.dumps({"turnos": turnos, "historial_claude": historial_claude}, ensure_ascii=False)
    ahora = datetime.utcnow().isoformat()

    if intento:
        conn.execute(
            "UPDATE position_check_intentos SET feedback_ia_json = ? WHERE id = ?",
            (feedback_json, intento["id"]),
        )
        conn.commit()
        nuevo_id = intento["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO position_check_intentos
               (alumno_id, posicion_id, analisis_escrito, feedback_ia_json, creado)
               VALUES (?,?,?,?,?)""",
            (alumno_id, posicion["id"], texto, feedback_json, ahora),
        )
        conn.commit()
        nuevo_id = cursor.lastrowid

    conn.close()
    session["pc_intento_id"] = nuevo_id

    respuesta = dict(datos)
    respuesta["terminado"] = bool(datos.get("cierre"))
    return jsonify(respuesta)


@position_check_bp.route("/portal/position-check/nuevo")
@portal_login_required
def position_check_nuevo():
    session.pop("pc_intento_id", None)
    session.pop("pc_posicion_id", None)
    return redirect("/portal/position-check")
