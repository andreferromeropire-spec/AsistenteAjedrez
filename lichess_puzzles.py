"""
Sugiere puzzles reales de Lichess para una lección de la biblioteca, a partir
de sus `temas_tag` (español, inventados por extraer_leccion.py) y el nivel
estimado del alumno.

Reutiliza el CSV y las funciones de trainer/puzzle_loader.py — no hay una
segunda copia de la base de puzzles ni de la lógica de filtrado.

Los "Themes" de Lichess son un vocabulario fijo (~60 valores). No cubren
patrones con nombre coloquial (ej. "kiss of death") — para esos casos el
mapeo cae en el tema más parecido disponible; es una aproximación, no una
búsqueda por patrón geométrico sobre el FEN.
"""

from trainer.puzzle_loader import load_puzzles, filter_puzzles, DEFAULT_PUZZLE_CSV

# temas_tag (español, ver SISTEMA en extraer_leccion.py) -> Themes de Lichess.
# Tags sin entrada acá simplemente no aportan al filtro (no rompen nada).
MAPEO_TEMAS_A_LICHESS = {
    "pin": ["pin"],
    "clavada": ["pin"],
    "fork_doble_ataque": ["fork"],
    "ataque_a_la_descubierta": ["discoveredAttack"],
    "doble_jaque": ["doubleCheck"],
    "atraccion": ["attraction"],
    "deflection": ["deflection"],
    "seguridad_del_rey": ["exposedKing", "kingsideAttack"],
    "calculo_de_capturas": ["hangingPiece", "advantage"],
    "conversion_de_ventaja": ["advantage", "endgame"],
    "sacrificio_por_actividad": ["sacrifice"],
    "desarrollo_de_piezas": ["opening"],
    "control_del_centro": ["opening"],
    "enroque": ["opening", "exposedKing"],
    "jaque_mate": ["mate"],
    "jaque_en_una_jugada": ["mateIn1"],
    "vision_de_jaques": ["mateIn1", "mateIn2"],
    "descarte_prematuro_de_jugadas": ["mateIn2", "mateIn3"],
    "visualizacion_sin_tablero": ["mateIn2", "mateIn3"],
    "peon_aislado": ["endgame"],
    "fianchetto": ["opening"],
}

NIVEL_A_ELO = {
    "principiante": (0, 800),
    "intermedio": (800, 1400),
    "avanzado": (1400, 9999),
}


def _temas_lichess(temas_tag):
    resultado = []
    for t in temas_tag or []:
        for lichess_theme in MAPEO_TEMAS_A_LICHESS.get(t, []):
            if lichess_theme not in resultado:
                resultado.append(lichess_theme)
    return resultado or None


def sugerir_puzzles(temas_tag, nivel_alumno_estimado, n=5):
    """Devuelve hasta n puzzles reales de Lichess como lista de dicts
    {puzzle_id, fen, moves, rating, themes, lichess_url}. Si no hay match
    de temas, devuelve puzzles del rango de elo sin filtrar por tema."""
    themes = _temas_lichess(temas_tag)
    elo_min, elo_max = NIVEL_A_ELO.get(nivel_alumno_estimado, (0, 9999))

    df = load_puzzles(str(DEFAULT_PUZZLE_CSV))
    encontrados = filter_puzzles(df, themes, elo_min, elo_max, n=n, max_per_theme=2)

    return [
        {
            "puzzle_id": p["PuzzleId"],
            "fen": p["FEN"],
            "moves": p["Moves"],
            "rating": int(p["Rating"]),
            "themes": p["Themes"],
            "lichess_url": f"https://lichess.org/training/{p['PuzzleId']}",
        }
        for p in encontrados
    ]
