from database import get_connection

# Agrega los rangos de precio de un alumno.
# Se llama una vez por alumno al configurarlo.
def agregar_promo(alumno_id, clases_desde, clases_hasta, precio_por_clase, moneda):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO promociones (alumno_id, clases_desde, clases_hasta, precio_por_clase, moneda)
        VALUES (?, ?, ?, ?, ?)
    """, (alumno_id, clases_desde, clases_hasta, precio_por_clase, moneda))
    conn.commit()
    conn.close()

# Devuelve todos los rangos de precio de un alumno
def obtener_promo(alumno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM promociones 
        WHERE alumno_id = ?
        ORDER BY clases_desde ASC
    """, (alumno_id,))
    rangos = cursor.fetchall()
    conn.close()
    return rangos

# Dado un alumno y una cantidad de clases, devuelve el precio correcto.
# Por ejemplo: 7 clases para Lidia → $32/clase
def calcular_precio(alumno_id, cantidad_clases):
    rangos = obtener_promo(alumno_id)
    if not rangos:
        return None, None  # No tiene promo cargada
    
    for rango in rangos:
        if rango['clases_desde'] <= cantidad_clases <= rango['clases_hasta']:
            return rango['precio_por_clase'], rango['moneda']
    
    # Si supera todos los rangos, aplica el precio del rango más alto
    ultimo = rangos[-1]
    return ultimo['precio_por_clase'], ultimo['moneda']

# Calcula el monto total a cobrar dado un alumno y cantidad de clases
def calcular_monto(alumno_id, cantidad_clases):
    precio, moneda = calcular_precio(alumno_id, cantidad_clases)
    if precio is None:
        return None, None, None
    monto_total = precio * cantidad_clases
    return monto_total, precio, moneda

# Cuenta las clases agendadas de un alumno en un mes específico
def clases_agendadas_mes(alumno_id, mes, anio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as total FROM clases
        WHERE alumno_id = ?
        AND strftime('%m', fecha) = ?
        AND strftime('%Y', fecha) = ?
        AND estado = 'agendada'
    """, (alumno_id, f"{mes:02d}", str(anio)))
    resultado = cursor.fetchone()
    conn.close()
    return resultado['total']

# Función principal: dado un alumno y un mes,
# devuelve el resumen completo con monto a cobrar
def resumen_cobro_alumno(alumno_id, mes, anio):
    from alumnos import obtener_alumno_por_id
    alumno = obtener_alumno_por_id(alumno_id)
    cantidad = clases_agendadas_mes(alumno_id, mes, anio)
    monto, precio_unitario, moneda = calcular_monto(alumno_id, cantidad)
    
    return {
        "alumno": alumno['nombre'],
        "mes": mes,
        "anio": anio,
        "clases_agendadas": cantidad,
        "precio_por_clase": precio_unitario,
        "monto_total": monto,
        "moneda": moneda
    }

# Calcula el cobro total para un representante
# sumando las clases de todos sus alumnos ese mes
def resumen_cobro_representante(nombre_representante, mes, anio):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Busca todos los alumnos de ese representante
    cursor.execute("""
        SELECT * FROM alumnos 
        WHERE representante LIKE ? AND activo = 1
    """, (f"%{nombre_representante}%",))
    alumnos = cursor.fetchall()
    conn.close()
    
    if not alumnos:
        return None
    
    # Suma las clases de todos los alumnos
    total_clases = 0
    detalle = []
    for alumno in alumnos:
        clases = clases_agendadas_mes(alumno['id'], mes, anio)
        total_clases += clases
        detalle.append(f"{alumno['nombre']}: {clases} clases")
    
    # Usa el id del primer alumno para obtener la promo
    # (todos los alumnos del mismo representante tienen la misma promo)
    monto, precio_unitario, moneda = calcular_monto(alumnos[0]['id'], total_clases)
    
    return {
        "representante": nombre_representante,
        "alumnos": detalle,
        "total_clases": total_clases,
        "precio_por_clase": precio_unitario,
        "monto_total": monto,
        "moneda": moneda,
        "mes": mes,
        "anio": anio
    }

def reemplazar_promo(alumno_id, nuevos_rangos, moneda):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM promociones WHERE alumno_id = ?", (alumno_id,))
    for rango in nuevos_rangos:
        cursor.execute("""
            INSERT INTO promociones (alumno_id, clases_desde, clases_hasta, precio_por_clase, moneda)
            VALUES (?, ?, ?, ?, ?)
        """, (alumno_id, rango["desde"], rango["hasta"], rango["precio"], moneda))
    conn.commit()
    conn.close()