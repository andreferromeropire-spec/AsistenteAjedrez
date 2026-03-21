DEMO_ALUMNOS = [
    {
        "id": 1,
        "nombre": "Lucas M.",
        "moneda": "USD",
        "precio_clase": 30,
        "clases_mes": 8,
        "pagado_mes": 210,
        "deuda_mes": 30,
        "pais": "AR",
    },
    {
        "id": 2,
        "nombre": "Grace K.",
        "moneda": "GBP",
        "precio_clase": 25,
        "clases_mes": 6,
        "pagado_mes": 150,
        "deuda_mes": 0,
        "pais": "UK",
    },
    {
        "id": 3,
        "nombre": "Henry S.",
        "moneda": "USD",
        "precio_clase": 28,
        "clases_mes": 5,
        "pagado_mes": 84,
        "deuda_mes": 56,
        "pais": "US",
    },
    {
        "id": 4,
        "nombre": "Emma R.",
        "moneda": "ARS",
        "precio_clase": 9000,
        "clases_mes": 4,
        "pagado_mes": 27000,
        "deuda_mes": 9000,
        "pais": "AR",
    },
]

DEMO_INGRESOS = {
    "labels": ["Ene", "Feb", "Mar", "Abr"],
    "USD": [120, 200, 340, 280],
    "GBP": [0, 75, 150, 150],
    "ARS": [80000, 120000, 95000, 110000],
}

DEMO_PORTAL_RESUMEN = [
    {
        "alumno_id": 1,
        "nombre": "Lucas M.",
        "al_dia": False,
        "clases_mes": [
            {"fecha": "2026-03-02", "hora": "18:00", "estado": "dada"},
            {"fecha": "2026-03-09", "hora": "18:00", "estado": "dada"},
            {"fecha": "2026-03-16", "hora": "18:00", "estado": "agendada"},
        ],
        "clases_impagas": 2,
        "proxima_clase": {"fecha": "2026-03-16", "hora": "18:00"},
        "mail_responsable": "lucas-demo@example.com",
    }
]

