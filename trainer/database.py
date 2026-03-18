"""
Módulo de persistencia para el entrenador táctico.

Nota:
- La tabla progreso_entrenamiento vive en la base de datos global del proyecto (database.py).
- Si querés guardar progreso agregado desde el trainer hacia esa tabla, hacelo con un helper separado
  en el proyecto principal que importe este módulo o use directamente database.get_connection().
"""


# -----------------------------------------------------------------------------
# ESQUEMA LEGACY LOCAL (sessions/results) - si seguís usando el trainer standalone
# -----------------------------------------------------------------------------
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH: str = str(Path(__file__).parent / "chess_pattern_trainer.db")


def get_local_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Conexión a la DB local del trainer (no la global del proyecto)."""
    path = db_path or DB_PATH
    return sqlite3.connect(path)


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Crea las tablas sessions y results si no existen.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            mode TEXT NOT NULL,
            elo_range TEXT NOT NULL,
            total_exercises INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            puzzle_id TEXT NOT NULL,
            theme TEXT NOT NULL,
            puzzle_rating INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            response_time_ms INTEGER NOT NULL,
            board_zone TEXT,
            prediction_score REAL,
            was_trap INTEGER,
            uncertain INTEGER,
            time_vs_minimum REAL
        )
    """)
    # Asegurar columnas nuevas si la tabla existía con un esquema anterior
    cur = conn.execute("PRAGMA table_info(results)")
    existing_cols = {row[1] for row in cur.fetchall()}
    extra_cols = {
        "prediction_score": "REAL",
        "was_trap": "INTEGER",
        "uncertain": "INTEGER",
        "time_vs_minimum": "REAL",
        "scan_time_ms": "INTEGER",
        "sector_missed": "TEXT",
        "false_positives": "INTEGER",
        "declared_sector": "TEXT",
    }
    for col, col_type in extra_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE results ADD COLUMN {col} {col_type}")
    conn.commit()


def start_session(
    conn: sqlite3.Connection,
    mode: str,
    elo_range: str,
    total: int,
) -> int:
    """
    Inserta una nueva sesión y devuelve su id.
    """
    cur = conn.execute(
        "INSERT INTO sessions (date, mode, elo_range, total_exercises) VALUES (?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), mode, elo_range, total),
    )
    conn.commit()
    return cur.lastrowid


def save_result(
    conn: sqlite3.Connection,
    session_id: int,
    puzzle_id: str,
    theme: str,
    puzzle_rating: int,
    correct: bool,
    response_time_ms: int,
    board_zone: str | None = None,
    prediction_score: float | None = None,
    was_trap: int | None = None,
    uncertain: int | None = None,
    time_vs_minimum: float | None = None,
    scan_time_ms: int | None = None,
    sector_missed: str | None = None,
    false_positives: int | None = None,
) -> None:
    """
    Inserta un resultado de ejercicio. correct se guarda como 1/0.
    Campos adicionales son opcionales y pueden quedar en NULL.
    """
    conn.execute(
        """INSERT INTO results
           (session_id, puzzle_id, theme, puzzle_rating, correct, response_time_ms, board_zone,
            prediction_score, was_trap, uncertain, time_vs_minimum,
            scan_time_ms, sector_missed, false_positives)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            puzzle_id,
            theme,
            puzzle_rating,
            1 if correct else 0,
            response_time_ms,
            board_zone,
            prediction_score,
            was_trap,
            uncertain,
            time_vs_minimum,
            scan_time_ms,
            sector_missed,
            false_positives,
        ),
    )
    conn.commit()


def get_session_stats(conn: sqlite3.Connection, session_id: int) -> dict:
    """
    Retorna total, correct, accuracy (0-100), avg_time_ms, errors_by_theme {theme: count_errors}.
    """
    cur = conn.execute(
        "SELECT correct, response_time_ms, theme FROM results WHERE session_id = ?",
        (session_id,),
    )
    rows = cur.fetchall()
    total = len(rows)
    correct = sum(1 for r in rows if r[0] == 1)
    times = [r[1] for r in rows if r[1] is not None]
    avg_time_ms = sum(times) / len(times) if times else 0.0
    accuracy = (100.0 * correct / total) if total else 0.0
    errors_by_theme: dict[str, int] = {}
    for r in rows:
        if r[0] == 0:
            t = r[2] or "unknown"
            errors_by_theme[t] = errors_by_theme.get(t, 0) + 1
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "avg_time_ms": avg_time_ms,
        "errors_by_theme": errors_by_theme,
    }


# Compatibilidad con esqueleto (init_schema = create_tables, insert_* si se usan en main/session_manager)
def init_schema(conn: sqlite3.Connection) -> None:
    """Crea las tablas si no existen (alias de create_tables)."""
    create_tables(conn)


def insert_session(
    conn: sqlite3.Connection,
    date: str,
    mode: str,
    elo_range: str,
    total_exercises: int,
) -> int:
    """Inserta sesión por fecha explícita; devuelve id."""
    cur = conn.execute(
        "INSERT INTO sessions (date, mode, elo_range, total_exercises) VALUES (?, ?, ?, ?)",
        (date, mode, elo_range, total_exercises),
    )
    conn.commit()
    return cur.lastrowid


def insert_result(
    conn: sqlite3.Connection,
    session_id: int,
    puzzle_id: str,
    theme: str,
    puzzle_rating: int,
    correct: int,
    response_time_ms: int,
    board_zone: Optional[str] = None,
) -> int:
    """Inserta un resultado (correct como int 0/1)."""
    cur = conn.execute(
        """INSERT INTO results
           (session_id, puzzle_id, theme, puzzle_rating, correct, response_time_ms, board_zone,
            prediction_score, was_trap, uncertain, time_vs_minimum)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)""",
        (session_id, puzzle_id, theme, puzzle_rating, correct, response_time_ms, board_zone),
    )
    conn.commit()
    return cur.lastrowid


def get_sessions(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    mode: Optional[str] = None,
) -> list[tuple]:
    """Lista sesiones, opcionalmente filtradas por modo y limitadas."""
    q = "SELECT id, date, mode, elo_range, total_exercises FROM sessions WHERE 1=1"
    params: list = []
    if mode is not None:
        q += " AND mode = ?"
        params.append(mode)
    q += " ORDER BY date DESC"
    if limit is not None:
        q += " LIMIT ?"
        params.append(limit)
    cur = conn.execute(q, params)
    return cur.fetchall()


def get_results_by_session(
    conn: sqlite3.Connection, session_id: int
) -> list[tuple]:
    """Obtiene todos los resultados de una sesión."""
    cur = conn.execute(
        "SELECT id, session_id, puzzle_id, theme, puzzle_rating, correct, response_time_ms, board_zone FROM results WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    return cur.fetchall()


def get_last_session_insights(conn: sqlite3.Connection, current_session_id: int) -> dict | None:
    """
    Retorna insights de la sesión anterior a current_session_id, o None si no existe.
    """
    cur = conn.execute(
        "SELECT id FROM sessions WHERE id < ? ORDER BY id DESC LIMIT 1",
        (current_session_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    prev_id = row[0]
    cur2 = conn.execute(
        "SELECT sector_missed, correct FROM results WHERE session_id = ?",
        (prev_id,),
    )
    rows = cur2.fetchall()
    if not rows:
        return None
    sector_counts = {}
    correct_count = 0
    for sector_missed, correct in rows:
        if sector_missed:
            sector_counts[sector_missed] = sector_counts.get(sector_missed, 0) + 1
        if correct:
            correct_count += 1
    accuracy = int(100 * correct_count / len(rows))
    sector_weakness = None
    if sector_counts:
        worst = max(sector_counts, key=lambda s: sector_counts[s])
        sector_labels = {
            "queenside": "flanco de dama",
            "center": "centro",
            "kingside": "flanco de rey"
        }
        sector_weakness = sector_labels.get(worst, worst)
    return {"accuracy": accuracy, "sector_weakness": sector_weakness}


if __name__ == "__main__":
    import os
    test_db = str(Path(__file__).parent / "test_chess.db")
    if os.path.exists(test_db):
        os.remove(test_db)
    conn = get_connection(test_db)
    create_tables(conn)
    sid = start_session(conn, "quick_training", "800-1400", 5)
    print("start_session -> session_id:", sid)
    save_result(conn, sid, "p1", "pin", 1000, True, 3200, "center")
    save_result(conn, sid, "p2", "fork", 1100, False, 5000, "kingside")
    save_result(conn, sid, "p3", "pin", 900, False, 2000, None)
    stats = get_session_stats(conn, sid)
    print("get_session_stats:", stats)
    conn.close()
    os.remove(test_db)
    print("Test database OK")
