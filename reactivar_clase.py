#!/usr/bin/env python3
"""
Reactiva una clase que fue cancelada en la DB.
Uso: python reactivar_clase.py "Ximena"
     python reactivar_clase.py "Ximena" 2026-03-03
"""
import sys
from database import get_connection
from clases import reactivar_clase

def main():
    if len(sys.argv) < 2:
        print("Uso: python reactivar_clase.py \"Nombre alumno\" [fecha YYYY-MM-DD]")
        sys.exit(1)
    nombre = sys.argv[1].strip()
    fecha = sys.argv[2].strip() if len(sys.argv) > 2 else None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.fecha, c.hora, c.estado, a.nombre
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE a.nombre LIKE ? AND c.estado LIKE 'cancelada%'
        ORDER BY c.fecha DESC
    """, (f"%{nombre}%",))
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        print(f"No hay clases canceladas de alguien que coincida con '{nombre}'.")
        sys.exit(1)
    if fecha:
        filas = [r for r in filas if r["fecha"] == fecha]
        if not filas:
            print(f"Ninguna clase cancelada de {nombre} en {fecha}.")
            sys.exit(1)
    clase = filas[0]
    reactivar_clase(clase["id"])
    print(f"Listo: clase de {clase['nombre']} del {clase['fecha']} reactivada (estado = agendada).")

if __name__ == "__main__":
    main()
