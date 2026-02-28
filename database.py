import sqlite3

# CONEXIÓN: Esta función abre (o crea) el archivo de base de datos.
# Si chess_assistant.db no existe, SQLite lo crea automáticamente.
def get_connection():
    conn = sqlite3.connect("chess_assistant.db")
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre, no solo por índice
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

    conn.commit()
    conn.close()
    print("Base de datos lista.")

# Esto permite correr el archivo directamente para crear las tablas
if __name__ == "__main__":
    crear_tablas()