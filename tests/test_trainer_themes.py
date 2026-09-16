"""El trainer filtra por Lichess Themes cuando se le pasa el parámetro
nuevo, sin romper el flujo sin `themes` que ya usaba el scanner de piezas
colgadas."""
from trainer import puzzle_loader


def test_filter_puzzles_sin_themes_no_filtra_por_tema():
    df = puzzle_loader.load_puzzles(str(puzzle_loader.DEFAULT_PUZZLE_CSV))
    encontrados = puzzle_loader.filter_puzzles(df, None, 800, 1400, n=10)
    assert len(encontrados) == 10


def test_filter_puzzles_con_themes_solo_devuelve_ese_tema():
    df = puzzle_loader.load_puzzles(str(puzzle_loader.DEFAULT_PUZZLE_CSV))
    encontrados = puzzle_loader.filter_puzzles(df, ["fork"], 800, 1400, n=10)
    assert len(encontrados) > 0
    assert all("fork" in p["Themes"].split() for p in encontrados)


def test_session_start_acepta_themes_por_query_param(client, tmp_path, monkeypatch):
    with client.session_transaction() as sess:
        sess["portal_alumno_ids"] = [1]

    # trainer/database.py tiene su PROPIO DB_PATH (chess_pattern_trainer.db,
    # separado de la DB principal) — se aísla igual que la DB principal para
    # no ensuciar el archivo real con sesiones de test.
    import trainer.database as trainer_db_module
    monkeypatch.setattr(trainer_db_module, "DB_PATH", str(tmp_path / "trainer_test.db"))
    trainer_db_module.create_tables(trainer_db_module.get_local_connection())

    # Registrar trainer_bp en la app de test (conftest no lo incluye porque
    # trainer_routes usa render_template con sus propios templates/estáticos).
    from trainer_routes import trainer_bp
    client.application.register_blueprint(trainer_bp)

    r_sin = client.get("/trainer/api/session/start?level=beginner")
    r_con = client.get("/trainer/api/session/start?level=beginner&themes=fork")
    assert r_sin.status_code == 200
    assert r_con.status_code == 200
