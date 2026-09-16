"""Creación de lecciones, idempotencia, y gating de estado al asignar."""
import json

from cargar_leccion_a_posiciones import cargar_desde_dict
from tests.conftest import LECCION_EJEMPLO, crear_leccion_aprobada, login_alumno


def test_cargar_desde_dict_crea_en_borrador_por_default(db):
    resultado = cargar_desde_dict(LECCION_EJEMPLO)
    conn = db.get_connection()
    fila = conn.execute("SELECT estado, reto_practico FROM lecciones WHERE id = ?", (resultado["leccion_id"],)).fetchone()
    conn.close()
    assert fila["estado"] == "borrador"
    assert fila["reto_practico"] == LECCION_EJEMPLO["reto_practico"]


def test_cargar_desde_dict_es_idempotente(db):
    r1 = cargar_desde_dict(LECCION_EJEMPLO)
    r2 = cargar_desde_dict(LECCION_EJEMPLO)
    assert r1["leccion_id"] == r2["leccion_id"]
    conn = db.get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM lecciones").fetchone()["n"]
    conn.close()
    assert total == 1


def test_no_se_puede_asignar_leccion_en_borrador(as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="borrador")
    r = as_profesora.post(
        "/dashboard/api/alumno_lecciones",
        json={"alumno_id": alumno_id, "leccion_id": leccion_id, "motivo": "test"},
    )
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_asignar_leccion_aprobada_actualiza_progreso(as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    r = as_profesora.post(
        "/dashboard/api/alumno_lecciones",
        json={"alumno_id": alumno_id, "leccion_id": leccion_id, "motivo": "vista hoy"},
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    conn = db.get_connection()
    concepto = conn.execute("SELECT * FROM alumno_conceptos WHERE alumno_id = ?", (alumno_id,)).fetchone()
    conn.close()
    assert concepto is not None
    assert concepto["veces_trabajado"] == 1


def test_no_se_puede_asignar_dos_veces_sin_revisar(as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    as_profesora.post("/dashboard/api/alumno_lecciones", json={"alumno_id": alumno_id, "leccion_id": leccion_id})
    r2 = as_profesora.post("/dashboard/api/alumno_lecciones", json={"alumno_id": alumno_id, "leccion_id": leccion_id})
    assert r2.status_code == 400


def test_historial_pedagogico_incluye_lecciones_conceptos_y_patrones(as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    as_profesora.post("/dashboard/api/alumno_lecciones", json={"alumno_id": alumno_id, "leccion_id": leccion_id})

    r = as_profesora.get(f"/dashboard/api/alumnos/{alumno_id}/historial_pedagogico")
    datos = r.get_json()
    assert r.status_code == 200
    assert len(datos["lecciones"]) == 1
    assert len(datos["conceptos"]) == 1
    assert len(datos["patrones"]) == 1
    assert datos["conceptos"][0]["estado_dominio"] == "necesita_trabajo"


def test_editar_leccion_actualiza_campos(as_profesora, db):
    leccion_id = crear_leccion_aprobada(db, estado="borrador")
    r = as_profesora.patch(
        f"/dashboard/api/lecciones/{leccion_id}",
        json={
            "tema_principal": "Tema editado",
            "resumen_clase": "Resumen editado",
            "temas_tag": "pin,fork",
            "conceptos_texto": "Pin :: Explicacion del pin",
            "errores_texto": "Error x :: Correccion x :: Principio x",
        },
    )
    assert r.status_code == 200
    conn = db.get_connection()
    fila = conn.execute("SELECT tema_principal, conceptos FROM lecciones WHERE id = ?", (leccion_id,)).fetchone()
    conn.close()
    assert fila["tema_principal"] == "Tema editado"
    assert json.loads(fila["conceptos"]) == [{"nombre": "Pin", "explicacion_dada": "Explicacion del pin"}]
