"""
Generación con IA: no pega a la API real de Claude en ningún test (evita
costo, red y no-determinismo) — mockea extraer_leccion.extraer_desde_texto
para los tests de flujo end-to-end, y el cliente Anthropic directamente
para probar el parseo de la respuesta cruda del modelo.
"""
import json
from types import SimpleNamespace

import extraer_leccion
from tests.conftest import LECCION_EJEMPLO


def _fake_respuesta(texto, stop_reason="end_turn"):
    bloque = SimpleNamespace(type="text", text=texto)
    return SimpleNamespace(content=[bloque], stop_reason=stop_reason)


def test_extraer_de_dialogo_parsea_json_con_bloque_de_codigo(monkeypatch):
    """El modelo a veces envuelve el JSON en ```json ... ``` pese a que se
    le pide que no lo haga — extraer_leccion.py ya lo maneja."""
    texto_modelo = "```json\n" + json.dumps(LECCION_EJEMPLO) + "\n```"

    class FakeMessages:
        def create(self, **kwargs):
            return _fake_respuesta(texto_modelo)

    monkeypatch.setattr(extraer_leccion, "cliente", SimpleNamespace(messages=FakeMessages()))

    resultado = extraer_leccion.extraer_desde_texto("un resumen cualquiera", es_resumen=True)
    assert resultado["tema_principal"] == LECCION_EJEMPLO["tema_principal"]


def test_extraer_de_dialogo_json_invalido_levanta_error_legible(monkeypatch, tmp_path):
    class FakeMessages:
        def create(self, **kwargs):
            return _fake_respuesta("esto no es json {")

    monkeypatch.setattr(extraer_leccion, "cliente", SimpleNamespace(messages=FakeMessages()))

    try:
        extraer_leccion.extraer_desde_texto("resumen", es_resumen=True)
        assert False, "debía levantar RuntimeError"
    except RuntimeError as e:
        assert "parsear" in str(e)


def test_generar_endpoint_guarda_borrador_con_ia_mockeada(as_profesora, db, monkeypatch):
    monkeypatch.setattr("extraer_leccion.extraer_desde_texto", lambda texto, es_resumen=False: dict(LECCION_EJEMPLO))

    r = as_profesora.post(
        "/dashboard/api/lecciones/generar",
        json={"texto": "cualquier cosa", "es_resumen": True},
    )
    datos = r.get_json()
    assert r.status_code == 200
    assert datos["ok"] is True
    assert datos["leccion"]["estado"] == "borrador"

    conn = db.get_connection()
    conceptos = conn.execute(
        "SELECT * FROM leccion_conceptos WHERE leccion_id = ?", (datos["leccion"]["id"],)
    ).fetchall()
    conn.close()
    assert len(conceptos) == 1  # vincular_conceptos_y_patrones corrió sin llamar de nuevo a la IA


def test_generar_endpoint_rechaza_respuesta_vacia_de_la_ia(as_profesora, db, monkeypatch):
    monkeypatch.setattr("extraer_leccion.extraer_desde_texto", lambda texto, es_resumen=False: {
        "tema_principal": None, "resumen_clase": None, "conceptos": [],
    })

    r = as_profesora.post(
        "/dashboard/api/lecciones/generar",
        json={"texto": "cualquier cosa", "es_resumen": True},
    )
    assert r.status_code == 502
    assert r.get_json()["ok"] is False

    conn = db.get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM lecciones").fetchone()["n"]
    conn.close()
    assert total == 0  # no se guardó nada


def test_generar_endpoint_maneja_error_de_la_ia(as_profesora, db, monkeypatch):
    def _falla(*a, **kw):
        raise RuntimeError("la API no respondió")

    monkeypatch.setattr("extraer_leccion.extraer_desde_texto", _falla)

    r = as_profesora.post(
        "/dashboard/api/lecciones/generar",
        json={"texto": "cualquier cosa", "es_resumen": True},
    )
    assert r.status_code == 502
    assert "no se pudo generar" in r.get_json()["error"].lower()


def test_generar_endpoint_requiere_texto(as_profesora):
    r = as_profesora.post("/dashboard/api/lecciones/generar", json={"texto": "", "es_resumen": True})
    assert r.status_code == 400
