# debug_henry_cutler.py
from calendar_google import buscar_alumno_en_evento

titulos = [
    "Chess Henry Cutler",
    "Chess Henry Chen",
]

for titulo in titulos:
    alumno = buscar_alumno_en_evento(titulo)
    if alumno:
        print(f"'{titulo}' → {alumno['nombre']} (id {alumno['id']})")
    else:
        print(f"'{titulo}' → No encontrado")