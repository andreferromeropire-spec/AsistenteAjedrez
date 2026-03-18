# Test plan (manual) — AsistenteAjedrez

Este checklist sirve para validar que la experiencia visible (alumnos + profe) está OK antes de compartirlo con alumnos reales o grabar un demo.

## Pre-requisitos
- Servicio corriendo (local o Railway).
- DB creada (`database.crear_tablas()`).
- Al menos 1 alumno activo en `alumnos`.
- Acceso al portal configurado (Lichess username en `portal_accesos` o login por Google con mail existente).

---

## 1) Login unificado (`/login`)
- Abrir `/login`.
- Ver 2 tarjetas:
  - **Soy alumna / responsable** (por defecto arriba).
  - **Soy profesora** (abajo).
- Click en “Cambiar a acceso de profesora”:
  - La tarjeta “Soy profesora” pasa arriba y se hace principal.
- **Profe**: ingresar contraseña incorrecta → se muestra error y no entra.
- **Profe**: ingresar contraseña correcta → redirige a `/dashboard`.
- **Alumno**: “Entrar con Lichess” → OAuth y luego redirige a `/portal/home`.

Resultado esperado: flujo claro, sin pantallas en blanco ni errores 500.

---

## 2) Portal alumnos (`/portal/home`)
- Ver saludo con nombre del representante o alumno.
- Ver datos del mes:
  - Próxima clase (si existe).
  - Estado de pago (badge verde/rojo).
  - Tabla de clases del mes con estados.
- Columna derecha:
  - Puzzle del día (o fallback “no disponible”).
  - Recordatorios (listar y crear).
  - Card “Entrenamiento de patrones” con botones.

Resultado esperado: la página carga completa y responde rápido.

---

## 3) Trainer (`/trainer`)
- Sin sesión de portal: abrir `/trainer` → redirige a `/login`.
- Con sesión: abrir `/trainer` desde el portal.
- Resolver 2–3 ejercicios.
- Usar “← Portal” para volver a `/portal/home`.

Resultado esperado: los endpoints `/trainer/api/...` responden 200 y no hay errores en consola.

---

## 4) Progreso del trainer (`/portal/entrenamiento`)
- Abrir `/portal/entrenamiento`.
- Ver tabla con métricas por alumno:
  - Ejercicios
  - % acierto
  - Tiempo medio
  - Rating medio
  - Última actividad
- Ver un “Mejor registro” (si hay datos).

Resultado esperado: después de hacer ejercicios, se reflejan acá y en el portal.

---

## 5) Dashboard docente (`/dashboard`)
- Tab “Entrenamiento”:
  - Ver filas por alumno con ejercicios, rating medio y última actividad.
- Ver el resto del dashboard sin regresiones (clases/pagos/alumnos).

Resultado esperado: el dashboard sigue funcionando y muestra el overview del trainer.

---

## 6) Recordatorios por mail

### Configuración
- En Railway, definir:
  - `RESEND_API_KEY`
  - `RESEND_FROM` (remitente verificado en Resend)

### Prueba
- Crear una clase `agendada` para dentro de ~60 min (en DB o via Calendar + sync).
- En portal, crear recordatorio: **30 min antes** → canal mail → mail destino real.
- Esperar hasta que el envío caiga dentro de la ventana del scheduler (corre cada 15 min).

Resultado esperado: llega un mail y se registra en `recordatorios_enviados` (no duplica).

