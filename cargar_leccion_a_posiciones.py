"""
Carga las posiciones clave de una lección extraída (ver extraer_leccion.py)
al banco de posiciones (tabla `posiciones`), calculando el FEN real de cada
una al reproducir las jugadas confirmadas con un motor de ajedrez — no
confía en que el modelo haya calculado el FEN él mismo.

Uso:
    python cargar_leccion_a_posiciones.py <ruta_a_leccion.json>

El índice de jugada que da el modelo (jugada_hasta_indice) puede tener algún
desvío ocasional de +/-1 jugada — conviene revisar las posiciones cargadas
antes de usarlas en una clase real.
"""

import sys
import json
from datetime import datetime

import chess

from database import get_connection


def calcular_fens(jugadas):
    """fens[i] = FEN después de reproducir jugadas[0:i]. fens[0] = posición inicial."""
    board = chess.Board()
    fens = [board.fen()]
    for san in jugadas:
        board.push_san(san)
        fens.append(board.fen())
    return fens


def _origen_de(leccion):
    partida = leccion.get("partida_analizada") or {}
    identificada = partida.get("identificada")
    return "transcript: " + (identificada or leccion.get("tema_principal") or "clase")


def _cargar_posiciones(leccion, conn, origen, verbose=False):
    """Inserta las posiciones clave de la partida analizada (si hay una),
    saltando cualquier (fen, origen) que ya exista para que re-cargar el
    mismo JSON dos veces no duplique filas."""
    partida = leccion.get("partida_analizada") or {}
    jugadas = partida.get("jugadas_confirmadas_por_transcript") or []
    posiciones_clave = partida.get("posiciones_clave") or []

    if not jugadas or not posiciones_clave:
        if verbose:
            print("No hay jugadas o posiciones clave para cargar en este JSON.")
        return 0

    try:
        fens = calcular_fens(jugadas)
    except Exception as e:
        if verbose:
            print(
                f"  No se pudieron reproducir las jugadas ({e}) — no se cargan "
                "posiciones, pero la lección sigue guardándose en la biblioteca."
            )
        return 0

    nivel_a_dificultad = {"principiante": 1, "intermedio": 2, "avanzado": 3}
    dificultad = nivel_a_dificultad.get(leccion.get("nivel_alumno_estimado"))

    insertadas = 0
    for pos in posiciones_clave:
        idx = pos.get("jugada_hasta_indice")
        if idx is None or idx < 0 or idx >= len(fens):
            if verbose:
                print(f"  omitido (índice inválido {idx}): {pos.get('momento')}")
            continue
        fen = fens[idx]
        tema = pos.get("concepto_asociado") or ""

        ya_existe = conn.execute(
            "SELECT 1 FROM posiciones WHERE fen = ? AND origen = ?", (fen, origen)
        ).fetchone()
        if ya_existe:
            if verbose:
                print(f"  ya existía, no se duplica ({tema}): {pos.get('momento')}")
            continue

        conn.execute(
            "INSERT INTO posiciones (fen, origen, dificultad, temas, creado) VALUES (?,?,?,?,?)",
            (fen, origen, dificultad, tema, datetime.utcnow().isoformat()),
        )
        insertadas += 1
        if verbose:
            print(f"  cargada ({tema}): {pos.get('momento')}\n    FEN: {fen}")

    return insertadas


def _cargar_leccion_biblioteca(leccion, conn, origen, verbose=False):
    """Guarda el contenido pedagógico (conceptos, errores corregidos, temas)
    en la biblioteca `lecciones`, exista o no una partida continua para
    reconstruir posiciones. Idempotente por (origen, resumen_clase)."""
    resumen = leccion.get("resumen_clase")

    ya_existe = conn.execute(
        "SELECT id FROM lecciones WHERE origen = ? AND resumen_clase = ?",
        (origen, resumen),
    ).fetchone()
    if ya_existe:
        if verbose:
            print(f"  lección ya estaba en la biblioteca (id {ya_existe[0]})")
        return ya_existe[0]

    temas_tag = ",".join(leccion.get("temas_tag") or [])
    cursor = conn.execute(
        """INSERT INTO lecciones
           (tema_principal, resumen_clase, nivel_alumno_estimado, conceptos,
            errores_y_correcciones, temas_tag, origen, creado)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            leccion.get("tema_principal"),
            resumen,
            leccion.get("nivel_alumno_estimado"),
            json.dumps(leccion.get("conceptos") or [], ensure_ascii=False),
            json.dumps(leccion.get("errores_y_correcciones") or [], ensure_ascii=False),
            temas_tag,
            origen,
            datetime.utcnow().isoformat(),
        ),
    )
    if verbose:
        print(f"  lección guardada en la biblioteca (id {cursor.lastrowid})")
    return cursor.lastrowid


def cargar_desde_dict(leccion, conn=None, verbose=False):
    """Núcleo reutilizable: recibe el dict ya parseado de una lección (mismo
    formato que devuelve extraer_leccion.py), guarda su contenido en la
    biblioteca `lecciones` y, si hay una partida continua, carga sus
    posiciones clave a `posiciones` — todo contra la conexión dada (o de
    get_connection() por default: local en desarrollo, la del volumen de
    Railway si corre en el servidor). Ambas cargas son idempotentes: volver
    a pasar el mismo JSON no duplica filas. Devuelve
    {"posiciones_cargadas": n, "leccion_id": id}."""
    origen = _origen_de(leccion)

    conn_propia = conn is None
    if conn_propia:
        conn = get_connection()

    posiciones_cargadas = _cargar_posiciones(leccion, conn, origen, verbose=verbose)
    leccion_id = _cargar_leccion_biblioteca(leccion, conn, origen, verbose=verbose)

    conn.commit()
    if conn_propia:
        conn.close()
    return {"posiciones_cargadas": posiciones_cargadas, "leccion_id": leccion_id}


def cargar(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as f:
        leccion = json.load(f)
    try:
        return cargar_desde_dict(leccion, verbose=True)
    except Exception as e:
        print(f"No se pudieron reproducir las jugadas ({e}) — no se carga nada.")
        return {"posiciones_cargadas": 0, "leccion_id": None}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cargar_leccion_a_posiciones.py <ruta_a_leccion.json>")
        sys.exit(1)
    resultado = cargar(sys.argv[1])
    print(
        f"\n{resultado['posiciones_cargadas']} posiciones cargadas al banco `posiciones`. "
        f"Lección en biblioteca: id {resultado['leccion_id']}."
    )
