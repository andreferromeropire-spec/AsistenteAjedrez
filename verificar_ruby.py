# verificar_ruby.py
from alumnos import buscar_alumno_por_nombre
resultado = buscar_alumno_por_nombre("Ruby")
for a in resultado:
    print(dict(a))