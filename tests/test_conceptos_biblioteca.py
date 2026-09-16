"""Matching/dedup de conceptos y patrones, y cálculo de estado_dominio."""
from conceptos_biblioteca import (
    _slugificar,
    _buscar_o_crear,
    vincular_conceptos_y_patrones,
    actualizar_progreso_alumno,
    _estado_dominio,
)
from tests.conftest import LECCION_EJEMPLO, crear_leccion_aprobada


def test_slugificar_normaliza_acentos_y_espacios():
    assert _slugificar("Ataque a la Descubierta") == "ataque_a_la_descubierta"
    assert _slugificar("Clavada (pin)") == "clavada_pin"


def test_buscar_o_crear_reusa_por_slug_exacto(db):
    conn = db.get_connection()
    id1 = _buscar_o_crear(conn, "conceptos", "ataque_a_la_descubierta", {"estado": "borrador"})
    id2 = _buscar_o_crear(conn, "conceptos", "ataque_a_la_descubierta", {"estado": "borrador"})
    conn.commit()
    conn.close()
    assert id1 == id2


def test_buscar_o_crear_reusa_por_similitud(db):
    conn = db.get_connection()
    id1 = _buscar_o_crear(conn, "conceptos", "Ataque a la descubierta", {"estado": "borrador"})
    # nombre levemente distinto, mismo concepto en la práctica
    id2 = _buscar_o_crear(conn, "conceptos", "ataques a la descubierta", {"estado": "borrador"})
    conn.commit()
    total = conn.execute("SELECT COUNT(*) AS n FROM conceptos").fetchone()["n"]
    conn.close()
    assert id1 == id2
    assert total == 1


def test_buscar_o_crear_no_junta_conceptos_distintos(db):
    conn = db.get_connection()
    id1 = _buscar_o_crear(conn, "conceptos", "ataque_a_la_descubierta", {"estado": "borrador"})
    id2 = _buscar_o_crear(conn, "conceptos", "horquilla_de_caballo", {"estado": "borrador"})
    conn.commit()
    conn.close()
    assert id1 != id2


def test_vincular_conceptos_y_patrones_crea_en_borrador(db):
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO lecciones (tema_principal, resumen_clase, creado) VALUES (?,?,datetime('now'))",
        ("prueba", "resumen"),
    )
    leccion_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    vincular_conceptos_y_patrones(conn, leccion_id, LECCION_EJEMPLO)
    conn.commit()

    conceptos = conn.execute("SELECT * FROM conceptos").fetchall()
    patrones = conn.execute("SELECT * FROM patrones_pensamiento").fetchall()
    vinculos_c = conn.execute("SELECT * FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchall()
    vinculos_p = conn.execute("SELECT * FROM leccion_patrones WHERE leccion_id = ?", (leccion_id,)).fetchall()
    conn.close()

    assert len(conceptos) == 1
    assert conceptos[0]["estado"] == "borrador"
    assert len(patrones) == 1
    assert len(vinculos_c) == 1
    assert len(vinculos_p) == 1


def test_vincular_no_duplica_si_se_llama_dos_veces(db):
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO lecciones (tema_principal, resumen_clase, creado) VALUES (?,?,datetime('now'))",
        ("prueba", "resumen"),
    )
    leccion_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    vincular_conceptos_y_patrones(conn, leccion_id, LECCION_EJEMPLO)
    vincular_conceptos_y_patrones(conn, leccion_id, LECCION_EJEMPLO)
    conn.commit()

    vinculos_c = conn.execute("SELECT * FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchall()
    conn.close()
    assert len(vinculos_c) == 1  # UNIQUE(leccion_id, concepto_id) + INSERT OR IGNORE


def test_estado_dominio_por_repeticion():
    assert _estado_dominio(1) == "necesita_trabajo"
    assert _estado_dominio(2) == "en_practica"
    assert _estado_dominio(3) == "en_practica"
    assert _estado_dominio(4) == "dominado"
    assert _estado_dominio(10) == "dominado"


def test_actualizar_progreso_alumno_sube_contador_y_dominio(db, alumno_id):
    leccion_id = crear_leccion_aprobada(db)
    conn = db.get_connection()

    actualizar_progreso_alumno(conn, alumno_id, leccion_id)
    conn.commit()
    fila = conn.execute("SELECT * FROM alumno_conceptos WHERE alumno_id = ?", (alumno_id,)).fetchone()
    assert fila["veces_trabajado"] == 1
    assert fila["estado_dominio"] == "necesita_trabajo"
    assert fila["primera_leccion_id"] == leccion_id

    # Asignar la misma lección de nuevo (ej. otra clase con el mismo concepto)
    actualizar_progreso_alumno(conn, alumno_id, leccion_id)
    conn.commit()
    fila2 = conn.execute("SELECT * FROM alumno_conceptos WHERE alumno_id = ?", (alumno_id,)).fetchone()
    conn.close()
    assert fila2["veces_trabajado"] == 2
    assert fila2["estado_dominio"] == "en_practica"


def test_actualizar_progreso_no_mezcla_alumnos(db, alumno_id, otro_alumno_id):
    leccion_id = crear_leccion_aprobada(db)
    conn = db.get_connection()
    actualizar_progreso_alumno(conn, alumno_id, leccion_id)
    conn.commit()
    conn.close()

    conn = db.get_connection()
    fila_otro = conn.execute(
        "SELECT * FROM alumno_conceptos WHERE alumno_id = ?", (otro_alumno_id,)
    ).fetchone()
    conn.close()
    assert fila_otro is None
