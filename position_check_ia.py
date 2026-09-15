import os
import json

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

cliente = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Sonnet, no Haiku: esto es razonamiento pedagógico sobre una posición, no
# parseo de intención como en interprete.py — vale la pena el modelo más caro.
MODEL = "claude-sonnet-5"

# Cantidad de mensajes del alumno antes de forzar el cierre. Sube esto con
# cuidado: cada turno extra es una llamada más a la API por intento.
MAX_TURNOS = 3

# Checklist de evaluación posicional: adaptado de los "siete desequilibrios"
# de Jeremy Silman (How to Reassess Your Chess) + seguridad del rey, que
# Silman trata aparte pero que el método Quiet Center pone primero. Esto es
# tanto lo que se le muestra al alumno como el ancla del prompt: la IA no
# debería comentar cosas fuera de estas categorías.
CHECKLIST = [
    {"id": "rey", "nombre": "Seguridad del rey",
     "detalle": "¿Está enrocado o en el centro? ¿Cuántas piezas propias lo defienden? ¿Hay líneas abiertas o amenazas directas?"},
    {"id": "material", "nombre": "Material",
     "detalle": "¿Hay ventaja material neta, o algún desequilibrio (pieza por peones, calidad)?"},
    {"id": "estructura", "nombre": "Estructura de peones",
     "detalle": "Peones débiles, doblados, aislados, pasados. Islas de peones."},
    {"id": "pieza_superior", "nombre": "Pieza superior",
     "detalle": "Alfil bueno vs. malo, alfil vs. caballo: ¿qué pieza menor es mejor acá y por qué?"},
    {"id": "espacio", "nombre": "Espacio",
     "detalle": "¿Quién controla más territorio? ¿El espacio extra permite maniobrar o asfixia al rival?"},
    {"id": "columna_diagonal", "nombre": "Control de columna o diagonal clave",
     "detalle": "¿Hay una columna abierta/semiabierta o una diagonal larga, y quién la controla?"},
    {"id": "desarrollo", "nombre": "Desarrollo e iniciativa",
     "detalle": "¿Quién tiene más piezas activas? ¿Quién obliga al otro a responder?"},
]


def _construir_sistema(fen, turno):
    es_ultimo_turno = turno >= MAX_TURNOS
    if es_ultimo_turno:
        instruccion_turno = (
            "Este es el ÚLTIMO turno permitido. No hagas más preguntas: cerrá "
            "con una síntesis del proceso de pensamiento del alumno (qué "
            "identificó bien, qué se le sigue escapando). Podés ahora sí orientar "
            "hacia el plan o la jugada correcta, pero priorizando el PROCESO por "
            "sobre la respuesta puntual. El campo \"cierre\" tiene que ser CORTO: "
            "4 líneas como máximo, sin repetir lo que ya está en \"reconocido\" y "
            "\"omitido\" — esos dos campos ya cubren el detalle, \"cierre\" es "
            "solo el remate. Si el trabajo fue sólido de principio a fin, decilo "
            "con honestidad — no inventes una crítica floja solo para parecer "
            "exhaustivo. Dejá \"pregunta_seguimiento\" en null."
        )
    else:
        instruccion_turno = (
            f"Este es el turno {turno} de {MAX_TURNOS}. Terminá con UNA sola "
            "pregunta concreta que lo lleve a notar algo que todavía no vio. "
            "Completá \"pregunta_seguimiento\" y dejá \"cierre\" en null."
        )

    checklist_lineas = [f"{i + 1}. {c['nombre']}: {c['detalle']}" for i, c in enumerate(CHECKLIST)]
    checklist_texto = "\n".join(checklist_lineas)

    return f"""Sos un entrenador de ajedrez que sigue el método Quiet Center: no le das la
respuesta al alumno, lo ayudás a entender cómo está pensando.

El alumno está analizando esta posición (FEN): {fen}

Tu evaluación tiene que anclarse SIEMPRE a este checklist (adaptado de los
"desequilibrios" de Jeremy Silman, How to Reassess Your Chess) — es el mismo
que el alumno tiene visible en pantalla:
{checklist_texto}

No abras líneas de análisis que no correspondan a ninguna de estas categorías
(por ejemplo, no te metas a calcular variantes tácticas profundas salvo que
haga falta para explicar "control de columna/diagonal" o "desarrollo e
iniciativa"). Si una categoría ya quedó bien cubierta por el alumno, no
insistas ahí — señalá otra categoría del checklist que todavía falte, o
dejala afuera si ya están todas cubiertas razonablemente. Cuando menciones
algo reconocido u omitido, dejá claro a qué categoría del checklist
corresponde (por ejemplo: "Estructura de peones: ...").

Reglas estrictas:
- NUNCA reveles la mejor jugada ni una evaluación numérica, salvo en el turno
  final (ver más abajo), y aun ahí con brevedad y enfocado en el razonamiento.
- Si el alumno pide directamente "decime la jugada" o algo equivalente,
  respondé con una pregunta que lo guíe a pensarlo él mismo, nunca con la
  respuesta.
- Reconocé primero, con honestidad, qué observó bien en su análisis (material,
  seguridad del rey, centro, actividad de piezas, estructura de peones,
  amenazas del rival, planes, jugadas candidatas).
- Sé HONESTO antes que exhaustivo: si el análisis de este turno fue realmente
  completo, "omitido" puede quedar vacío ([]) — no inventes una omisión menor
  solo para tener algo que señalar. Cuando sí hay algo genuinamente relevante
  sin considerar, señalá como máximo uno o dos factores, sin resolvérselos
  directamente.
- Sé breve: 3 a 5 líneas como máximo por intervención.

{instruccion_turno}

Tu respuesta COMPLETA tiene que ser el objeto JSON de abajo y nada más: sin
ningún párrafo antes ni después, sin bloques de código, sin repetir el cierre
como texto libre. El primer carácter de tu respuesta tiene que ser "{{".
{{
  "reconocido": ["...", "..."],
  "omitido": ["...", "..."],
  "pregunta_seguimiento": "..." o null,
  "cierre": "..." o null
}}"""


def generar_feedback(fen, historial, turno):
    """
    historial: lista de dicts [{"rol": "alumno"|"ia", "texto": str}, ...] en
    orden cronológico. Para turnos "ia", texto es el JSON crudo que devolvió
    el modelo la vez anterior (se reutiliza tal cual como turno "assistant").
    turno: número de turno del alumno que se está respondiendo ahora (1-indexado).

    Devuelve (datos, texto_crudo): datos es el dict ya parseado, texto_crudo
    es el string que hay que guardar para alimentar el próximo turno.
    """
    sistema = _construir_sistema(fen, turno)
    mensajes = [
        {"role": "user" if t["rol"] == "alumno" else "assistant", "content": t["texto"]}
        for t in historial
    ]

    respuesta = cliente.messages.create(
        model=MODEL,
        max_tokens=900,
        system=sistema,
        messages=mensajes,
        # Sin esto, el modelo piensa por defecto y ese razonamiento consume
        # max_tokens antes de llegar al JSON (visto en pruebas: stop_reason
        # "max_tokens" con la respuesta cortada a mitad de string). No
        # necesitamos la cadena de pensamiento expuesta para esta tarea.
        thinking={"type": "disabled"},
    )

    # No asumir que el bloque de texto está en la posición 0: con este modelo
    # puede venir precedido de un ThinkingBlock.
    bloque_texto = next((b for b in respuesta.content if b.type == "text"), None)
    if bloque_texto is None:
        datos = {
            "reconocido": [],
            "omitido": [],
            "pregunta_seguimiento": None,
            "cierre": "Hubo un problema generando el feedback. Probá enviar tu respuesta de nuevo.",
        }
        return datos, json.dumps(datos)

    texto = bloque_texto.text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    datos = None
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        # A veces el modelo antepone una frase en prosa antes del JSON pese a
        # la instrucción de devolver solo JSON (visto en pruebas: un párrafo
        # de cierre seguido recién del bloque {...}). Buscamos el objeto JSON
        # dentro del texto en vez de descartar toda la respuesta.
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin > inicio:
            try:
                datos = json.loads(texto[inicio:fin + 1])
            except json.JSONDecodeError:
                datos = None

    if datos is None:
        datos = {
            "reconocido": [],
            "omitido": [],
            "pregunta_seguimiento": None,
            "cierre": "Hubo un problema generando el feedback. Probá enviar tu respuesta de nuevo.",
        }
        texto = json.dumps(datos)

    return datos, texto
