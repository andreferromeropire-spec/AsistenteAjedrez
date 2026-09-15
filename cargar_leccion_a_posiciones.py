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


def cargar(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as f:
        leccion = json.load(f)

    partida = leccion.get("partida_analizada") or {}
    jugadas = partida.get("jugadas_confirmadas_por_transcript") or []
    posiciones_clave = partida.get("posiciones_clave") or []

    if not jugadas or not posiciones_clave:
        print("No hay jugadas o posiciones clave para cargar en este JSON.")
        return 0

    try:
        fens = calcular_fens(jugadas)
    except Exception as e:
        print(f"No se pudieron reproducir las jugadas ({e}) — no se carga nada.")
        return 0

    nivel_a_dificultad = {"principiante": 1, "intermedio": 2, "avanzado": 3}
    dificultad = nivel_a_dificultad.get(leccion.get("nivel_alumno_estimado"))

    identificada = partida.get("identificada")
    origen = "transcript: " + (identificada or leccion.get("tema_principal") or "clase")

    conn = get_connection()
    insertadas = 0
    for pos in posiciones_clave:
        idx = pos.get("jugada_hasta_indice")
        if idx is None or idx < 0 or idx >= len(fens):
            print(f"  omitido (índice inválido {idx}): {pos.get('momento')}")
            continue
        fen = fens[idx]
        tema = pos.get("concepto_asociado") or ""

        conn.execute(
            "INSERT INTO posiciones (fen, origen, dificultad, temas, creado) VALUES (?,?,?,?,?)",
            (fen, origen, dificultad, tema, datetime.utcnow().isoformat()),
        )
        insertadas += 1
        print(f"  cargada ({tema}): {pos.get('momento')}\n    FEN: {fen}")

    conn.commit()
    conn.close()
    return insertadas


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cargar_leccion_a_posiciones.py <ruta_a_leccion.json>")
        sys.exit(1)
    n = cargar(sys.argv[1])
    print(f"\n{n} posiciones cargadas al banco `posiciones`.")
