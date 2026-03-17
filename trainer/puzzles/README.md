# Carpeta de puzzles

Aquí debe ubicarse el archivo de puzzles tácticos de Lichess para que el entrenador pueda cargarlos.

## Archivo esperado

- **Nombre:** `lichess_db_puzzle.csv`
- **Origen:** base de datos de puzzles de [Lichess](https://database.lichess.org/). Puedes descargar el CSV de puzzles desde su sección de bases de datos (puzzles).
- **Uso:** el módulo `puzzle_loader` lee este CSV, filtra por rango de Elo y muestra puzzles en las sesiones de entrenamiento.

Coloca el archivo `lichess_db_puzzle.csv` en esta carpeta (`chess_pattern_trainer/puzzles/`) antes de ejecutar una sesión.
