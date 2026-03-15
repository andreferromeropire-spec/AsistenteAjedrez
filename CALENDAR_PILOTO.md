# Google Calendar por profe (sin que te den acceso ni contraseñas)

Cada profe puede usar **su propio Google Calendar**. No te comparten contraseña ni te dan acceso a su cuenta: solo comparten **un calendario** con un email robot (cuenta de servicio). El asistente lee ese calendario y sincroniza las clases.

---

## Para vos (Andrea): configuración una sola vez

### 1. Crear una cuenta de servicio en Google Cloud

1. Entrá a [Google Cloud Console](https://console.cloud.google.com/) y elegí el proyecto que usás para el asistente (o creá uno).
2. **APIs y servicios** → **Credenciales** → **Crear credenciales** → **Cuenta de servicio**.
3. Nombre sugerido: `asistente-ajedrez-calendar`. Crear.
4. En la cuenta de servicio, pestaña **Claves** → **Agregar clave** → **Crear clave** → JSON. Se descarga un archivo `.json`.
5. Abrí el JSON y copiá **todo el contenido** (un objeto con `type`, `project_id`, `private_key_id`, `private_key`, `client_email`, etc.). Ese texto lo vas a usar en Railway.

El **email de la cuenta de servicio** aparece en el JSON como `client_email` (ej. `asistente-ajedrez-calendar@tu-proyecto.iam.gserviceaccount.com`). Ese es el email que cada profe va a “invitar” a su calendario.

### 2. Variables en Railway (por cada profe que use Calendar)

En el **servicio de ese profe** en Railway, agregá (o editá) estas variables:

| Variable | Valor | Notas |
|----------|--------|--------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | El contenido completo del JSON de la cuenta de servicio | Pegar todo el JSON como texto (una sola línea o con saltos, según acepte Railway). **Mismo valor para todos** los pilotos que usen Calendar. |
| `GOOGLE_CALENDAR_ID` | El ID del calendario de ese profe | Ver abajo cómo lo obtiene el profe. **Distinto por cada profe.** |

**Importante:** No pongas `GOOGLE_SERVICE_ACCOUNT_JSON` ni `GOOGLE_CALENDAR_ID` en **tu** instancia (la de Andrea) si seguís usando tu token OAuth y tu calendario "primary". Esas variables son solo para instancias donde el profe usa su propio Calendar.

---

## Para el profe: compartir su calendario (sin darte su contraseña)

Mandales estas instrucciones (podés copiarlas o adaptarlas):

---

**Para que el asistente lea tus clases desde tu Google Calendar:**

1. **Abrí Google Calendar** (calendar.google.com) con tu cuenta.
2. Elegí el **calendario** donde tenés las clases (si usás solo uno, es ese).
3. Al lado del nombre del calendario, hacé clic en los **tres puntitos** → **Configuración y uso compartido** (o **Configuración**).
4. En **Compartir con determinadas personas**, hacé clic en **Agregar personas**.
5. Pegá este email (te lo pasa Andrea):  
   `[EL_EMAIL_DE_LA_CUENTA_DE_SERVICIO]`  
   Ejemplo: `asistente-ajedrez-calendar@proyecto.iam.gserviceaccount.com`
6. Elegí el permiso **"Ver todos los detalles del evento"** (solo lectura). Guardar.
7. **Sacar el ID del calendario:** en la misma pantalla de configuración del calendario, bajá hasta **"Integrar calendario"**. Ahí aparece **"ID del calendario"** (puede ser un email tipo `tuemail@gmail.com` o un texto largo). **Copiá ese ID** y pasáselo a Andrea.

Andrea lo configura en el sistema y después, cuando sincronicen el calendario desde el asistente, se cargarán las clases de **tu** calendario.

No tenés que dar tu contraseña de Google ni dar acceso a tu cuenta: solo compartiste un calendario con un “robot” que lee los eventos.

---

## Resumen

| Quién | Qué hace |
|-------|----------|
| **Vos** | Creás una cuenta de servicio en Google Cloud, sacás el JSON y el `client_email`. En cada servicio de profe que use Calendar: ponés `GOOGLE_SERVICE_ACCOUNT_JSON` (mismo para todos) y `GOOGLE_CALENDAR_ID` (el ID que te pasó ese profe). |
| **El profe** | Comparte su calendario con el email de la cuenta de servicio (permiso “Ver todos los detalles”) y te pasa el ID de ese calendario. |

Así cada uno usa su propio Google Calendar sin que te den acceso ni contraseñas.
