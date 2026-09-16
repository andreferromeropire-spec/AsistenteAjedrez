"""Clases antiguas: una lección cargada antes de que existiera esta capa
(sin leccion_conceptos) puede sumarse a la biblioteca sin volver a llamar
a la IA, y no rompe si se corre dos veces."""
from tests.conftest import LECCION_EJEMPLO


def _crear_leccion_legacy(db):
    """Simula una lección de antes de esta feature: tiene `conceptos`/
    `errores_y_correcciones` guardados, pero nunca pasó por
    vincular_conceptos_y_patrones (0 filas en leccion_conceptos)."""
    import json
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO lecciones (tema_principal, resumen_clase, conceptos,
           errores_y_correcciones, patrones_pensamiento, estado, creado)
           VALUES (?,?,?,?,?,?,datetime('now'))""",
        (
            LECCION_EJEMPLO["tema_principal"],
            LECCION_EJEMPLO["resumen_clase"],
            json.dumps(LECCION_EJEMPLO["conceptos"]),
            json.dumps(LECCION_EJEMPLO["errores_y_correcciones"]),
            json.dumps(LECCION_EJEMPLO["patrones_pensamiento_detectados"]),
            "aprobada",
        ),
    )
    leccion_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    return leccion_id


def test_leccion_legacy_no_tiene_conceptos_vinculados(db):
    leccion_id = _crear_leccion_legacy(db)
    conn = db.get_connection()
    n = conn.execute("SELECT COUNT(*) AS n FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchone()["n"]
    conn.close()
    assert n == 0


def test_generar_retroactivo_vincula_sin_llamar_a_la_ia(as_profesora, db, monkeypatch):
    # Si esto llamara a la IA, este test fallaría por falta de red/API key.
    monkeypatch.setattr("extraer_leccion.extraer_desde_texto", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no debería llamarse")))

    leccion_id = _crear_leccion_legacy(db)
    r = as_profesora.post(f"/dashboard/api/lecciones/{leccion_id}/generar_retroactivo")
    assert r.status_code == 200

    conn = db.get_connection()
    n = conn.execute("SELECT COUNT(*) AS n FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchone()["n"]
    conn.close()
    assert n == 1


def test_generar_retroactivo_es_idempotente(as_profesora, db):
    leccion_id = _crear_leccion_legacy(db)
    as_profesora.post(f"/dashboard/api/lecciones/{leccion_id}/generar_retroactivo")
    as_profesora.post(f"/dashboard/api/lecciones/{leccion_id}/generar_retroactivo")

    conn = db.get_connection()
    n = conn.execute("SELECT COUNT(*) AS n FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchone()["n"]
    total_conceptos = conn.execute("SELECT COUNT(*) AS n FROM conceptos").fetchone()["n"]
    conn.close()
    assert n == 1
    assert total_conceptos == 1


def test_generar_retroactivo_404_si_no_existe(as_profesora):
    r = as_profesora.post("/dashboard/api/lecciones/99999/generar_retroactivo")
    assert r.status_code == 404
