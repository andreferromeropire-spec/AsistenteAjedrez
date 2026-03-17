"""
Cálculo de estadísticas y formato de resúmenes a partir de sesiones y resultados.
"""

from typing import Optional

import sqlite3


def format_session_summary(stats: dict) -> str:
    """
    Recibe el dict de get_session_stats() y retorna un string formateado para pantalla.
    Ejemplo: Ejercicios: 10 | Correctos: 7 | Precisión: 70%
             Tiempo promedio: 4.2s
             Más errores en: hangingPiece (3), pin (1)
    """
    total = stats.get("total", 0)
    correct = stats.get("correct", 0)
    accuracy = stats.get("accuracy", 0.0)
    avg_ms = stats.get("avg_time_ms", 0.0)
    errors_by_theme = stats.get("errors_by_theme") or {}
    line1 = f"Ejercicios: {total} | Correctos: {correct} | Precisión: {accuracy:.0f}%"
    secs = avg_ms / 1000.0
    line2 = f"Tiempo promedio: {secs:.1f}s"
    if errors_by_theme:
        parts = [f"{theme} ({count})" for theme, count in sorted(errors_by_theme.items(), key=lambda x: -x[1])]
        line3 = "Más errores en: " + ", ".join(parts)
        return f"{line1}\n{line2}\n{line3}"
    return f"{line1}\n{line2}"


# Mantener stubs del esqueleto por si main los usa
def get_total_sessions(conn: sqlite3.Connection) -> int:
    """Número total de sesiones registradas."""
    pass


def get_correct_rate(
    conn: sqlite3.Connection,
    session_id: Optional[int] = None,
    mode: Optional[str] = None,
) -> float:
    """Porcentaje de aciertos (0.0 a 1.0)."""
    pass


def get_average_response_time_ms(
    conn: sqlite3.Connection,
    session_id: Optional[int] = None,
) -> float:
    """Tiempo medio de respuesta en ms."""
    pass


def get_results_by_theme(
    conn: sqlite3.Connection,
    session_id: Optional[int] = None,
    limit: int = 20,
) -> list[tuple[str, int, int]]:
    """Agrupa resultados por tema (theme, correct_count, total_count)."""
    pass


def get_recent_sessions_summary(
    conn: sqlite3.Connection,
    n: int = 10,
) -> list[tuple]:
    """Resumen de las n últimas sesiones."""
    pass


def get_scan_insights(conn: sqlite3.Connection, session_id: int) -> dict:
    """
    Retorna insights accionables de la sesión para mostrar en el resumen.
    {
        "sector_weakness": "flanco de dama" | "centro" | "flanco de rey" | None,
        "avg_scan_time_ms": float,
        "false_positive_rate": float,
        "total": int,
    }
    """
    cur = conn.execute(
        "SELECT sector_missed, scan_time_ms, false_positives FROM results WHERE session_id = ?",
        (session_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return {"sector_weakness": None, "avg_scan_time_ms": 0.0,
                "false_positive_rate": 0.0, "total": 0}

    sector_counts = {}
    scan_times = []
    fp_total = 0

    for sector_missed, scan_time, false_pos in rows:
        if sector_missed:
            sector_counts[sector_missed] = sector_counts.get(sector_missed, 0) + 1
        if scan_time is not None:
            scan_times.append(scan_time)
        if false_pos is not None:
            fp_total += false_pos

    sector_weakness = None
    if sector_counts:
        worst = max(sector_counts, key=lambda s: sector_counts[s])
        sector_labels = {
            "queenside": "flanco de dama",
            "center": "centro",
            "kingside": "flanco de rey"
        }
        sector_weakness = sector_labels.get(worst, worst)

    avg_scan = sum(scan_times) / len(scan_times) if scan_times else 0.0
    fp_rate = fp_total / len(rows) if rows else 0.0

    return {
        "sector_weakness": sector_weakness,
        "avg_scan_time_ms": avg_scan,
        "false_positive_rate": fp_rate,
        "total": len(rows),
    }


if __name__ == "__main__":
    stats = {
        "total": 10,
        "correct": 7,
        "accuracy": 70.0,
        "avg_time_ms": 4200.5,
        "errors_by_theme": {"hangingPiece": 3, "pin": 1},
    }
    print(format_session_summary(stats))
    print("---")
    print(format_session_summary({"total": 5, "correct": 5, "accuracy": 100.0, "avg_time_ms": 2000, "errors_by_theme": {}}))
