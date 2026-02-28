# debug_michael.py
from calendar_google import buscar_alumno_en_evento

titulos = [
    "Chess Lesson - Noam y Andrea Romero",
    "Chess Lesson - Jeff and Andrea Romero",
    "Chess Lesson - John Hammers y Andrea Romero",
    "Chess - Leila",
]

for titulo in titulos:
    alumno = buscar_alumno_en_evento(titulo)
    if alumno:
        print(f"'{titulo}' → {alumno['nombre']} (id {alumno['id']})")
    else:
        print(f"'{titulo}' → No encontrado")