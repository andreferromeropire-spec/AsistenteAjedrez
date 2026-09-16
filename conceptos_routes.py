import json

from flask import Blueprint, Response, session, redirect

from portal_routes import portal_login_required, PORTAL_HTML
from database import get_connection

conceptos_bp = Blueprint("conceptos_portal", __name__)

_BADGE_DOMINIO = {
    "dominado": ("🟢", "Dominado"),
    "en_practica": ("🟡", "En práctica"),
    "necesita_trabajo": ("🔴", "Necesita trabajo"),
}


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
    return alumno_ids[0] if alumno_ids else None


@conceptos_bp.route("/portal/conceptos")
@portal_login_required
def conceptos_lista():
    alumno_id = _alumno_actual()
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    filas = conn.execute(
        """SELECT c.id, c.nombre, ac.estado_dominio, ac.veces_trabajado, ac.ultima_vez_en
           FROM alumno_conceptos ac JOIN conceptos c ON c.id = ac.concepto_id
           WHERE ac.alumno_id = ?
           ORDER BY ac.ultima_vez_en DESC""",
        (alumno_id,),
    ).fetchall()
    conn.close()

    if filas:
        items = []
        for f in filas:
            emoji, etiqueta = _BADGE_DOMINIO.get(f["estado_dominio"], ("⚪", f["estado_dominio"]))
            items.append(
                f"""
                <a class="practicar-row" href="/portal/conceptos/{f['id']}">
                  <span class="practicar-row__icon">{emoji}</span>
                  <span class="practicar-row__body">
                    <span class="practicar-row__title">{_escape(f['nombre'])}</span>
                    <span class="practicar-row__desc">{etiqueta} — trabajado {f['veces_trabajado']} vez(es)</span>
                  </span>
                </a>
                """
            )
        cuerpo = "".join(items)
    else:
        cuerpo = '<p style="font-size:0.9rem;color:var(--text-dim)">Todavía no tenés conceptos registrados.</p>'

    contenido = f"""
<div class="card">
  <span class="eyebrow">Conceptos</span>
  <div class="hero-greet">
    <h2>Mis conceptos</h2>
  </div>
  <p style="font-size:0.9rem;color:var(--text-dim);margin:0.6rem 0 1.1rem">
    Lo que fuiste aprendiendo, con qué tan afianzado lo tenés.
  </p>
  <div class="practicar-links">
    {cuerpo}
  </div>
  <div class="btn-row">
    <a href="/portal/home" class="btn btn-sm">← Volver al portal</a>
  </div>
</div>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


PRACTICA_JS = """
(function() {
  var puzzles = window.__PUZZLES__ || [];
  var indice = 0;
  var cont = document.getElementById('practica-cont');

  function renderPuzzleActual() {
    if (indice >= puzzles.length) {
      cont.innerHTML = '<p class="empty">Terminaste los puzzles de este concepto. Volvé mas tarde por mas.</p>';
      return;
    }
    var puzzle = puzzles[indice];
    var solution = puzzle.moves.split(' ');

    cont.innerHTML = '';

    var meta = document.createElement('div');
    meta.style.marginBottom = '0.6rem';
    meta.style.fontSize = '0.82rem';
    meta.style.color = 'var(--text-dim)';
    meta.textContent = 'Puzzle ' + (indice + 1) + ' de ' + puzzles.length + ' - rating ' + puzzle.rating;
    cont.appendChild(meta);

    var turnLabel = document.createElement('div');
    turnLabel.style.marginBottom = '0.4rem';
    turnLabel.style.fontWeight = '600';
    cont.appendChild(turnLabel);

    var boardWrap = document.createElement('div');
    var boardEl = document.createElement('div');
    boardEl.id = 'practica-board';
    boardWrap.appendChild(boardEl);
    cont.appendChild(boardWrap);

    var status = document.createElement('div');
    status.style.margin = '0.6rem 0';
    status.style.fontSize = '0.9rem';
    cont.appendChild(status);

    var actions = document.createElement('div');
    actions.className = 'btn-row';
    var btnSiguiente = document.createElement('button');
    btnSiguiente.type = 'button';
    btnSiguiente.className = 'btn btn-sm';
    btnSiguiente.textContent = 'Siguiente puzzle';
    btnSiguiente.style.display = 'none';
    var linkLichess = document.createElement('a');
    linkLichess.href = puzzle.lichess_url;
    linkLichess.target = '_blank';
    linkLichess.rel = 'noopener';
    linkLichess.className = 'btn btn-sm';
    linkLichess.textContent = 'Ver en Lichess';
    actions.appendChild(btnSiguiente);
    actions.appendChild(linkLichess);
    cont.appendChild(actions);

    var chessGame = new Chess(puzzle.fen);
    var solveIndex = 0;
    var puzzleSolved = false;
    var awaitingReply = false;
    var studentColor = chessGame.turn();
    var chessBoard = null;

    function setStatus(texto) { status.textContent = texto; }

    function actualizarTurno() {
      if (puzzleSolved) { turnLabel.textContent = ''; return; }
      turnLabel.textContent = (studentColor === 'w') ? 'Jugas con blancas' : 'Jugas con negras';
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
        setStatus('Resuelto.');
        btnSiguiente.style.display = 'inline-block';
      } else {
        setStatus('Tu turno.');
      }
      actualizarTurno();
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
        setStatus('Esa no es la jugada. Proba de nuevo.');
        return 'snapback';
      }
      solveIndex++;
      if (solveIndex >= solution.length) {
        puzzleSolved = true;
        setStatus('Resuelto.');
        btnSiguiente.style.display = 'inline-block';
        actualizarTurno();
      } else {
        setStatus('Bien. El rival responde...');
        awaitingReply = true;
        setTimeout(jugarRespuestaRival, 550);
      }
    }

    function onSnapEnd() { chessBoard.position(chessGame.fen()); }

    var boardSize = Math.min(360, window.innerWidth - 64);
    boardWrap.style.width = boardSize + 'px';
    setTimeout(function() {
      chessBoard = Chessboard('practica-board', {
        position: puzzle.fen,
        orientation: (studentColor === 'w') ? 'white' : 'black',
        draggable: true,
        pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
        width: boardSize,
        onDragStart: onDragStart,
        onDrop: onDrop,
        onSnapEnd: onSnapEnd
      });
      actualizarTurno();
      setStatus('Tu turno.');
    }, 50);

    btnSiguiente.addEventListener('click', function() {
      indice++;
      renderPuzzleActual();
    });
  }

  if (!puzzles.length) {
    cont.innerHTML = '<p class="empty">Todavia no hay puzzles para este concepto.</p>';
  } else if (typeof Chess === 'undefined' || typeof Chessboard === 'undefined') {
    cont.innerHTML = '<p class="empty">No se pudo cargar el tablero.</p>';
  } else {
    renderPuzzleActual();
  }
})();
"""


@conceptos_bp.route("/portal/practicar/concepto/<int:concepto_id>")
@portal_login_required
def practicar_concepto(concepto_id):
    alumno_id = _alumno_actual()
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    relacion = conn.execute(
        "SELECT 1 FROM alumno_conceptos WHERE alumno_id = ? AND concepto_id = ?",
        (alumno_id, concepto_id),
    ).fetchone()
    if not relacion:
        conn.close()
        return redirect("/portal/conceptos")

    concepto = conn.execute("SELECT * FROM conceptos WHERE id = ?", (concepto_id,)).fetchone()
    conn.close()
    if not concepto:
        return redirect("/portal/conceptos")

    from lichess_puzzles import sugerir_puzzles_por_lichess_themes
    try:
        puzzles = sugerir_puzzles_por_lichess_themes(concepto["lichess_themes"], concepto["nivel"], n=5)
    except Exception:
        puzzles = []

    puzzles_json = json.dumps(puzzles, ensure_ascii=False).replace("</script>", "<\\/script>")

    contenido = f"""
<div class="card">
  <span class="eyebrow">Practicá</span>
  <div class="hero-greet">
    <h2>{_escape(concepto['nombre'])}</h2>
  </div>
  <div id="practica-cont" style="margin-top:0.9rem"><p class="empty">Cargando...</p></div>
  <div class="btn-row" style="margin-top:1.2rem">
    <a href="/portal/conceptos/{concepto_id}" class="btn btn-sm">← Volver al concepto</a>
  </div>
</div>
<script>window.__PUZZLES__ = {puzzles_json};</script>
<script>{PRACTICA_JS}</script>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")


@conceptos_bp.route("/portal/conceptos/<int:concepto_id>")
@portal_login_required
def conceptos_detalle(concepto_id):
    alumno_id = _alumno_actual()
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    relacion = conn.execute(
        "SELECT * FROM alumno_conceptos WHERE alumno_id = ? AND concepto_id = ?",
        (alumno_id, concepto_id),
    ).fetchone()
    if not relacion:
        conn.close()
        return redirect("/portal/conceptos")

    concepto = conn.execute("SELECT * FROM conceptos WHERE id = ?", (concepto_id,)).fetchone()
    if not concepto:
        conn.close()
        return redirect("/portal/conceptos")

    lecciones = conn.execute(
        """SELECT l.id, l.tema_principal, al.asignado_en
           FROM leccion_conceptos lc
           JOIN lecciones l ON l.id = lc.leccion_id
           JOIN alumno_lecciones al ON al.leccion_id = l.id AND al.alumno_id = ?
           WHERE lc.concepto_id = ?
           ORDER BY al.asignado_en DESC""",
        (alumno_id, concepto_id),
    ).fetchall()
    conn.close()

    errores = json.loads(concepto["errores_frecuentes"] or "[]")
    emoji, etiqueta = _BADGE_DOMINIO.get(relacion["estado_dominio"], ("⚪", relacion["estado_dominio"]))

    bloques_lecciones = "".join(
        f'<li><a href="/portal/lecciones/{l["id"]}">{_escape(l["tema_principal"])}</a> — {_escape(l["asignado_en"])}</li>'
        for l in lecciones
    ) or "<li>Sin lecciones registradas.</li>"

    bloques_errores = "".join(f"<li>{_escape(e)}</li>" for e in errores)

    contenido = f"""
<div class="card">
  <span class="eyebrow">{emoji} {etiqueta}</span>
  <div class="hero-greet">
    <h2>{_escape(concepto['nombre'])}</h2>
  </div>
  <p style="font-size:0.85rem;color:var(--text-dim)">Primera vez: {_escape(relacion['primera_vez_en'])} · Trabajado {relacion['veces_trabajado']} vez(es) · Última: {_escape(relacion['ultima_vez_en'])}</p>

  {f'<p style="font-size:0.95rem;margin:0.9rem 0">{_escape(concepto["explicacion_pedagogica"])}</p>' if concepto['explicacion_pedagogica'] else ''}
  {f'<p style="font-size:0.9rem;color:var(--text-dim);font-style:italic">{_escape(concepto["ejemplo"])}</p>' if concepto['ejemplo'] else ''}

  {"<h3 style='margin-top:1.2rem'>Errores frecuentes</h3><ul style='margin:0.4rem 0 0 1.1rem;font-size:0.9rem'>" + bloques_errores + "</ul>" if errores else ""}

  <h3 style="margin-top:1.2rem">Clases donde apareció</h3>
  <ul style="margin:0.4rem 0 0 1.1rem;font-size:0.9rem">{bloques_lecciones}</ul>

  <div class="btn-row" style="margin-top:1.2rem;display:flex;gap:0.6rem;flex-wrap:wrap">
    <a href="/portal/practicar/concepto/{concepto_id}" class="btn">Volver a practicar</a>
    <a href="/portal/conceptos" class="btn btn-sm">← Mis conceptos</a>
  </div>
</div>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")
