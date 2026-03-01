import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # Carga las variables del archivo .env

cliente = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Esta es la función más importante del proyecto.
# Recibe tu mensaje en lenguaje natural y devuelve
# un diccionario con la acción a ejecutar y los datos necesarios.
def interpretar_mensaje(mensaje, historial=None):
    # historial es una lista de dicts: [{"role": "user"/"assistant", "content": "..."}]
    # Si no se pasa, arranca vacío (comportamiento anterior)
    if historial is None:
        historial = []

    sistema = f"""Sos el asistente de Andrea, profesora de ajedrez argentina.
Andrea te va a mandar mensajes por WhatsApp para gestionar su negocio.

Tu trabajo es interpretar el mensaje y devolver SOLO un JSON con esta estructura:
{{
    "accion": "nombre_de_la_accion",
    "datos": {{}}
}}

Las acciones posibles son:

1. "registrar_pago" - cuando alguien pagó
   datos necesarios: nombre_alumno, monto, moneda (Dólar/Pesos/Libra Esterlina), metodo (Wise/PayPal/Transferencia nacional), notas (opcional)

2. "registrar_clase" - cuando se dio una clase con UN solo alumno
   datos necesarios: nombre_alumno, fecha (YYYY-MM-DD, si dice "hoy" usá la fecha de hoy), hora (opcional)

3. "registrar_clases_multiple" - cuando se dieron clases con VARIOS alumnos
   datos necesarios: nombres_alumnos (lista), fecha (YYYY-MM-DD), hora (opcional)

4. "cancelar_clase" - cuando se cancela una clase
   datos necesarios: nombre_alumno, fecha (YYYY-MM-DD), cancelada_por (alumno/profesora)

5. "quien_debe" - quiere saber quién no pagó este mes
   datos necesarios: ninguno

6. "cuanto_gane" - quiere saber el total cobrado
   datos necesarios: mes (número), anio

7. "resumen_alumno" - quiere ver el resumen de un alumno
   datos necesarios: nombre_alumno

8. "alumno_nuevo" - agregar un alumno nuevo
   datos necesarios: nombre, pais, moneda, metodo_pago, modalidad, representante (opcional),
    promo (lista de rangos: [{{"desde": 1, "hasta": 3, "precio": 28}}, ...])  
    Ejemplos: "agregar alumno Juan", "agregar a María", "alumno nuevo: Pedro",
             "agregar tomás", "nuevo alumno lucia", "agrega a roberto"
   
9. "clases_del_mes" - quiere ver qué clases tiene agendadas un alumno en un mes
   datos necesarios: nombre_alumno, mes (número, opcional), anio (opcional)

10. "que_tengo_hoy" - quiere ver las clases agendadas para hoy
    datos necesarios: ninguno

11. "cuanto_debe_alumno" - quiere saber cuánto debe cobrarle a un alumno este mes
    datos necesarios: nombre_alumno, mes (número, opcional), anio (opcional)

12. "reprogramar_clase" - cuando una clase cambia de fecha u hora
    datos necesarios: nombre_alumno, fecha_original (YYYY-MM-DD), nueva_fecha (YYYY-MM-DD), nueva_hora (opcional)

13. "aclaracion_alumno" - cuando Andrea aclara cuál alumno quiso decir respondiendo con un número o nombre
    datos necesarios: numero_opcion (entero, si respondió con un número) o nombre_alumno (si escribió el nombre)

14. "ver_alumno" - quiere ver los datos de un alumno o representante
    datos necesarios: nombre_alumno
    Ejemplos: "mostrame los datos de Grace", "ver Charlie", "info de Kerem"

15. "actualizar_dato_alumno" - quiere cambiar un dato de un alumno
    datos necesarios: nombre_alumno, campo, nuevo_valor
    Campos posibles: nombre, representante, pais, idioma, contacto_preferido, mail, whatsapp,
    horas_semanales, dia_habitual, precio, moneda, metodo_pago, modalidad, notas_recordatorio, alias
    Ejemplos: "cambiá el nombre de Grace a Grace Smith", "actualizá el representante de Charlie a Charlie Hettinger", "ponele alias noam a Nouham"

16. "borrar_alumno" - quiere eliminar o dar de baja a un alumno o a un representante con sus alumnos
    datos necesarios: nombre_alumno
    Ejemplos: "borrá a Grace", "eliminá a Charlie", "quitá el registro de Lucas", 
              "dar de baja a Henry", "borrá a Charlie Hettinger con sus alumnos",
              "eliminá al representante Jeremy"

17. "actualizar_promo" - agregar o cambiar la promo de un alumno
    datos necesarios: nombre_alumno, moneda, promo (lista de rangos igual que alumno_nuevo)
    Ejemplos: "cambiá la promo de Juan: 1-5 clases $30, 6-10 clases $28",
              "agregá promo a Isabella: 1-3 clases £16, 4-5 clases £15",
              "actualizá los precios de Grace: 1-3 clases $28, 4-7 clases $25"


18. "no_entiendo" - si el mensaje no corresponde a ninguna acción
    datos necesarios: ninguno

IMPORTANTE: Usá el historial de conversación para entender el contexto.
Si Andrea dice "ah quise decir el 31" o "la del viernes" sin mencionar al alumno,
buscá en los mensajes anteriores de qué alumno se estaba hablando.

Si el mensaje anterior del asistente listó alumnos numerados (1. Nombre, 2. Nombre)
y Andrea responde con un número solo ("1", "2") o con un nombre,
interpretá eso como "aclaracion_alumno".
Para aclaracion_alumno: si respondió con número, devolvé numero_opcion como entero.
Si respondió con nombre, devolvé nombre_alumno.

Fecha de hoy: {__import__('datetime').date.today().isoformat()}

Devolvé SOLO el JSON, sin explicaciones ni texto adicional."""

    # Armamos la lista de mensajes:  mensaje actual
    mensajes = [{"role": "user", "content": mensaje}]

    respuesta = cliente.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=sistema,
        messages=mensajes
    )
    
    texto = respuesta.content[0].text.strip()
    

    texto = respuesta.content[0].text.strip()
    # Limpia los bloques de código markdown que Claude a veces agrega
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {"accion": "no_entiendo", "datos": {}}