# Planilla de alumnos para importación masiva (pilotos)

Cada profe puede tener su propia planilla en Google Sheets para hacer una **primera carga de alumnos** en su instancia. Vos (Andrea) configurás el ID de esa planilla en Railway y después se usa el botón/link de sincronizar alumnos.

---

## Para vos (Andrea): pasos por cada profe que quiera usar planilla

1. **El profe crea una copia** de una planilla con el formato de abajo (o crea una desde cero con esas columnas).
2. **Comparte la planilla** con la cuenta de Google que usás para el token del asistente (la que está en `GOOGLE_TOKEN_JSON`). Tiene que tener permiso de **lector** como mínimo.
3. **Sacás el ID de la planilla** de la URL:
   - URL tipo: `https://docs.google.com/spreadsheets/d/XXXXXXXXXX/edit`
   - El ID es la parte `XXXXXXXXXX`.
4. En Railway, en el **servicio de ese profe**, agregás la variable de entorno:
   - Nombre: `GOOGLE_SHEET_ID`
   - Valor: ese ID (ej. `1LpfRUAPy-05h7IpRuZdR9iWqs_joW5xASJUQXt2GPX4`).
5. Después de que el servicio reinicie, entrás a:
   - `https://<servicio-ese-profe>.railway.app/sincronizar_alumnos`
   - Eso importa los alumnos de **esa** planilla a la base de **ese** profe.

Si no querés que un profe use planilla, no ponés `GOOGLE_SHEET_ID` para ese servicio y cargás alumnos a mano desde el dashboard (como en el checklist del onboarding).

---

## Formato de la planilla (para el profe o para vos)

- **Fila 5** = encabezados (los títulos de cada columna).
- **Desde la fila 6** = un alumno por fila.

Columnas (desde la columna A; la primera columna puede estar vacía):

| Columna | Contenido | Ejemplo |
|---------|-----------|---------|
| A | (vacío o lo que quieran) | |
| B | Representante | Lidia |
| C | **Nombre** (obligatorio) | Ximena |
| D | País | Argentina |
| E | Idioma | Español |
| F | Contacto preferido | WhatsApp |
| G | Mail | ximena@mail.com |
| H | WhatsApp | +54 9 11 1234-5678 |
| I | Promo (rangos de precio) | 1-3 clases: $35/h, 4-7: $32/h |
| J | Moneda | $ o USD o £ o ARS |
| K | Método de pago | Wise |
| L | Modalidad | Mensual |
| M | Notas / recordatorio | Clase los martes |

**Promo (columna I):** texto con rangos, uno por línea, por ejemplo:
```
1-3 clases: $35/h
4-7 clases: $32/h
8-10 clases: $29/h
```

**Moneda (columna J):** `$` o USD = Dólar, `£` o GBP = Libra Esterlina, ARS = Pesos.

---

## Resumen

- **¿Necesitan crear una planilla?** No es obligatorio. Podés cargar 2–3 alumnos a mano en el dashboard y listo.
- **Si quieren importación masiva:** crean la planilla con este formato, la comparten con tu cuenta de Google, vos ponés `GOOGLE_SHEET_ID` en su servicio y después abrís `/sincronizar_alumnos` de ese servicio una vez.
