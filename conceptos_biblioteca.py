"""
Biblioteca global de conceptos ajedrecísticos y patrones de pensamiento —
capa de "diario de aprendizaje" sobre `lecciones` (ver docs/learning-journal-plan.md).

Tres entidades separadas a propósito:
- CONCEPTO GLOBAL (`conceptos`/`patrones_pensamiento`): contenido pedagógico
  reutilizable entre alumnos y lecciones.
- CLASE/LECCIÓN (`leccion_conceptos`/`leccion_patrones`): dónde apareció ese
  concepto, con la redacción puntual de esa clase.
- APRENDIZAJE DEL ALUMNO (`alumno_conceptos`/`alumno_patrones`): la relación
  personal de un alumno con ese concepto (cuántas veces, cuándo).

Todo esto corre una sola vez, al guardar la lección (matching determinístico
con difflib, sin llamada extra a la IA) o al asignarla a un alumno — nunca
al visitar el portal, que es de solo lectura.
"""

import re
import unicodedata
from datetime import datetime
from difflib import get_close_matches

CUTOFF_SIMILITUD = 0.8


def _slugificar(nombre):
    nfkd = unicodedata.normalize("NFKD", nombre or "")
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "_", sin_acentos.lower()).strip("_")
    return slug or "concepto"


def _buscar_o_crear(conn, tabla, nombre, campos_extra):
    """tabla: 'conceptos' o 'patrones_pensamiento'. Devuelve el id existente
    si hay un match exacto o difuso por nombre; si no, crea uno nuevo en
    estado 'borrador' con los campos_extra dados."""
    nombre = (nombre or "").strip()
    if not nombre:
        return None

    slug = _slugificar(nombre)

    fila = conn.execute(f"SELECT id FROM {tabla} WHERE slug = ?", (slug,)).fetchone()
    if fila:
        return fila["id"]

    existentes = conn.execute(f"SELECT id, nombre FROM {tabla}").fetchall()
    nombres_existentes = {e["nombre"]: e["id"] for e in existentes}
    coincidencias = get_close_matches(nombre, nombres_existentes.keys(), n=1, cutoff=CUTOFF_SIMILITUD)
    if coincidencias:
        return nombres_existentes[coincidencias[0]]

    columnas = ["nombre", "slug", "creado"] + list(campos_extra.keys())
    valores = [nombre, slug, datetime.utcnow().isoformat()] + list(campos_extra.values())
    placeholders = ",".join("?" for _ in columnas)
    try:
        cursor = conn.execute(
            f"INSERT INTO {tabla} ({','.join(columnas)}) VALUES ({placeholders})",
            valores,
        )
        return cursor.lastrowid
    except Exception:
        # Colisión de slug entre dos inserts casi simultáneos con nombres
        # levemente distintos que no llegaron al cutoff de similitud —
        # se recupera reusando el que ya quedó insertado, no se duplica.
        fila = conn.execute(f"SELECT id FROM {tabla} WHERE slug = ?", (slug,)).fetchone()
        if fila:
            return fila["id"]
        raise


def vincular_conceptos_y_patrones(conn, leccion_id, leccion):
    """Crea/vincula los conceptos y patrones de pensamiento de una lección
    ya guardada. No llama a la IA — usa lo que ya devolvió extraer_leccion.py."""
    for c in leccion.get("conceptos") or []:
        concepto_id = _buscar_o_crear(
            conn, "conceptos", c.get("nombre"),
            {
                "descripcion_corta": c.get("explicacion_dada"),
                "estado": "borrador",
                "nivel": leccion.get("nivel_alumno_estimado"),
            },
        )
        if concepto_id is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO leccion_conceptos (leccion_id, concepto_id, nota, confianza) VALUES (?,?,?,?)",
            (leccion_id, concepto_id, c.get("explicacion_dada"), c.get("confianza")),
        )

    for p in leccion.get("patrones_pensamiento_detectados") or []:
        patron_id = _buscar_o_crear(
            conn, "patrones_pensamiento", p.get("principio"),
            {"descripcion": p.get("principio"), "estado": "borrador"},
        )
        if patron_id is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO leccion_patrones (leccion_id, patron_id, nota, confianza) VALUES (?,?,?,?)",
            (leccion_id, patron_id, p.get("contexto"), p.get("confianza")),
        )


def _estado_dominio(veces):
    if veces >= 4:
        return "dominado"
    if veces >= 2:
        return "en_practica"
    return "necesita_trabajo"


def _upsert_progreso(conn, tabla_rel, columna_id, alumno_id, entidad_id, leccion_id, contador_col, con_dominio):
    ahora = datetime.utcnow().isoformat()
    fila = conn.execute(
        f"SELECT id, {contador_col} FROM {tabla_rel} WHERE alumno_id = ? AND {columna_id} = ?",
        (alumno_id, entidad_id),
    ).fetchone()

    if fila:
        nuevas_veces = fila[contador_col] + 1
        set_dominio = ", estado_dominio = ?" if con_dominio else ""
        params = [nuevas_veces, leccion_id, ahora]
        if con_dominio:
            params.append(_estado_dominio(nuevas_veces))
        params.append(ahora)
        params.append(fila["id"])
        conn.execute(
            f"""UPDATE {tabla_rel}
                SET {contador_col} = ?, ultima_leccion_id = ?, ultima_vez_en = ?{set_dominio}, actualizado = ?
                WHERE id = ?""",
            params,
        )
    else:
        columnas = ["alumno_id", columna_id, contador_col, "primera_leccion_id", "primera_vez_en",
                    "ultima_leccion_id", "ultima_vez_en", "actualizado"]
        valores = [alumno_id, entidad_id, 1, leccion_id, ahora, leccion_id, ahora, ahora]
        if con_dominio:
            columnas.append("estado_dominio")
            valores.append(_estado_dominio(1))
        conn.execute(
            f"INSERT INTO {tabla_rel} ({','.join(columnas)}) VALUES ({','.join('?' for _ in columnas)})",
            valores,
        )


def actualizar_progreso_alumno(conn, alumno_id, leccion_id):
    """Se llama cuando una lección se ASIGNA a un alumno (no al generarla).
    Actualiza cuántas veces trabajó cada concepto/patrón vinculado a esa
    lección y recalcula su estado de dominio."""
    conceptos = conn.execute(
        "SELECT concepto_id FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)
    ).fetchall()
    for c in conceptos:
        _upsert_progreso(conn, "alumno_conceptos", "concepto_id", alumno_id, c["concepto_id"],
                          leccion_id, "veces_trabajado", con_dominio=True)

    patrones = conn.execute(
        "SELECT patron_id FROM leccion_patrones WHERE leccion_id = ?", (leccion_id,)
    ).fetchall()
    for p in patrones:
        _upsert_progreso(conn, "alumno_patrones", "patron_id", alumno_id, p["patron_id"],
                          leccion_id, "veces_visto", con_dominio=False)
