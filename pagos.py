from database import get_connection
from datetime import date

# Registra un pago nuevo en la base de datos.
# alumno_id: el número de ID del alumno que pagó
# monto: lo que pagó ese mes (puede variar según clases dadas)
# moneda: "Dólar", "Pesos", "Libra Esterlina"
# metodo: "Wise", "PayPal", "Transferencia nacional"
# notas: cualquier aclaración, por ejemplo "pagó 3 clases de febrero"
def registrar_pago(alumno_id, monto, moneda, metodo, notas=None, fecha_pago=None):
    conn = get_connection()
    cursor = conn.cursor()
    # Si no se indica fecha, usa hoy. Los llamadores deben pasar el primer día
    # del mes de las clases para que el pago aparezca en el mes correcto.
    fecha = fecha_pago if fecha_pago else date.today().isoformat()
    cursor.execute("""
        INSERT INTO pagos (alumno_id, fecha, monto, moneda, metodo, notas)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alumno_id, fecha, monto, moneda, metodo, notas))
    pago_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"Pago registrado: alumno {alumno_id} - {monto} {moneda} via {metodo} ({fecha})")
    return pago_id

# Devuelve todos los pagos de un mes y año específico.
# mes y año son números: mes=2, anio=2026 para febrero 2026
def obtener_pagos_del_mes(mes, anio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, a.nombre 
        FROM pagos p
        JOIN alumnos a ON p.alumno_id = a.id
        WHERE strftime('%m', p.fecha) = ? 
        AND strftime('%Y', p.fecha) = ?
    """, (f"{mes:02d}", str(anio)))
    pagos = cursor.fetchall()
    conn.close()
    return pagos

# Compara alumnos mensuales contra pagos del mes actual.
# Devuelve la lista de alumnos que todavía no pagaron este mes.
def quien_debe_este_mes():
    conn = get_connection()
    cursor = conn.cursor()
    hoy = date.today()
    mes = f"{hoy.month:02d}"
    anio = str(hoy.year)

    # Primero busca todos los alumnos con modalidad mensual
    cursor.execute("""
        SELECT * FROM alumnos 
        WHERE modalidad = 'Mensual' AND activo = 1
    """)
    alumnos_mensuales = cursor.fetchall()

    # Después busca quiénes ya pagaron este mes
    cursor.execute("""
        SELECT DISTINCT alumno_id FROM pagos
        WHERE strftime('%m', fecha) = ?
        AND strftime('%Y', fecha) = ?
    """, (mes, anio))
    ids_que_pagaron = {row['alumno_id'] for row in cursor.fetchall()}

    conn.close()

    # Devuelve solo los que NO están en la lista de pagados
    deben = [a for a in alumnos_mensuales if a['id'] not in ids_que_pagaron]
    return deben

# Muestra todo el historial de pagos de un alumno específico
def historial_de_pagos_alumno(alumno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM pagos 
        WHERE alumno_id = ?
        ORDER BY fecha DESC
    """, (alumno_id,))
    pagos = cursor.fetchall()
    conn.close()
    return pagos

# Devuelve los últimos N pagos de un alumno con detalle suficiente
# para que el bot pueda mostrarlos numerados y el usuario elija cuál borrar
def historial_reciente_alumno(alumno_id, limite=5):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fecha, monto, moneda, metodo, notas
        FROM pagos
        WHERE alumno_id = ?
        ORDER BY fecha DESC, id DESC
        LIMIT ?
    """, (alumno_id, limite))
    pagos = cursor.fetchall()
    conn.close()
    return pagos

# Borra un pago y desmarca las clases que estaban vinculadas a él.
# "Desmarcar" significa poner pago_id = NULL para que queden listas
# para ser pagadas de nuevo, como si ese pago nunca hubiera existido.
def borrar_pago(pago_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Primero verificamos que el pago existe
    cursor.execute("SELECT * FROM pagos WHERE id = ?", (pago_id,))
    pago = cursor.fetchone()
    if not pago:
        conn.close()
        return False, "No encontré ese pago."

    # Desvinculamos las clases que tenían este pago_id
    cursor.execute("""
        UPDATE clases SET pago_id = NULL
        WHERE pago_id = ?
    """, (pago_id,))
    clases_desvinculadas = cursor.rowcount  # cuántas clases se desmarcaron

    # Borramos el pago
    cursor.execute("DELETE FROM pagos WHERE id = ?", (pago_id,))
    conn.commit()
    conn.close()
    return True, clases_desvinculadas

# Suma el total cobrado en un mes, agrupado por moneda
# Devuelve algo como: {"Dólar": 350, "Pesos": 54000}
def total_cobrado_en_mes(mes, anio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT moneda, SUM(monto) as total
        FROM pagos
        WHERE strftime('%m', fecha) = ?
        AND strftime('%Y', fecha) = ?
        GROUP BY moneda
    """, (f"{mes:02d}", str(anio)))
    resultados = cursor.fetchall()
    conn.close()
    totales = {row['moneda']: row['total'] for row in resultados}
    return totales