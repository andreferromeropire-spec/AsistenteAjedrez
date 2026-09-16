# Diario de aprendizaje — qué se implementó

Ver `docs/learning-journal-plan.md` para el análisis y el diseño completo antes de codear. Este documento es el resumen de lo que quedó realmente construido, para orientarse rápido sin releer los 5 commits de la feature.

## Arquitectura en una frase

`lecciones` (ya existía) sigue siendo la mini-lección. Se le sumó una capa de biblioteca reutilizable: `conceptos` y `patrones_pensamiento` (globales, aprobados por la profesora) más `alumno_conceptos`/`alumno_patrones` (progreso personal por repetición), conectados a las lecciones vía `leccion_conceptos`/`leccion_patrones`. Todo el matching es determinístico (difflib), sin llamadas extra a Claude.

## Tablas nuevas

| Tabla | Para qué |
|---|---|
| `conceptos` | Biblioteca global de conceptos ajedrecísticos (nombre, slug, explicación pedagógica, ejemplo, errores frecuentes, `lichess_themes`, nivel, estado borrador/aprobado). |
| `patrones_pensamiento` | Biblioteca global de hábitos de razonamiento (nombre, slug, descripción, ejemplo, estado). |
| `leccion_conceptos` / `leccion_patrones` | Qué concepto/patrón apareció en qué lección, con la redacción puntual de esa clase (`nota`) y si fue confirmado o inferido por la IA. |
| `alumno_conceptos` / `alumno_patrones` | Relación personal: veces trabajado, primera/última vez, y (solo conceptos) `estado_dominio` — `necesita_trabajo` (1 vez) / `en_practica` (2-3) / `dominado` (4+). |

Columnas nuevas en `lecciones`: `clase_id` (FK a `clases`, no usada activamente todavía — ver Pendientes), `reto_practico`, `patrones_pensamiento` (JSON crudo de esa clase puntual).

## Rutas nuevas

**Dashboard** (`dashboard_routes.py`, todas `@login_required`):
- `GET/PATCH/POST.../DELETE /dashboard/api/conceptos[...]` y lo mismo para `/dashboard/api/patrones[...]` — mismo patrón borrador→aprobado que ya usaban las lecciones.
- `POST /dashboard/api/lecciones/<id>/generar_retroactivo` — vincula conceptos/patrones de una lección vieja sin llamar a la IA.
- `GET /dashboard/api/alumnos/<id>/historial_pedagogico` — lecciones + conceptos (con estado de dominio) + patrones de un alumno.
- Pestaña "Lecciones" ampliada con sub-secciones de Conceptos, Patrones y el selector de historial por alumno.

**Portal** (`lecciones_routes.py` extendido + `conceptos_routes.py` nuevo):
- `/portal/lecciones/<id>` — rediseñada: Idea principal, Lo que aprendiste (conceptos expandibles), Tu forma de pensar, Tu reto, botón Practicar.
- `/portal/conceptos` y `/portal/conceptos/<id>` — "Mis conceptos" con 🟢🟡🔴.
- `/portal/practicar/concepto/<id>` — tablero interactivo con puzzles reales de Lichess filtrados por el concepto.

**Trainer** (`trainer_routes.py`): `GET /trainer/api/session/start` acepta `?themes=` opcional (coma-separado).

## IA

`extraer_leccion.py` pide dos campos nuevos además de los que ya devolvía: `reto_practico` y `patrones_pensamiento_detectados` (distinto de `errores_y_correcciones` — un patrón puede reforzarse sin que haya error de por medio). Cada concepto/patrón ahora trae `"confianza": "confirmado" | "inferido"`.

El matching (`conceptos_biblioteca.py`) corre **una sola vez**, al guardar la lección — nunca al visitar el portal. Usa `difflib.get_close_matches` (cutoff 0.8) contra los nombres ya existentes; si no hay match, crea un concepto/patrón nuevo en `estado='borrador'`.

## Trainer

Único cambio: `filter_puzzles()` (que ya soportaba un parámetro `themes`) ahora recibe ese valor desde la query string en vez de `None` hardcodeado. El mecanismo *principal* de "Practicar" para un concepto es la vista nueva `/portal/practicar/concepto/<id>` (reusa el patrón de tablero del puzzle diario, no el trainer) porque el trainer resuelve un ejercicio distinto (detectar piezas colgadas, no resolver la táctica) y su tabla de progreso está hardcodeada a `tipo_patrones='vulnerables'`. La puerta al trainer vía `?themes=` queda abierta como alternativa, no como el camino principal.

## Cómo probarlo

```bash
venv/bin/python -m pytest tests/ -v
```

35 tests, ninguno pega a la API real de Claude (mockeada con `monkeypatch`) ni toca `chess_assistant.db`/`trainer/chess_pattern_trainer.db` reales (cada test usa una SQLite temporal vía `tmp_path`). Cubren: creación/idempotencia de lecciones, matching y dedup de conceptos/patrones, cálculo de `estado_dominio`, gating de estado al asignar (no se puede asignar un borrador), historial pedagógico, edición de lecciones, generación con IA mockeada (éxito, respuesta vacía → 502, error de la IA → 502), permisos de portal (un alumno nunca ve datos de otro), generación retroactiva sobre lecciones "legacy", y filtrado del trainer por `themes`.

Para probar a mano end-to-end: levantar el server local (`PORT=5050 python bot.py`), entrar a `/dashboard` → pestaña Lecciones → generar una lección → aprobarla junto con sus conceptos/patrones → asignarla a un alumno → entrar al portal de ese alumno → ver `/portal/lecciones/<id>`, `/portal/conceptos`, practicar.

## Variables de entorno nuevas

Ninguna — reutiliza `ANTHROPIC_API_KEY` (ya existente) y el CSV de puzzles que ya usaba el trainer.

## Decisiones importantes (por si hace falta revisar el porqué)

- **`estado_dominio` es por repetición, no por resultado de ejercicios** — no hay todavía un lazo que conecte "resolvió mal este puzzle" con "este concepto" en la práctica nueva. Documentado como límite conocido en el plan (§9).
- **No se migró nada retroactivamente de forma automática** — las lecciones viejas quedan sin conceptos vinculados hasta que la profesora aprieta "Vincular conceptos" a mano en su tarjeta.
- **La vista de práctica por concepto es standalone, no reusa/toca el widget del puzzle diario** — copiar el patrón de tablero en vez de refactorizarlo en una función compartida fue deliberado: esta sesión encontró y corrigió dos bugs de escaping distintos (`\n` y `\'` sin doblar la barra dentro de los strings gigantes de Python) tocando ese tipo de código compartido; aislar la vista nueva evita arriesgar una feature que ya andaba en producción.
- **`lecciones.clase_id` existe en el schema pero no se usa activamente** — quedó preparado (nullable, FK a `clases`) para cuando se quiera, desde el dashboard, generar una lección eligiendo una clase puntual del calendario en vez de solo pegar texto suelto. No se conectó una UI para setearlo porque no era necesario para el criterio de éxito pedido.

## Pendientes / fuera de alcance (ya estaban anotados en el plan, se repiten acá para que no se pierdan)

- Conectar resultados reales de la práctica (correcto/incorrecto por puzzle) al `estado_dominio` de un concepto, en vez de solo contar repeticiones.
- Traer de Lichess qué puzzles resolvió/falló el alumno fuera de esta plataforma (necesita scope OAuth `puzzle:read`).
- Búsqueda indexada server-side (hoy es filtro client-side, suficiente al volumen actual por alumno).
- UI para setear `lecciones.clase_id` desde el dashboard al generar una lección.
- Mail de resumen de clase (pendiente de una sesión anterior, sin relación con esta feature — ver `contexto.md`).
