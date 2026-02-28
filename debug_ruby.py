from calendar_google import buscar_alumno_en_evento

alumno = buscar_alumno_en_evento("Chess Lesson - Ruby Morrow y Andrea Romero")
if alumno:
    print(f"Alumno encontrado: {alumno['nombre']}")
else:
    print("No encontró ningún alumno")