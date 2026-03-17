"""
Lógica de un solo ejercicio: validar jugada, cronometrar, determinar zona del tablero.
"""

from typing import Optional

import chess

# Valores válidos para board_zone (guardados en results para heatmap futuro)
BOARD_ZONE_QUEENSIDE = "queenside"
BOARD_ZONE_KINGSIDE = "kingside"
BOARD_ZONE_CENTER = "center"


def get_hanging_pieces(board: chess.Board, color: chess.Color) -> list[int]:
    """
    Piezas que están atacadas por al menos una pieza rival y no defendidas por ninguna propia.
    No incluye al rey. Devuelve lista de squares (0-63).
    """
    result = []
    opponent = not color
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color or piece.piece_type == chess.KING:
            continue
        attackers_opp = board.attackers(opponent, square)
        defenders_own = board.attackers(color, square)
        if attackers_opp and not defenders_own:
            result.append(square)
    return result


def get_pinned_pieces(board: chess.Board, color: chess.Color) -> list[int]:
    """
    Piezas del color dado que están clavadas. Usa board.is_pinned(color, square).
    """
    result = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color:
            continue
        if board.is_pinned(color, square):
            result.append(square)
    return result


def get_board_inventory(board: chess.Board) -> dict:
    """
    Conteo y ubicaciones de todas las piezas por color y tipo.
    Formato: {WHITE: {PAWN: {count, squares}, ...}, BLACK: {...}}
    """
    piece_types = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
    inv = {
        chess.WHITE: {pt: {"count": 0, "squares": []} for pt in piece_types},
        chess.BLACK: {pt: {"count": 0, "squares": []} for pt in piece_types},
    }
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        inv[piece.color][piece.piece_type]["count"] += 1
        inv[piece.color][piece.piece_type]["squares"].append(square)
    return inv


def get_board_zone(square: int) -> str:
    """
    Devuelve "queenside" si columna <= 3, "kingside" si columna >= 5, "center" si columna 4 (e).
    """
    file = chess.square_file(square)
    if file <= 3:
        return BOARD_ZONE_QUEENSIDE
    if file >= 5:
        return BOARD_ZONE_KINGSIDE
    return BOARD_ZONE_CENTER


def validate_answer(
    exercise_type: str,
    correct_squares: list[int],
    clicked_square: int,
) -> bool:
    """
    Para board_inventory, quick_training y speed_directed: True si clicked_square está en correct_squares.
    """
    return clicked_square in correct_squares


# --- Funciones del esqueleto (sin implementar, para compatibilidad con main/board_ui) ---


def is_correct_move(
    user_from: str,
    user_to: str,
    solution_moves_uci: list[str],
) -> bool:
    """Comprueba si la jugada del usuario coincide con la solución."""
    pass


def uci_to_board_zone(from_square: str, to_square: str) -> Optional[str]:
    """Determina la zona del tablero según las casillas involucradas."""
    pass


def start_timer() -> float:
    """Inicia el cronómetro para tiempo de respuesta."""
    pass


def elapsed_ms(since: float) -> int:
    """Milisegundos transcurridos desde since."""
    pass


def get_first_move_uci(solution_moves_uci: list[str]) -> tuple[str, str]:
    """Extrae el primer movimiento de la solución en (from_square, to_square) UCI."""
    pass


def get_sector(square: int) -> str:
    """
    Devuelve el sector del tablero según la columna del square:
    - "queenside" si file <= 2
    - "center" si file == 3 o 4
    - "kingside" si file >= 5
    """
    file = chess.square_file(square)
    if file <= 2:
        return "queenside"
    if file in (3, 4):
        return "center"
    return "kingside"


def classify_threats(board: chess.Board) -> dict[int, str]:
    """
    Clasifica piezas sin defensor de ambos colores.

    Retorna un diccionario {square: "undefended"} para cada pieza (excepto el rey)
    que esté atacada por al menos una pieza rival y no tenga defensores propios.
    """
    amenazas: dict[int, str] = {}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        color = piece.color
        opponent = not color
        atacantes = board.attackers(opponent, square)
        defensores = board.attackers(color, square)
        if atacantes and not defensores:
            amenazas[square] = "undefended"
    return amenazas


def get_vulnerable_pieces(board: chess.Board) -> dict[int, str]:
    """
    Clasifica piezas de ambos colores en dos categorías:
    - "hanging": atacada por rival Y sin ningún defensor propio
    - "vulnerable": sin ningún defensor propio Y sin atacantes (expuesta pero no atacada aún)
    No incluye reyes. Retorna {square: "hanging"|"vulnerable"}
    """
    result: dict[int, str] = {}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        opponent = not piece.color
        attackers = board.attackers(opponent, square)
        defenders = board.attackers(piece.color, square)
        if defenders:
            continue
        if attackers:
            result[square] = "hanging"
        else:
            result[square] = "vulnerable"
    return result


if __name__ == "__main__":
    # Test con posición simple: rey blanco en e1, torre negra ataca peón blanco en e4 sin defensa
    board = chess.Board("4k3/8/8/8/4P3/8/8/4K3 b - - 0 1")
    board.turn = chess.BLACK
    # Peón e4 atacado por nada aquí; probamos solo inventory y zone
    inv = get_board_inventory(board)
    print("get_board_inventory:", inv[chess.WHITE][chess.PAWN])
    print("get_board_zone(e4):", get_board_zone(chess.E4))
    print("get_board_zone(a1):", get_board_zone(chess.A1))
    print("get_board_zone(h8):", get_board_zone(chess.H8))
    hanging_w = get_hanging_pieces(board, chess.WHITE)
    print("get_hanging_pieces(WHITE):", hanging_w)
    print("validate_answer('quick_training', [chess.E4], chess.E4):", validate_answer("quick_training", [chess.E4], chess.E4))
    print("validate_answer('quick_training', [chess.E4], chess.E5):", validate_answer("quick_training", [chess.E4], chess.E5))
