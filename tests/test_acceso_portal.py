"""Permisos: un alumno solo ve sus propias lecciones/conceptos, nunca los
de otro; sin sesión, todo redirige a login (nunca 200 con datos)."""
from tests.conftest import crear_leccion_aprobada, login_alumno


def _asignar(as_profesora, alumno_id, leccion_id):
    return as_profesora.post(
        "/dashboard/api/alumno_lecciones", json={"alumno_id": alumno_id, "leccion_id": leccion_id}
    )


def test_sin_sesion_redirige_a_login(client):
    r = client.get("/portal/lecciones", follow_redirects=False)
    assert r.status_code in (301, 302)


def test_alumno_ve_su_propia_leccion(client, as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    _asignar(as_profesora, alumno_id, leccion_id)

    login_alumno(client, alumno_id)
    r = client.get(f"/portal/lecciones/{leccion_id}")
    assert r.status_code == 200
    assert b"Idea principal" in r.data


def test_alumno_no_ve_leccion_de_otro(client, as_profesora, db, alumno_id, otro_alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    _asignar(as_profesora, alumno_id, leccion_id)

    login_alumno(client, otro_alumno_id)
    r = client.get(f"/portal/lecciones/{leccion_id}", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert r.headers["Location"].endswith("/portal/lecciones")


def test_alumno_no_ve_concepto_de_otro(client, as_profesora, db, alumno_id, otro_alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    _asignar(as_profesora, alumno_id, leccion_id)
    conn = db.get_connection()
    concepto_id = conn.execute("SELECT concepto_id FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchone()[0]
    conn.close()

    login_alumno(client, otro_alumno_id)
    r_detalle = client.get(f"/portal/conceptos/{concepto_id}", follow_redirects=False)
    r_practicar = client.get(f"/portal/practicar/concepto/{concepto_id}", follow_redirects=False)
    assert r_detalle.status_code in (301, 302)
    assert r_practicar.status_code in (301, 302)


def test_alumno_ve_su_propio_concepto(client, as_profesora, db, alumno_id):
    leccion_id = crear_leccion_aprobada(db, estado="aprobada")
    _asignar(as_profesora, alumno_id, leccion_id)
    conn = db.get_connection()
    concepto_id = conn.execute("SELECT concepto_id FROM leccion_conceptos WHERE leccion_id = ?", (leccion_id,)).fetchone()[0]
    conn.close()

    login_alumno(client, alumno_id)
    r = client.get(f"/portal/conceptos/{concepto_id}")
    assert r.status_code == 200
    assert b"Clases donde apareci" in r.data


def test_dashboard_endpoints_requieren_login_profesora(client):
    for url in ["/dashboard/api/lecciones", "/dashboard/api/conceptos", "/dashboard/api/patrones"]:
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302), url
