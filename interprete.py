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

1. "registrar_pago" - cuando alguien pagó o pago (sin tilde también)
   Ejemplos: "jeff pagó", "jeff pago", "pagó lucas", "pago de isabella"
   datos necesarios: nombre_alumno, monto, moneda (Dólar/ARS$/Libra Esterlina), metodo (Wise/PayPal/Transferencia nacional), notas (opcional)
   Para la moneda, convertí siempre al nombre interno:
   - "pesos", "ARS", "pesos argentinos", "$" → "ARS$"
   - "dólares", "dólar", "USD", "usd", "dolares" → "Dólar"
   - "libras", "libra", "GBP", "pounds", "£" → "Libra Esterlina"
   Si no se menciona moneda, dejá el campo vacío (no lo inventes).

2. "registrar_clase" - cuando se dio una clase con UN solo alumno
   datos necesarios: nombre_alumno, fecha (YYYY-MM-DD, si dice "hoy" usá la fecha de hoy), hora (opcional)

3. "registrar_clases_multiple" - cuando se dieron clases con VARIOS alumnos
   datos necesarios: nombres_alumnos (lista), fecha (YYYY-MM-DD), hora (opcional)

4. "cancelar_clase" - cuando el alumno avisa con anticipación que NO va a poder venir
   SOLO usar cuando hay intención de cancelar ANTES de que ocurra la clase.
   datos necesarios: nombre_alumno, fecha (YYYY-MM-DD), cancelada_por (alumno/profesora)
   Ejemplos: "henry canceló el jueves", "fiona no puede el lunes", "cancelo la de jeff del 5"

4b. "marcar_ausente" - cuando un alumno NO asistió a una clase que YA PASÓ (faltó, no vino, no apareció)
    Usar cuando la clase ya ocurrió y el alumno simplemente no se presentó.
    datos necesarios: nombre_alumno, fecha (YYYY-MM-DD, opcional)
    Ejemplos: "henry cutler faltó la clase del 2", "jeff no vino hoy", "fiona faltó",
              "ilay estuvo ausente el lunes", "marco no asistió el 3 de marzo",
              "jeff faltó a la clase de marzo", "fiona no apareció", "henry no vino ayer"

4c. "desmarcar_ausente" - para quitar una ausencia registrada por error (el alumno SÍ vino)
    datos necesarios: nombre_alumno, fecha (YYYY-MM-DD, opcional)
    Ejemplos: "ilay sí vino el 2", "ilay estuvo presente la clase del 2",
              "desmarcar ausente ilay", "quita la ausencia de ilay el 2",
              "ilay no estuvo ausente el 2", "ilay si estuvo la clase del 2",
              "ilay sí asistió", "error, henry sí vino"

4d. "reactivar_clase" - para revertir una cancelación registrada por error (la clase SÍ se va a dar o se dio)
    datos necesarios: nombre_alumno, fecha (YYYY-MM-DD, opcional)
    Ejemplos: "reactivá la clase de jeff del 10 de marzo", "jeff no canceló",
              "quita la cancelación de henry el 5", "la clase de jeff del 10 no estaba cancelada",
              "error, jeff sí tiene clase el 17", "reactivar clase jeff"

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

18. "borrar_pago" - cuando quiere eliminar un pago registrado por error
    datos necesarios: nombre_alumno
    datos opcionales: mes (número 1-12 si menciona un mes), anio (año si lo menciona)
    Ejemplos: "borrá el último pago de Stephen", "eliminar un pago de Grace",
              "me equivoqué con el pago de Lucas", "quiero borrar un pago de Jeff",
              "borrar pagos de jeff de febrero", "eliminar pagos de marzo de Grace"


18. "sincronizar_calendario" - quiere sincronizar las clases con Google Calendar
    datos necesarios: mes (número, opcional), anio (opcional)
    Ejemplos: "sincronizá el calendario", "sincronizar clases", "actualizá las clases desde calendar",
              "sincronizá marzo", "traé las clases de abril"

19. "ignorar_evento" - quiere ignorar un evento del calendario que no es una clase
    datos necesarios: titulo (el título del evento a ignorar, tal como aparece)
    Ejemplos: "ignorar: Andrea y Lucia de Elizalde", "ignorá ese evento", "no es una clase, ignoralo"

20. "no_entiendo" - si el mensaje no corresponde a ninguna acción
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