"""
Carga y filtra puzzles tácticos desde el CSV de Lichess (lichess_db_puzzle.csv).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# Niveles de dificultad (usar en todo el proyecto)
BEGINNER = {"label": "Principiante", "elo_min": 0, "elo_max": 800}
INTER = {"label": "Intermedio", "elo_min": 800, "elo_max": 1400}
ADVANCED = {"label": "Avanzado", "elo_min": 1400, "elo_max": 9999}

# Ruta por defecto al CSV (carpeta puzzles junto al paquete)
DEFAULT_PUZZLE_CSV: Path = Path(__file__).parent / "puzzles" / "lichess_db_puzzle.csv"

# Columnas requeridas del CSV Lichess
REQUIRED_COLUMNS = ["PuzzleId", "FEN", "Moves", "Rating", "Themes"]

# Temas válidos para filtrar
VALID_THEMES = frozenset(
    {"hangingPiece", "pin", "fork", "skewer", "mateIn1", "mateIn2"}
)


def load_puzzles(filepath: str) -> pd.DataFrame:
    """
    Carga el CSV de puzzles de Lichess.
    Lanza FileNotFoundError si el archivo no existe.
    Lanza ValueError si faltan columnas esperadas (PuzzleId, FEN, Moves, Rating, Themes).
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de puzzles: {filepath}")
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias en el CSV: {missing}. "
            f"Esperadas: {REQUIRED_COLUMNS}"
        )
    return df


def filter_puzzles(
    df: pd.DataFrame,
    themes: list[str] | None,
    elo_min: int,
    elo_max: int,
    n: int,
    max_per_theme: int | None = None,
) -> list[dict]:
    """
    Filtra por Rating entre elo_min y elo_max; si themes no es None,
    filtra filas donde Themes contenga al menos uno de los temas.
    Devuelve n puzzles aleatorios como lista de dicts; si hay menos de n, devuelve todos.
    """
    out = df[(df["Rating"] >= elo_min) & (df["Rating"] <= elo_max)].copy()
    if themes is not None:
        def has_any_theme(themes_cell: str) -> bool:
            if pd.isna(themes_cell):
                return False
            themes_in_row = str(themes_cell).split()
            return any(t in themes_in_row for t in themes)
        out = out[out["Themes"].apply(has_any_theme)]
    n = min(n, len(out))
    if n <= 0:
        return []
    sampled = out.sample(n=n, random_state=None)
    sampled_list = sampled.to_dict(orient="records")
    if max_per_theme is None:
        return sampled_list
    conteos: dict[str, int] = {}
    resultado: list[dict] = []
    for puzzle in sampled_list:
        themes_str = puzzle.get("Themes", "")
        if isinstance(themes_str, str) and themes_str:
            tema_principal = themes_str.split()[0]
        else:
            tema_principal = ""
        count_actual = conteos.get(tema_principal, 0)
        if count_actual < max_per_theme:
            resultado.append(puzzle)
            conteos[tema_principal] = count_actual + 1
    return resultado


if __name__ == "__main__":
    import sys
    path = str(DEFAULT_PUZZLE_CSV)
    if len(sys.argv) > 1:
        path = sys.argv[1]
    print("Test puzzle_loader")
    try:
        df = load_puzzles(path)
        print(f"  Filas cargadas: {len(df)}")
        print(f"  Columnas: {list(df.columns)}")
        filtered = filter_puzzles(df, themes=["pin", "fork"], elo_min=800, elo_max=1200, n=3)
        print(f"  filter_puzzles(pin|fork, 800-1200, n=3) -> {len(filtered)} puzzles")
        if filtered:
            print(f"  Primer puzzle keys: {list(filtered[0].keys())}")
    except FileNotFoundError as e:
        print(f"  (esperado si no hay CSV) {e}")
    except ValueError as e:
        print(f"  Error columnas: {e}")
