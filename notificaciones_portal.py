import os
from datetime import datetime, timedelta

import resend

from database import get_connection


def _enviar_mail(destino, asunto, cuerpo):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("notificaciones_portal: RESEND_API_KEY no configurada, no se envían mails.")
        return False
    try:
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": os.environ.get("RESEND_FROM", "notificaciones@tudominio.com"),
                "to": [destino],
                "subject": asunto,
                "text": cuerpo,
            }
        )
        return True
    except Exception as e:
        print("notificaciones_portal: error enviando mail con Resend:", repr(e))
        return False


def enviar_recordatorios_pendientes():
    try:
        conn = get_connection()
        ahora = datetime.utcnow()
        ventana_inicio = ahora - timedelta(minutes=15)

        # 1) Clases agendadas en próximas 24h
        clases = conn.execute("""
            SELECT c.id, c.fecha, c.hora, c.alumno_id, a.nombre, a.idioma
            FROM clases c
            JOIN alumnos a ON a.id = c.alumno_id
            WHERE c.estado = 'agendada'
              AND datetime(c.fecha || ' ' || c.hora) > datetime('now')
              AND datetime(c.fecha || ' ' || c.hora) <= datetime('now', '+24 hours')
        """).fetchall()

        for c in clases:
            clase_id = c["id"]
            alumno_id = c["alumno_id"]
            fecha_clase = c["fecha"]
            hora_clase = c["hora"] or "00:00"
            try:
                dt_clase = datetime.fromisoformat(fecha_clase + " " + hora_clase)
            except Exception:
                # Si falla el parseo, intentar sin hora
                try:
                    dt_clase = datetime.fromisoformat(fecha_clase + " 00:00")
                except Exception:
                    continue

            # 3) Recordatorios activos de mail
            recs = conn.execute("""
                SELECT * FROM recordatorios
                WHERE alumno_id = ?
                  AND activo = 1
                  AND canal = 'mail'
                  AND (alcance = 'todas' OR (alcance = 'proxima' AND clase_id = ?))
            """, (alumno_id, clase_id)).fetchall()

            for r in recs:
                minutos_antes = r["minutos_antes"]
                try:
                    delta = timedelta(minutes=int(minutos_antes))
                except Exception:
                    continue
                momento_envio = dt_clase - delta
                if not (ventana_inicio <= momento_envio <= ahora):
                    continue

                # 5) Evitar duplicados
                ya = conn.execute("""
                    SELECT 1 FROM recordatorios_enviados
                    WHERE recordatorio_id = ? AND clase_id = ?
                """, (r["id"], clase_id)).fetchone()
                if ya:
                    continue

                mail_destino = r["mail_destino"] or ""
                if not mail_destino:
                    continue

                # 6) Armar mail
                idioma = (c["idioma"] or "").lower()
                minutos = int(minutos_antes)
                if minutos < 60:
                    unidades_es = "minutos"
                    unidades_en = "minutes"
                    valor = minutos
                else:
                    horas = minutos // 60
                    unidades_es = "horas"
                    unidades_en = "hours"
                    valor = horas

                if idioma.startswith("es"):
                    asunto = "Recordatorio: clase de ajedrez en %d %s" % (valor, unidades_es)
                    cuerpo = "Hola %s, te recordamos que tenés clase de ajedrez el %s a las %s." % (
                        c["nombre"], fecha_clase, hora_clase
                    )
                else:
                    asunto = "Reminder: chess class in %d %s" % (valor, unidades_en)
                    cuerpo = "Hi %s, reminder that you have a chess class on %s at %s." % (
                        c["nombre"], fecha_clase, hora_clase
                    )

                ok = _enviar_mail(mail_destino, asunto, cuerpo)
                if ok:
                    conn.execute(
                        "INSERT OR IGNORE INTO recordatorios_enviados (recordatorio_id, clase_id, enviado_en) VALUES (?,?,datetime('now'))",
                        (r["id"], clase_id),
                    )
                    conn.commit()

        conn.close()
    except Exception as e:
        print("notificaciones_portal: error general en enviar_recordatorios_pendientes:", repr(e))

