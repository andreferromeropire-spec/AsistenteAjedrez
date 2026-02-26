from alumnos import buscar_alumno_por_nombre
from clases import agendar_clase
from datetime import date, timedelta

def fechas_del_mes(anio, mes, dia_semana):
    fechas = []
    d = date(anio, mes, 1)
    while d.month == mes:
        if d.weekday() == dia_semana:
            fechas.append(d.isoformat())
        d += timedelta(days=1)
    return fechas

def cargar_clases_mes(anio, mes):
    clases = [
        # LUNES (0)
        ("Ilay", 0, "17:00"),
        ("Henry (Girl)", 0, "21:00"),
        # MARTES (1)
        ("Nouham", 1, "11:30"),
        ("Michael", 1, "16:30"),
        ("Ximena", 1, "19:00"),
        ("Giuliana", 1, "20:30"),
        ("Jeff", 1, "21:30"),
        # MIÉRCOLES (2)
        ("Ruby", 2, "12:30"),
        ("Kerem", 2, "14:00"),
        ("Lucas", 2, "15:00"),
        ("David y George", 2, "17:30"),
        # JUEVES (3)
        ("Isabella", 3, "15:00"),
        ("Grace", 3, "17:30"),
        ("Fiona", 3, "18:30"),
        ("Rafa", 3, "20:30"),
        # VIERNES (4)
        ("Henry", 4, "17:15"),
        ("Leila", 4, "18:15"),
        # SÁBADO (5)
        ("John", 5, "15:00"),
    ]

    for nombre, dia_semana, hora in clases:
        alumnos = buscar_alumno_por_nombre(nombre)
        if not alumnos:
            print(f"❌ No encontré: {nombre}")
            continue
        alumno = alumnos[0]
        fechas = fechas_del_mes(anio, mes, dia_semana)
        for fecha in fechas:
            agendar_clase(
                alumno_id=alumno['id'],
                fecha=fecha,
                hora=hora,
                origen="recurrente"
            )
        print(f"✅ {alumno['nombre']}: {len(fechas)} clases en {mes}/{anio}")

if __name__ == "__main__":
    cargar_clases_mes(2026, 3)  # Marzo 2026
    print("\nClases de marzo cargadas.")