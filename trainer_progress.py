from database import get_connection


def guardar_progreso_entrenamiento(alumno_id, tipo_patrones, dificultad, resultado, tiempo_segundos, rating_cambio=0.0):
    """
    Guarda un registro de progreso de entrenamiento en la tabla global progreso_entrenamiento.
    """
    if not alumno_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO progreso_entrenamiento
        (alumno_id, tipo_patrones, dificultad, resultado, tiempo_segundos, rating_cambio)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (alumno_id, tipo_patrones, dificultad, resultado, tiempo_segundos, rating_cambio),
    )
    conn.commit()
    conn.close()

