"""
Extrae una lección estructurada (conceptos, posiciones clave, preguntas
socráticas, errores corregidos) a partir de un transcript de closed captions
de Zoom de una clase de ajedrez.

Uso:
    python extraer_leccion.py "/ruta/al/meeting_saved_closed_caption.txt"

No corre en producción — es una herramienta de una sola vez para prototipar
qué se puede extraer de las clases reales de Andrea, antes de decidir si esto
se integra a los endpoints web. Guarda el resultado como JSON al lado del
transcript original.
"""

import os
import re
import sys
import json

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

cliente = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-5"

# El transcript de Zoom viene como bloques "[Hablante] HH:MM:SS\ntexto\n\n".
# Lo colapsamos a un diálogo simple (Hablante: texto por línea) porque los
# timestamps por segundo no aportan nada a la extracción y consumen tokens.
PATRON_BLOQUE = re.compile(r"^\[(?P<hablante>[^\]]+)\]\s+\d{1,2}:\d{2}:\d{2}$")


def cargar_transcript(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        lineas = [l.rstrip("\n") for l in f]

    turnos = []
    hablante_actual = None
    texto_actual = []

    def cerrar_turno():
        if hablante_actual is not None and texto_actual:
            texto = " ".join(t.strip() for t in texto_actual if t.strip())
            if texto:
                turnos.append((hablante_actual, texto))

    for linea in lineas:
        m = PATRON_BLOQUE.match(linea.strip())
        if m:
            cerrar_turno()
            hablante_actual = m.group("hablante")
            texto_actual = []
        elif linea.strip():
            texto_actual.append(linea)
    cerrar_turno()

    # Colapsar turnos consecutivos del mismo hablante (Zoom corta cada
    # oración en un bloque nuevo con su propio timestamp).
    colapsado = []
    for hablante, texto in turnos:
        if colapsado and colapsado[-1][0] == hablante:
            colapsado[-1] = (hablante, colapsado[-1][1] + " " + texto)
        else:
            colapsado.append([hablante, texto])
    return colapsado


def formatear_dialogo(turnos, nombre_profesora="Andrea Romero"):
    lineas = []
    for hablante, texto in turnos:
        rol = "PROFESORA" if hablante == nombre_profesora else "ALUMNO/A"
        lineas.append(f"{rol}: {texto}")
    return "\n".join(lineas)


SISTEMA = """Sos un asistente que convierte transcripts crudos (closed captions
automáticos de Zoom, con errores de transcripción, oraciones cortadas y
palabras mal reconocidas) de clases particulares de ajedrez en una lección
estructurada y reutilizable.

El transcript es un diálogo entre PROFESORA (Andrea, dueña de una escuela de
ajedrez online llamada Quiet Center) y ALUMNO/A. Los captions tienen errores
típicos de reconocimiento de voz (ej: "assures" en vez de "skewers", "pent" en
vez de "pin", "Duke" mal transcripto, nombres propios deformados). Tu trabajo
es leer a través de esos errores y reconstruir la intención real usando
contexto ajedrecístico — nunca inventes contenido que no esté implícito en el
diálogo.

Reglas:
- Los conceptos y explicaciones tienen que venir DE LO QUE DICE LA PROFESORA
  en el transcript, no de tu conocimiento general de ajedrez agregado después.
- Si la clase analiza una partida específica (propia, de un alumno, o una
  partida histórica famosa), reconstruí la secuencia de jugadas que se
  mencionan explícitamente, en notación algebraica estándar, en el orden en
  que se juegan. Si identificás que es una partida histórica conocida,
  decilo (nombre, jugadores, año) — pero marcá bien qué jugadas están
  confirmadas por el transcript y cuáles inferiste solo por reconocer la
  partida.
- Un "momento socrático" es cuando la profesora hace una pregunta ANTES de
  revelar la respuesta, buscando que el alumno razone. Capturá esos momentos
  tal cual ocurrieron: la pregunta, lo que respondió el alumno, y cómo
  confirmó/corrigió la profesora.
- Un "error corregido" es un momento donde el alumno se equivocó (en una
  jugada, en una idea, en un cálculo) y la profesora lo corrigió explicando
  el porqué. Nos interesa el principio general detrás de la corrección, no
  solo el hecho puntual.
- "temas_tag" tiene que ser una lista corta de etiquetas normalizadas en
  minúscula y sin espacios (usá guion_bajo), pensadas para ser reutilizadas
  como filtro de contenido (ej: "desarrollo_de_piezas", "seguridad_del_rey",
  "pin", "conversion_de_ventaja", "calculo_de_capturas", "fianchetto").
  Preferí etiquetas que ya uses en otra lección si el concepto es el mismo
  (pensá en una taxonomía chica y reusable, no en tags únicos por clase).
- Si algo no está claro en el transcript, usá null en vez de inventar.
- Para cada posición clave, además del texto libre en "momento", indicá
  "jugada_hasta_indice": la cantidad de jugadas (medias-jugadas, no de
  movimientos completos) de "jugadas_confirmadas_por_transcript" que hay que
  reproducir desde el inicio para llegar a esa posición exacta (1 = después
  de la primera jugada de la lista, 2 = después de la segunda, etc.). Esto
  tiene que ser exacto porque se usa para reconstruir el FEN de forma
  automática con un motor de ajedrez — no lo dejes en null salvo que
  jugadas_confirmadas_por_transcript esté vacío o la posición no corresponda
  a ningún punto de esa lista.

Devolvé ÚNICAMENTE un objeto JSON con esta forma exacta, sin texto antes ni
después, sin bloques de código:
{
  "tema_principal": "string corto",
  "resumen_clase": "2-3 líneas en español, qué se trabajó y por qué",
  "nivel_alumno_estimado": "principiante" | "intermedio" | "avanzado" | null,
  "conceptos": [
    {"nombre": "...", "explicacion_dada": "cómo lo explicó la profesora, en sus palabras"}
  ],
  "partida_analizada": {
    "identificada": "nombre/jugadores/año si se reconoce, o null",
    "jugadas_confirmadas_por_transcript": ["e4", "a5", "Nf3", "..."],
    "posiciones_clave": [
      {
        "momento": "después de qué jugada, en texto",
        "jugada_hasta_indice": 6,
        "concepto_asociado": "tag de temas_tag que mejor aplica",
        "pregunta_socratica": "la pregunta real que hizo la profesora, o null",
        "respuesta_alumno": "qué respondió, o null",
        "correccion_o_confirmacion": "qué dijo la profesora después"
      }
    ]
  },
  "errores_y_correcciones": [
    {"error": "...", "correccion": "...", "principio_general": "..."}
  ],
  "temas_tag": ["...", "..."]
}"""


def extraer(ruta_transcript):
    turnos = cargar_transcript(ruta_transcript)
    dialogo = formatear_dialogo(turnos)

    respuesta = cliente.messages.create(
        model=MODEL,
        max_tokens=12000,
        system=SISTEMA,
        messages=[{"role": "user", "content": dialogo}],
        thinking={"type": "disabled"},
    )

    bloque_texto = next((b for b in respuesta.content if b.type == "text"), None)
    if bloque_texto is None:
        raise RuntimeError("El modelo no devolvió texto.")

    texto = bloque_texto.text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    if respuesta.stop_reason == "max_tokens":
        print(
            "ADVERTENCIA: la respuesta se cortó por max_tokens — el JSON puede "
            "venir incompleto. Subí max_tokens si esto pasa seguido.",
            file=sys.stderr,
        )

    inicio = texto.find("{")
    fin = texto.rfind("}")
    try:
        return json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError as e:
        ruta_cruda = "/tmp/extraer_leccion_respuesta_cruda.txt"
        with open(ruta_cruda, "w", encoding="utf-8") as f:
            f.write(texto)
        raise RuntimeError(
            f"No se pudo parsear el JSON ({e}). Respuesta cruda guardada en {ruta_cruda}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python extraer_leccion.py <ruta_al_transcript.txt>")
        sys.exit(1)

    ruta = sys.argv[1]
    datos = extraer(ruta)

    ruta_salida = os.path.splitext(ruta)[0] + "_leccion.json"
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(json.dumps(datos, ensure_ascii=False, indent=2))
    print(f"\nGuardado en: {ruta_salida}")
