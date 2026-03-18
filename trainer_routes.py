import chess
import random

from flask import Blueprint, render_template, jsonify, request, session

from trainer import puzzle_loader, exercise_logic, database as trainer_db, statistics as trainer_stats


trainer_bp = Blueprint("trainer", __name__)


PIEZA_NOMBRE = {
    'p': 'Peón', 'n': 'Caballo', 'b': 'Alfil', 'r': 'Torre',
    'q': 'Dama', 'k': 'Rey'
}

PIECE_NAMES_EN = {
    'p': 'Pawn', 'n': 'Knight', 'b': 'Bishop', 'r': 'Rook',
    'q': 'Queen', 'k': 'King'
}


def _pieza_es(piece):
    if piece is None:
        return None
    return PIEZA_NOMBRE.get(piece.symbol().lower(), piece.symbol())


def _piece_en(piece):
    if piece is None:
        return None
    return PIECE_NAMES_EN.get(piece.symbol().lower(), piece.symbol())


def build_piece_explanation(board_before, board_after, sq, lang='es'):
    piece = board_after.piece_at(sq)
    if piece is None:
        return ''
    if piece.symbol().lower() == 'k':
        return ''
    piece_name = _pieza_es(piece) if lang == 'es' else _piece_en(piece)
    sq_name = chess.square_name(sq)
    color = piece.color
    opponent = not color
    attackers = list(board_after.attackers(opponent, sq))
    defenders_before = list(board_before.attackers(color, sq))
    defenders_after = list(board_after.attackers(color, sq))
    lost_defenders = [d for d in defenders_before if d not in defenders_after]
    attacker_str = ''
    if attackers:
        att = board_after.piece_at(attackers[0])
        att_name = _pieza_es(att) if lang == 'es' else _piece_en(att)
        att_sq = chess.square_name(attackers[0])
        attacker_str = att_name + ' en ' + att_sq if lang == 'es' else att_name + ' on ' + att_sq
    if lost_defenders:
        lost_def = board_before.piece_at(lost_defenders[0])
        lost_name = _pieza_es(lost_def) if lang == 'es' else _piece_en(lost_def)
        if lang == 'es':
            return (
                piece_name + ' en ' + sq_name + ': quedó sin defensor después de que '
                'el ' + lost_name + ' se movió. '
                + ('Ahora ' + attacker_str + ' la ataca.' if attacker_str else 'Quedó expuesta.')
            )
        else:
            return (
                piece_name + ' on ' + sq_name + ': lost its defender when '
                'the ' + lost_name + ' moved away. '
                + ('Now ' + attacker_str + ' is attacking it.' if attacker_str else "Now it's exposed.")
            )
    else:
        if lang == 'es':
            return (
                piece_name + ' en ' + sq_name + ': no tenía defensor '
                + ('y ahora ' + attacker_str + ' la ataca.' if attacker_str else '— quedó expuesta.')
            )
        else:
            return (
                piece_name + ' on ' + sq_name + ': had no defender '
                + ('and now ' + attacker_str + ' is attacking it.' if attacker_str else '— left exposed.')
            )


def count_vulnerable(puzzle):
    try:
        board = chess.Board(puzzle['FEN'])
        moves = puzzle.get('Moves', '').strip().split()
        if not moves:
            return 0
        board.push_uci(moves[0])
        return len(exercise_logic.get_vulnerable_pieces(board))
    except Exception:
        return 0


LEVEL_FILTERS = {
    'beginner': lambda n: n == 1,
    'intermediate': lambda n: 2 <= n <= 3,
    'advanced': lambda n: n >= 4,
}


@trainer_bp.route("/trainer")
def trainer_index():
    return render_template("trainer.html")


@trainer_bp.route("/trainer/api/ping")
def trainer_ping():
    return jsonify({"status": "ok"})


@trainer_bp.route("/trainer/api/session/start")
def trainer_session_start():
    level = request.args.get('level', 'beginner')
    if level not in LEVEL_FILTERS:
        level = 'beginner'

    df = puzzle_loader.load_puzzles('puzzles/lichess_db_puzzle.csv')
    puzzles = puzzle_loader.filter_puzzles(df, None, 800, 1400, 10)

    filter_fn = LEVEL_FILTERS.get(level, LEVEL_FILTERS['beginner'])
    filtered = [p for p in puzzles if filter_fn(count_vulnerable(p))]
    if len(filtered) < 5:
        filtered = puzzles

    session['puzzles'] = filtered
    session['level'] = level

    conn = trainer_db.get_local_connection()
    try:
        session_id = trainer_db.start_session(conn, 'quick_training', '800-1400', len(filtered))
    finally:
        conn.close()

    puzzle_data = _puzzle_response(0)
    return jsonify({
        'session_id': session_id,
        'total': len(filtered),
        'level': level,
        'first_puzzle': puzzle_data
    })


def _puzzle_response(index):
    puzzles = session.get('puzzles')
    if not puzzles or index < 0 or index >= len(puzzles):
        return None
    p = puzzles[index]
    fen = p['FEN']
    moves_str = p.get('Moves', '')
    if not moves_str or not moves_str.strip():
        return None
    first_move_uci = moves_str.strip().split()[0]
    board = chess.Board(fen)
    from_sq = first_move_uci[0:2]
    to_sq = first_move_uci[2:4]
    piece_at_from = board.piece_at(chess.parse_square(from_sq))
    piece_name = _pieza_es(piece_at_from) if piece_at_from else 'Pieza'
    board.push_uci(first_move_uci)
    vulnerable = exercise_logic.get_vulnerable_pieces(board)
    vulnerable_json = {chess.square_name(sq): typ for sq, typ in vulnerable.items()}
    orientation = 'white' if board.turn == chess.WHITE else 'black'
    return {
        'index': index,
        'fen': board.fen(),
        'orientation': orientation,
        'rival_move': {'from': from_sq, 'to': to_sq, 'piece': piece_name},
        'vulnerable': vulnerable_json,
        'vulnerable_count': len(vulnerable),
        'total': len(puzzles)
    }


@trainer_bp.route("/trainer/api/puzzle/<int:index>")
def trainer_get_puzzle(index):
    puzzle_data = _puzzle_response(index)
    if puzzle_data is None:
        return jsonify({'error': 'Puzzle no encontrado'}), 404
    return jsonify(puzzle_data)


@trainer_bp.route("/trainer/api/session/summary/<int:session_id>")
def trainer_session_summary(session_id):
    conn = trainer_db.get_local_connection()
    try:
        stats = trainer_db.get_session_stats(conn, session_id)
        insights = trainer_stats.get_scan_insights(conn, session_id)
    finally:
        conn.close()
    return jsonify({
        'total': stats['total'],
        'correct': stats['correct'],
        'accuracy': stats['accuracy'],
        'avg_time_ms': stats['avg_time_ms'],
        'errors_by_theme': stats['errors_by_theme'],
        'sector_weakness': insights.get('sector_weakness'),
        'avg_scan_time_ms': insights.get('avg_scan_time_ms', 0.0),
        'false_positive_rate': insights.get('false_positive_rate', 0.0),
    })


@trainer_bp.route("/trainer/api/result", methods=['POST'])
def trainer_api_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON requerido'}), 400
    session_id = data.get('session_id')
    puzzle_index = data.get('puzzle_index')
    marked_squares = data.get('marked_squares', [])
    elapsed_ms = data.get('elapsed_ms', 0)
    scan_time_ms = data.get('scan_time_ms', 0)
    lang = data.get('lang', 'es')
    if lang not in ('es', 'en'):
        lang = 'es'

    puzzles = session.get('puzzles')
    if not puzzles or puzzle_index < 0 or puzzle_index >= len(puzzles):
        return jsonify({'error': 'Sesión o puzzle inválido'}), 400

    p = puzzles[puzzle_index]
    fen = p['FEN']
    moves_str = p.get('Moves', '').strip().split()
    if not moves_str:
        return jsonify({'error': 'Puzzle sin jugadas'}), 400
    first_move_uci = moves_str[0]
    board_before = chess.Board(fen)
    board = chess.Board(fen)
    board.push_uci(first_move_uci)
    vulnerable = exercise_logic.get_vulnerable_pieces(board)
    vulnerable_by_name = {chess.square_name(sq): typ for sq, typ in vulnerable.items()}

    marked_set = set(marked_squares)
    correct_set = set(vulnerable_by_name.keys())

    missed = []
    for sq_name in correct_set:
        if sq_name not in marked_set:
            sq = chess.parse_square(sq_name)
            typ = vulnerable_by_name[sq_name]
            piece = board.piece_at(sq)
            if piece is not None:
                opponent = not piece.color
                attackers = board.attackers(opponent, sq)
                if attackers:
                    att_sq = next(iter(attackers))
                    att_piece = board.piece_at(att_sq)
                    missed.append({
                        'square': sq_name,
                        'type': typ,
                        'attacker_square': chess.square_name(att_sq),
                        'attacker_piece': _pieza_es(att_piece),
                        'explanation': build_piece_explanation(board_before, board, sq, lang)
                    })
                else:
                    missed.append({
                        'square': sq_name,
                        'type': typ,
                        'attacker_square': None,
                        'attacker_piece': None,
                        'explanation': build_piece_explanation(board_before, board, sq, lang)
                    })

    false_positives = [sq for sq in marked_set if sq not in correct_set]

    conn = trainer_db.get_local_connection()
    try:
        trainer_db.save_result(
            conn,
            session_id=session_id,
            puzzle_id=p.get('PuzzleId', ''),
            theme=p.get('Themes', ''),
            puzzle_rating=int(p.get('Rating', 0)),
            correct=(len(missed) == 0 and len(false_positives) == 0),
            response_time_ms=int(elapsed_ms),
            board_zone=None,
            prediction_score=None,
            was_trap=None,
            uncertain=None,
            time_vs_minimum=None,
            scan_time_ms=int(scan_time_ms),
            sector_missed=None,
            false_positives=len(false_positives),
        )
    finally:
        conn.close()

    return jsonify({
        'correct': len(missed) == 0 and len(false_positives) == 0,
        'missed': missed,
        'false_positives': false_positives,
    })
