"""
Fixtures compartidas. Cada test corre contra una base SQLite temporal
(nunca la real chess_assistant.db) monkeypatcheando database.DB_PATH —
get_connection() lee ese nombre del módulo en cada llamada, así que
alcanza con reemplazarlo antes de crear las tablas.

La app de Flask para los tests registra solo los blueprints necesarios,
no importa bot.py entero (evita levantar el scheduler, Twilio, etc.).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.crear_tablas()
    return database


@pytest.fixture()
def app(db):
    from flask import Flask
    from dashboard_routes import dashboard_bp
    from portal_routes import portal_bp
    from lecciones_routes import lecciones_bp
    from conceptos_routes import conceptos_bp

    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(portal_bp)
    flask_app.register_blueprint(lecciones_bp)
    flask_app.register_blueprint(conceptos_bp)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def as_profesora(client):
    with client.session_transaction() as sess:
        sess["dashboard_logged_in"] = True
    return client


def login_alumno(client, alumno_id):
    with client.session_transaction() as sess:
        sess["portal_alumno_ids"] = [alumno_id]
    return client


@pytest.fixture()
def alumno_id(db):
    conn = db.get_connection()
    cur = conn.execute(
        "INSERT INTO alumnos (nombre, activo) VALUES (?, 1)", ("Alumno de prueba",)
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


@pytest.fixture()
def otro_alumno_id(db):
    conn = db.get_connection()
    cur = conn.execute(
        "INSERT INTO alumnos (nombre, activo) VALUES (?, 1)", ("Otro alumno",)
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


LECCION_EJEMPLO = {
    "tema_principal": "Ataques a la descubierta",
    "resumen_clase": "Se trabajó el patrón de ataque a la descubierta con ejemplos.",
    "nivel_alumno_estimado": "intermedio",
    "conceptos": [
        {"nombre": "ataque_a_la_descubierta", "explicacion_dada": "Mover una pieza libera el ataque de otra.", "confianza": "confirmado"},
    ],
    "partida_analizada": {"identificada": None, "jugadas_confirmadas_por_transcript": [], "posiciones_clave": []},
    "errores_y_correcciones": [
        {"error": "Confundió el patrón con doble jaque.", "correccion": "Se aclaró la diferencia.", "principio_general": "Verificar qué pieza queda libre antes de mover."},
    ],
    "patrones_pensamiento_detectados": [
        {"principio": "Identificar la amenaza del rival antes de mover", "contexto": "Reforzado durante el ejemplo.", "confianza": "confirmado"},
    ],
    "reto_practico": "Antes de mover, revisá si liberás un ataque de otra pieza.",
    "temas_tag": ["ataque_a_la_descubierta", "identificar_amenazas"],
}


def crear_leccion_aprobada(db, leccion_dict=None, estado="aprobada"):
    """Inserta una lección directamente (sin pasar por la IA) usando
    cargar_desde_dict, y la deja en el estado pedido."""
    from cargar_leccion_a_posiciones import cargar_desde_dict

    conn = db.get_connection()
    resultado = cargar_desde_dict(leccion_dict or LECCION_EJEMPLO, conn=conn)
    if estado != "borrador":
        conn.execute("UPDATE lecciones SET estado = ? WHERE id = ?", (estado, resultado["leccion_id"]))
        conn.execute("UPDATE conceptos SET estado = 'aprobado' WHERE id IN (SELECT concepto_id FROM leccion_conceptos WHERE leccion_id = ?)", (resultado["leccion_id"],))
        conn.execute("UPDATE patrones_pensamiento SET estado = 'aprobado' WHERE id IN (SELECT patron_id FROM leccion_patrones WHERE leccion_id = ?)", (resultado["leccion_id"],))
    conn.commit()
    conn.close()
    return resultado["leccion_id"]
