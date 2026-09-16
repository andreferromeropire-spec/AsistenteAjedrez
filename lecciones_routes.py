import json
from datetime import datetime

from flask import Blueprint, Response, session, redirect

from portal_routes import portal_login_required, PORTAL_HTML
from database import get_connection

lecciones_bp = Blueprint("lecciones", __name__)


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
    # Igual que en portal_home/position-check: tomamos el primer alumno como
    # contexto principal hasta que exista un selector de hijo para
    # representantes con varios alumnos vinculados a la misma cuenta.
    return alumno_ids[0] if alumno_ids else None


@lecciones_bp.route("/portal/lecciones")
@portal_login_required
def lecciones_lista():
    alumno_id = _alumno_actual()
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    filas = conn.execute(
        """
        SELECT al.id AS asignacion_id, al.motivo, al.asignado_en, al.revisada_en,
               l.id AS leccion_id, l.tema_principal
        FROM alumno_lecciones al
        JOIN lecciones l ON l.id = al.leccion_id
        WHERE al.alumno_id = ?
        ORDER BY al.asignado_en DESC
        """,
        (alumno_id,),
    ).fetchall()
    conn.close()

    if filas:
        items = []
        for f in filas:
            estado = "Leída" if f["revisada_en"] else "Nueva"
            motivo = f'<div class="practicar-row__desc">{_escape(f["motivo"])}</div>' if f["motivo"] else ""
            items.append(
                f"""
                <a class="practicar-row" href="/portal/lecciones/{f['leccion_id']}">
                  <span class="practicar-row__icon">📖</span>
                  <span class="practicar-row__body">
                    <span class="practicar-row__title">{_escape(f['tema_principal']) or 'Lección'} — <em>{estado}</em></span>
                    {motivo}
                  </span>
                </a>
                """
            )
        cuerpo = "".join(items)
    else:
        cuerpo = '<p style="font-size:0.9rem;color:var(--text-dim)">Todavía no tenés lecciones asignadas.</p>'

    contenido = f"""
<div class="card">
  <span class="eyebrow">Lecciones</span>
  <div class="hero-greet">
    <h2>Mis lecciones</h2>
  </div>
  <p style="font-size:0.9rem;color:var(--text-dim);margin:0.6rem 0 1.1rem">
    Lo que fuiste viendo en clase, para repasar cuando quieras.
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


@lecciones_bp.route("/portal/lecciones/<int:leccion_id>")
@portal_login_required
def lecciones_detalle(leccion_id):
    alumno_id = _alumno_actual()
    if not alumno_id:
        return redirect("/portal")

    conn = get_connection()
    asignacion = conn.execute(
        "SELECT id, revisada_en, motivo FROM alumno_lecciones WHERE alumno_id = ? AND leccion_id = ?",
        (alumno_id, leccion_id),
    ).fetchone()
    if not asignacion:
        conn.close()
        return redirect("/portal/lecciones")

    leccion = conn.execute("SELECT * FROM lecciones WHERE id = ?", (leccion_id,)).fetchone()
    if not leccion:
        conn.close()
        return redirect("/portal/lecciones")

    if not asignacion["revisada_en"]:
        conn.execute(
            "UPDATE alumno_lecciones SET revisada_en = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), asignacion["id"]),
        )
        conn.commit()
    conn.close()

    conceptos = json.loads(leccion["conceptos"] or "[]")
    errores = json.loads(leccion["errores_y_correcciones"] or "[]")
    temas = [t for t in (leccion["temas_tag"] or "").split(",") if t]

    bloques_conceptos = "".join(
        f"""
        <div class="next-class" style="align-items:flex-start">
          <div class="next-class__icon">♟</div>
          <div>
            <div class="next-class__eyebrow">{_escape(c.get('nombre'))}</div>
            <div class="next-class__value" style="font-weight:400;font-size:0.92rem">{_escape(c.get('explicacion_dada'))}</div>
          </div>
        </div>
        """
        for c in conceptos
    ) or '<p style="font-size:0.9rem;color:var(--text-dim)">Sin conceptos registrados.</p>'

    bloques_errores = "".join(
        f"""
        <div class="next-class" style="align-items:flex-start">
          <div class="next-class__icon">✦</div>
          <div>
            <div class="next-class__eyebrow">{_escape(e.get('principio_general'))}</div>
            <div class="next-class__value" style="font-weight:400;font-size:0.92rem">
              {_escape(e.get('error'))} → {_escape(e.get('correccion'))}
            </div>
          </div>
        </div>
        """
        for e in errores
    )

    chips = "".join(
        f'<span class="eyebrow" style="margin:0.2rem 0.3rem 0 0;display:inline-block">{_escape(t)}</span>'
        for t in temas
    )

    puzzles = json.loads(leccion["puzzles_sugeridos"] or "[]")
    bloques_puzzles = "".join(
        f"""
        <a class="practicar-row" href="{_escape(p.get('lichess_url'))}" target="_blank" rel="noopener">
          <span class="practicar-row__icon">♟</span>
          <span class="practicar-row__body">
            <span class="practicar-row__title">Puzzle #{_escape(p.get('puzzle_id'))} (rating {_escape(p.get('rating'))})</span>
            <span class="practicar-row__desc">{_escape(p.get('themes'))}</span>
          </span>
        </a>
        """
        for p in puzzles
    )

    motivo_html = (
        f'<p style="font-size:0.9rem;color:var(--text-dim)"><em>{_escape(asignacion["motivo"])}</em></p>'
        if asignacion["motivo"]
        else ""
    )

    contenido = f"""
<div class="card">
  <span class="eyebrow">Lección</span>
  <div class="hero-greet">
    <h2>{_escape(leccion['tema_principal']) or 'Lección'}</h2>
  </div>
  {motivo_html}
  <p style="font-size:0.95rem;margin:0.6rem 0 1.1rem">{_escape(leccion['resumen_clase'])}</p>

  <h3 style="margin-top:1.4rem">Conceptos</h3>
  {bloques_conceptos}

  {"<h3 style='margin-top:1.4rem'>Errores y correcciones</h3>" + bloques_errores if errores else ""}

  <div style="margin-top:1.2rem">{chips}</div>

  {"<h3 style='margin-top:1.4rem'>Practicá</h3><div class='practicar-links'>" + bloques_puzzles + "</div>" if puzzles else ""}

  <div class="btn-row" style="margin-top:1.2rem">
    <a href="/portal/lecciones" class="btn btn-sm">← Volver a mis lecciones</a>
  </div>
</div>
"""
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    return Response(html, mimetype="text/html; charset=utf-8")
