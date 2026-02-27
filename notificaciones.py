import os
from twilio.rest import Client
from dotenv import load_dotenv
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

# Inicializa el cliente de Twilio con tus credenciales
cliente_twilio = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

NUMERO_TWILIO = "whatsapp:+14155238886"  # Número del sandbox de Twilio
MI_NUMERO = os.getenv("MI_NUMERO")

# ENVIAR_MENSAJE: Función base que manda cualquier mensaje a tu WhatsApp
def enviar_mensaje(texto):
    cliente_twilio.messages.create(
        from_=NUMERO_TWILIO,
        to=MI_NUMERO,
        body=texto
    )

# RESUMEN_DIARIO: Te manda las clases que tenés agendadas para hoy
def resumen_diario():
    from database import get_connection
    hoy = date.today().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, a.nombre 
        FROM clases c
        JOIN alumnos a ON c.alumno_id = a.id
        WHERE c.fecha = ? AND c.estado = 'agendada'
        ORDER BY c.hora ASC
    """, (hoy,))
    clases = cursor.fetchall()
    conn.close()

    if not clases:
        enviar_mensaje(f"📅 Buenos días! No tenés clases agendadas para hoy ({hoy}).")
        return

    texto = f"📅 Buenos días! Tus clases de hoy ({hoy}):\n"
    for clase in clases:
        hora = f"a las {clase['hora']}" if clase['hora'] else "sin hora especificada"
        texto += f"• {clase['nombre']} {hora}\n"
    enviar_mensaje(texto)

# RECORDATORIO_PAGOS: Te avisa quién no pagó este mes
def recordatorio_pagos_mensuales():
    from pagos import quien_debe_este_mes
    deudores = quien_debe_este_mes()
    if not deudores:
        enviar_mensaje("✅ Todos los alumnos mensuales pagaron este mes.")
        return
    lista = "\n".join([f"• {a['nombre']}" for a in deudores])
    enviar_mensaje(f"💸 Recordatorio de pagos pendientes:\n{lista}")

# ALERTA_PAQUETES: Te avisa cuando un alumno tiene 2 o menos clases en su paquete
def alerta_paquetes():
    from clases import alumnos_por_renovar_paquete
    por_renovar = alumnos_por_renovar_paquete()
    if not por_renovar:
        return
    for alumno in por_renovar:
        enviar_mensaje(
            f"⚠️ {alumno['alumno']} tiene {alumno['clases_restantes']} "
            f"clases restantes en su paquete. ¡Hora de renovar!"
        )


# CONFIGURAR_SCHEDULER: Define cuándo se ejecuta cada función automáticamente
def configurar_scheduler():
    scheduler = BackgroundScheduler()
    
    # Resumen diario a las 8am
    scheduler.add_job(resumen_diario, 'cron', hour=8, minute=0)
    
    # Recordatorio de pagos el día 1 de cada mes a las 9am
    scheduler.add_job(recordatorio_pagos_mensuales, 'cron', day=1, hour=9, minute=0)
    
    # Revisión de paquetes todos los lunes a las 9am
    scheduler.add_job(alerta_paquetes, 'cron', day_of_week='mon', hour=9, minute=0)
    
    # Sincronización con Calendar dos veces por día
    from sincronizacion import sincronizacion_diaria
    scheduler.add_job(sincronizacion_diaria, 'cron', hour=8, minute=30)
    scheduler.add_job(sincronizacion_diaria, 'cron', hour=20, minute=0)

    scheduler.start()
    return scheduler