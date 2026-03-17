# Contexto — chess-trainer-web

## Qué es

Web app Flask para un **entrenador táctico de ajedrez**. El usuario ve una posición tras la jugada del rival, escanea el tablero por sectores (flanco dama, centro, flanco rey) y marca las piezas sin defensor (colgadas o vulnerables). Se comparan sus marcas con la solución y al final se muestra un resumen con precisión, tiempo, racha máxima y recomendaciones. Incluye **niveles de dificultad** por cantidad de piezas sin defensor, **perfiles de visualización** (tamaño de tablero y tipografía), **feedback explicativo** por pieza, **sonido** y **rachas** de aciertos.

## Stack

- **Backend:** Python 3, Flask (puerto 5001, debug=True)
- **Base de datos:** SQLite (`database.py`, `chess_pattern_trainer.db`)
- **Frontend:** HTML + Bootstrap 5 (CDN), jQuery, chessboard.js (@chrisoakman/chessboardjs), chess.js, Web Audio API (sonidos sintéticos)
- **Puzzles:** CSV Lichess (`puzzles/lichess_db_puzzle.csv`) con columnas PuzzleId, FEN, Moves, Rating, Themes

## Estructura del proyecto

```
chess-trainer-web/
├── app.py                 # Flask app, rutas y lógica de sesión/puzzle/result/summary
├── database.py            # SQLite: get_connection, create_tables, start_session, save_result, get_session_stats
├── exercise_logic.py      # get_vulnerable_pieces(board), get_hanging_pieces, etc.
├── puzzle_loader.py       # load_puzzles(path), filter_puzzles(df, themes, elo_min, elo_max, n)
├── statistics.py          # get_scan_insights(conn, session_id) → sector_weakness, avg_scan_time_ms, false_positive_rate
├── requirements.txt      # flask, python-chess, pandas, pillow
├── templates/
│   └── trainer.html       # Página única: tablero #board, #board-wrapper, #scan-overlay (flechas SVG), panel #panel, #exercise-progress-bar, selector nivel/perfil, botón sonido
├── static/
│   └── trainer.js         # initBoard, applyProfile, startSession, loadPuzzle, escaneo, marcado, submit, showFeedback, drawArrow, playSound, racha, resumen
├── puzzles/
│   ├── lichess_db_puzzle.csv
│   └── README.md
└── CONTEXTO.md            # Este archivo
```

## Flujo de una sesión (fases en `sessionState.phase`)

1. **loading** — Carga de puzzles vía `GET /api/session/start?level=beginner|intermediate|advanced`.
2. **rival_move** — Se muestra la posición tras la primera jugada del rival (resaltado amarillo from/to), 2,5 s.
3. **scanning** — Tres sectores (a-c, d-e, f-h), 2 s cada uno con resaltado blanco semitransparente.
4. **marking** — Usuario marca casillas sin defensor; botón "No hay ninguna" / "Confirmar (n marcadas)" (habilitado a los 3 s; si el tablero no está listo se reintenta a los 200 ms). Clicks en casillas por **delegación** en `document` (#board .square-55d63) para evitar pérdida de listeners al redibujar el tablero.
5. **feedback** — `POST /api/result` (body incluye `lang`). Se muestran aciertos (verde), errores (rojo/amarillo), falsos positivos; **atacantes** resaltados en azul y **flechas SVG** atacante→pieza; explicación por pieza (`missed[].explanation`); **sonido** correct/incorrect (Web Audio); **racha** de aciertos (badge si >1, sonido "streak" cada 3). Un solo botón "Siguiente" / "Comprendido, siguiente" (sin auto-avance).
6. **summary** — `GET /api/session/summary/<session_id>`; métricas, insights, **mejor racha de la sesión** (si ≥ 3), frase de transferencia, pregunta de piezas perdidas, "Nueva Ronda" / "Menú principal".

## API (app.py)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Renderiza `trainer.html` |
| GET | `/api/ping` | `{"status": "ok"}` |
| GET | `/api/session/start` | Query `level` (default beginner). Filtra puzzles por `count_vulnerable` (LEVEL_FILTERS: beginner=1, intermediate=2–3, advanced≥4); si hay <5 usa todos. Devuelve `session_id`, `total`, `level`, `first_puzzle`. |
| GET | `/api/puzzle/<index>` | Puzzle desde sesión: FEN, orientation, rival_move, vulnerable, **vulnerable_count** |
| POST | `/api/result` | Body: session_id, puzzle_index, marked_squares, elapsed_ms, scan_time_ms, **lang** (es/en). Compara con vulnerables; para cada `missed` añade **explanation** vía `build_piece_explanation(board_before, board_after, sq, lang)` (contexto de jugada: defensor que se movió, atacante). Devuelve correct, missed, false_positives. |
| GET | `/api/session/summary/<session_id>` | get_session_stats + get_scan_insights; devuelve total, correct, accuracy, avg_time_ms, errors_by_theme, sector_weakness, avg_scan_time_ms, false_positive_rate |

## Módulos que no se modifican

- **exercise_logic.py** — Lógica de piezas vulnerables/colgadas.
- **puzzle_loader.py** — Carga y filtrado del CSV.
- **statistics.py** — Insights de escaneo.
- **database.py** — Esquema y funciones de persistencia.

Siempre usar `database.get_connection()` y cerrar la conexión; no asumir columnas sin verificar.

## Frontend (resumen)

- **trainer.html:** Variables CSS en `:root` (--fondo, --panel, --panel-alt, --texto, --acento, --error, --font-size-base, --btn-padding, --btn-font-size, etc.). Pantallas centradas (body flex, .screen flex center). **Perfiles de visualización:** selector en home y botón ⚙️ en entrenamiento (overlay con 3 opciones). Barra de progreso de ejercicios (#exercise-progress-bar / #exercise-progress-fill). Botón sonido 🔊/🔇 junto al selector de idioma. Mobile: tablero 100vw, panel scroll, botones sticky 44px. Animaciones fadeIn (pantallas), streakPop (badge de racha). Focus visible en botones.
- **trainer.js:**
  - **sessionState:** sessionId, currentPuzzle, markedSquares, phase, lang, selectedLevel, level, clicksEnabled, profile, **soundEnabled**, **streak**, **maxStreak** (no barCancelled; soundEnabled desde `localStorage.trainer_sound`).
  - **Perfiles:** `PROFILES` (small 560/18px, standard 480/15px, comfort 480/18px). `applyProfile(key)` aplica variables CSS, ancho de #board-wrapper (en mobile 100%), `board.resize()` y opcionalmente `board.position()`; persiste en `trainer_profile`.
  - **Tablero:** `initBoard()` con setTimeout 50 ms; ancho explícito desde perfil (`maxSize = Math.min(profile.boardSize, window.innerWidth - 32)`), se asigna a wrapper y a Chessboard.
  - **Clicks:** Un solo listener en `document` para `#board .square-55d63`; control por `clicksEnabled` y `phase === 'marking'`. En startMarkingPhase se comprueba `$('#board .square-55d63').length > 0` antes de habilitar; si no, reintento a los 200 ms.
  - **Feedback:** `drawArrow(fromSquare, toSquare, color)` dibuja SVG en #scan-overlay; `clearHighlights()` también elimina `.arrow-overlay`. Resaltado de atacantes en azul. `playSound('correct'|'incorrect'|'streak')` con Web Audio (falla en silencio). Racha: incremento en acierto, reset en error; `showStreakBadge(n)`; sonido streak cada 3; maxStreak en resumen si ≥ 3.
  - **Historial:** `getHistoryByLevel()` (objeto por nivel; migración desde array). Historial guardado por nivel en showSummary y al responder "piezas perdidas". Progreso con nivel en loadPuzzle (`progressWithLevel`).
  - Rutas absolutas en fetch: `/api/...`.

## Cómo arrancar

```bash
pip install -r requirements.txt
python app.py
# http://127.0.0.1:5001
```

Las tablas se crean al importar `app` (`with app.app_context(): database.create_tables(conn)`).

## Funcionalidades añadidas (resumen)

- **Niveles:** Principiante (1 pieza sin defensor), Intermedio (2–3), Avanzado (4+). Selector en home, historial y estadísticas por nivel, sugerencia de subir/bajar nivel.
- **Feedback sin auto-avance:** Un solo botón "Siguiente" / "Comprendido, siguiente". Explicación por pieza con contexto de jugada (backend `build_piece_explanation`), idioma en POST /api/result.
- **Rediseño y perfiles:** Variables CSS, perfiles small/standard/comfort (tamaño tablero y tipografía), selector en home y ⚙️ en entrenamiento, barra de progreso de ejercicios, layout centrado (horizontal y vertical), mobile 100vw y botones 44px, animaciones y a11y.
- **Tablero:** Inicialización con ancho explícito desde perfil (setTimeout), redimensionado al cambiar perfil; centrado con flex en body y .screen.
- **Resaltado del atacante:** Casilla del atacante en azul y flecha SVG (drawArrow) en #scan-overlay; se limpia en clearHighlights.
- **Sonido:** Web Audio (correcto: dos notas ascendentes; incorrecto: descendente; racha: tres notas). Toggle 🔊/🔇, preferencia en `trainer_sound`.
- **Racha:** Contador de aciertos seguidos; badge animado si >1; sonido cada 3; reset al fallar y al iniciar sesión; mejor racha en resumen si ≥ 3.
