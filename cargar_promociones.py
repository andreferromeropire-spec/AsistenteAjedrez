from database import get_connection
from promociones import agregar_promo
from alumnos import buscar_alumno_por_nombre

def cargar_todas_las_promociones():
    promos = [
        # Grace y Fiona (id 1) - Dólares
        ("Grace y Fiona", [(1,3,28,"Dólar"), (4,5,26,"Dólar"), (6,8,25,"Dólar")]),
        # Henry Girl (id 16) - Dólares
        ("Henry (Girl)", [(1,3,35,"Dólar"), (4,5,32,"Dólar"), (6,10,28,"Dólar")]),
        # Leila (id 12) - Dólares
        ("Leila", [(1,3,28,"Dólar"), (4,5,26,"Dólar"), (6,8,25,"Dólar")]),
        # Henry (id 2) - Dólares
        ("Henry", [(1,3,28,"Dólar"), (4,5,26,"Dólar"), (6,8,25,"Dólar")]),
        # Ximena y Rafa (id 5) - Dólares
        ("Ximena y Rafa", [(1,3,35,"Dólar"), (4,7,32,"Dólar"), (8,10,29,"Dólar")]),
        # Giuliana (id 6) - Dólares
        ("Giuliana", [(1,3,35,"Dólar"), (4,5,32,"Dólar"), (6,10,30,"Dólar")]),
        # John (id 14) - Dólares
        ("John", [(1,3,35,"Dólar"), (4,5,32,"Dólar"), (6,10,30,"Dólar")]),
        # Jeff (id 7) - Dólares, clase suelta fija
        ("Jeff", [(1,10,35,"Dólar")]),
        # Michael (id 4) - Dólares, precio fijo PayPal
        ("Michael", [(1,10,40,"Dólar")]),
        # Isabella (id 10) - Libras
        ("Isabella", [(1,3,16,"Libra Esterlina"), (4,5,15,"Libra Esterlina"), (6,10,14,"Libra Esterlina")]),
        # Nouham (id 13) - Libras
        ("Nouham", [(1,3,16,"Libra Esterlina"), (4,5,15,"Libra Esterlina"), (6,10,14,"Libra Esterlina")]),
        # Ruby - Libras
        ("Ruby", [(1,3,19,"Libra Esterlina"), (4,5,18,"Libra Esterlina"), (6,10,17,"Libra Esterlina")]),
        # Kerem (id 17) - Libras
        ("Kerem", [(1,3,16,"Libra Esterlina"), (4,5,15,"Libra Esterlina"), (6,10,14,"Libra Esterlina")]),
        # Ilay (id 15) - Pesos, domicilio
        ("Ilay", [(1,10,20000,"Pesos")]),
        # David, George y Larry (id 8) - Pesos, domicilio
        ("David, George y Larry", [(1,10,20000,"Pesos")]),
        # Lucas (id 11) - Pesos, domicilio
        ("Lucas", [(1,10,20000,"Pesos")]),
    ]

    for nombre, rangos in promos:
        alumnos = buscar_alumno_por_nombre(nombre)
        if not alumnos:
            print(f"❌ No encontré: {nombre}")
            continue
        alumno = alumnos[0]
        for clases_desde, clases_hasta, precio, moneda in rangos:
            agregar_promo(alumno['id'], clases_desde, clases_hasta, precio, moneda)
        print(f"✅ Promo cargada: {alumno['nombre']}")

if __name__ == "__main__":
    cargar_todas_las_promociones()
    print("\nTodas las promociones cargadas.")