import sqlite3

# CONEXIÓN: Esta función abre (o crea) el archivo de base de datos.
# Si chess_assistant.db no existe, SQLite lo crea automáticamente.
import os

DB_PATH = os.environ.get("DB_PATH", "chess_assistant.db")

def get_connection():
    # Crea la carpeta si no existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# CREAR TABLAS: Esta función define la estructura de la base de datos.
# El IF NOT EXISTS hace que sea seguro correrla varias veces sin borrar datos.
def crear_tablas():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de alumnos: guarda la info fija de cada persona
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            representante TEXT,
            pais TEXT,
            idioma TEXT,
            contacto_preferido TEXT,
            mail TEXT,
            whatsapp TEXT,
            horas_semanales REAL,
            dia_habitual TEXT,
            precio REAL,
            moneda TEXT,
            metodo_pago TEXT,
            modalidad TEXT,
            notas_recordatorio TEXT,
            activo INTEGER DEFAULT 1
        )
    """)

    # Tabla de pagos: cada pago queda registrado con fecha y monto
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            monto REAL,
            moneda TEXT,
            metodo TEXT,
            notas TEXT,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)
    # Tabla de clases: registra cada clase agendada, dada o cancelada
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT,
            estado TEXT NOT NULL DEFAULT 'agendada',
            origen TEXT DEFAULT 'manual',
            google_event_id TEXT,
            notas TEXT,
            fecha_cancelacion TEXT,
            cancelada_por TEXT,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)

    # Tabla de promociones: cada fila es un rango de precio para un alumno
    # Ejemplo: alumno 5, de 1 a 3 clases cobra $35, de 4 a 7 cobra $32, etc.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promociones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            clases_desde INTEGER NOT NULL,
            clases_hasta INTEGER NOT NULL,
            precio_por_clase REAL NOT NULL,
            moneda TEXT NOT NULL,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)
    
    # Tabla de eventos de Calendar a ignorar en sincronizaciones futuras
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos_ignorados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_event_id TEXT NOT NULL UNIQUE,
            titulo TEXT,
            fecha_ignorado TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE alumnos ADD COLUMN alias TEXT")
    except:
        pass  # Ya existe, ignorar

    try:
        cursor.execute("ALTER TABLE alumnos ADD COLUMN clases_credito INTEGER DEFAULT 0")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE clases ADD COLUMN ausente INTEGER DEFAULT 0")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE clases ADD COLUMN pago_id INTEGER")
    except:
        pass  # Ya existe, ignorar

    # acciones_pendientes en DB: funciona con múltiples workers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS acciones_pendientes (
            numero TEXT PRIMARY KEY,
            datos TEXT NOT NULL,
            actualizado TEXT NOT NULL
        )
    """)

    # Configuración clave-valor (ej: token Google renovado para OAuth web)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    # Nuevas tablas para portal de alumnos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portal_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            lichess_username TEXT,
            created_at TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portal_accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lichess_username TEXT NOT NULL,
            alumno_id INTEGER NOT NULL,
            notas TEXT,
            creado TEXT,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)

    # Recordatorios para portal de alumnos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            minutos_antes INTEGER NOT NULL,
            alcance TEXT NOT NULL DEFAULT 'todas',
            canal TEXT NOT NULL DEFAULT 'mail',
            mail_destino TEXT,
            clase_id INTEGER,
            activo INTEGER DEFAULT 1,
            creado TEXT,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordatorios_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recordatorio_id INTEGER,
            clase_id INTEGER,
            enviado_en TEXT,
            UNIQUE(recordatorio_id, clase_id)
        )
    """)

    # Progreso del entrenador táctico de patrones (trainer/)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progreso_entrenamiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            tipo_patrones TEXT,
            dificultad INTEGER,
            resultado TEXT,
            tiempo_segundos INTEGER,
            rating_cambio REAL DEFAULT 0.0,
            FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
        )
    """)

    conn.commit()
    conn.close()
    print("Base de datos lista.")

def get_config(clave):
    """Devuelve el valor de una clave en configuracion, o None."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_config(clave, valor):
    """Guarda o actualiza una clave en configuracion."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (clave, valor)
        )
        conn.commit()
    finally:
        conn.close()


# Esto permite correr el archivo directamente para crear las tablas
if __name__ == "__main__":
    crear_tablas()
    print("Tablas creadas.")