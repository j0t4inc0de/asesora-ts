# Documentación de Mejoras y Nuevas Secciones - Sistema de Reservas AsesoraTS 📅

Este documento detalla todas las mejoras técnicas, de diseño y las nuevas secciones implementadas en el proyecto Django **asesora-ts** para solucionar los conflictos del agendamiento, optimizar la concurrencia y preparar el sitio para su lanzamiento oficial.

---

## 1. Correcciones de Concurrencia y Base de Datos (SQLite + Django) 🗄️

### Modo WAL en SQLite y Timeout Extendido
* **Cambio**: Añadimos configuración de base de datos a nivel de señal en `core/settings.py` para forzar a SQLite a usar el modo **WAL (Write-Ahead Logging)** y extendimos el tiempo de espera de bloqueo de base de datos a **15 segundos** (`busy_timeout=15000`).
* **Motivo**: SQLite por defecto bloquea toda la base de datos en operaciones de escritura, lo que causaba falsos conflictos de "base de datos bloqueada" o inestabilidades bajo solicitudes simultáneas. El modo WAL permite lecturas concurrentes simultáneas mientras se escribe en disco.

### Control de Condiciones de Carrera (TOCTOU)
* **Cambio**: Modificamos `agendar_cita` en `views.py` para ejecutarse enteramente bajo una transacción de base de datos atómica (`transaction.atomic()`). 
* **Flujo seguro**:
  1. Se abre la transacción.
  2. Se eliminan citas antiguas canceladas (`estado='X'`) en el bloque horario solicitado para evitar colisiones de clave única (`unique=True`).
  3. Se comprueba la disponibilidad actual con un `.exists()` protegido. Si el slot está tomado, se lanza un error controlado.
  4. Se crea el registro del cliente y de la cita de forma segura.
  5. Se consolida (commit) la transacción y se procede a la pasarela de pagos.

---

## 2. Nueva Lógica de Expiración de Reservas Fantasma ⏳

### Creación del campo `creada_en`
* **Cambio**: Añadimos el campo `creada_en = models.DateTimeField(auto_now_add=True, null=True)` al modelo `Cita` y aplicamos las correspondientes migraciones en base de datos.
* **Solución al Bug de Expiración**:
  * **Antes**: Las citas pendientes se expiraban evaluando el campo `fecha_hora__lt` (la hora programada de la cita). Si alguien reservaba para el día de mañana a las 10:00 AM y abandonaba el pago, el slot quedaba bloqueado permanentemente hasta que llegaba el día de la cita.
  * **Ahora**: Evaluamos el momento de la solicitud (`creada_en__lt=limite`). Cualquier cita pendiente sin pago se cancela automáticamente a los **30 minutos de haber sido creada**, liberando el slot futuro.
  * Se implementó un fallback dinámico usando consultas `Q` para resguardar la compatibilidad retrospectiva con citas antiguas que posean `creada_en` nulo.
* **Puntos de Aplicación**:
  1. Limpieza en caliente al consultar disponibilidad (`obtener_slots_disponibles`).
  2. Acción masiva en el panel de administración (`expirar_citas_pendientes`).
  3. Comando de consola periódico (`python manage.py expirar_citas`).

---

## 3. Integración Directa de Servicios Gratuitos (Bypass MP) 💰

* **Cambio**: Si el servicio reservado tiene un valor de `$0` (ej: charlas informativas o diagnóstico inicial gratis), el sistema elude de manera automática el flujo de Mercado Pago (que rechaza montos de $0).
* **Flujo**:
  1. Registra al cliente.
  2. Confirma la cita de forma inmediata (`estado='C'`, `estado_pago='PA'`).
  3. Emite un ID de transacción simulado (`FREE-XXXX`).
  4. Envía el correo de confirmación y redirige directamente a la pantalla de éxito.

---

## 4. Mejoras de Interactividad y UX en el Frontend 🎨

### Doble Submit e Indicador de Carga
* Deshabilitamos el botón de reserva inmediatamente después del primer clic y agregamos un spinner con la leyenda *"Procesando reserva..."* para evitar duplicidades de envío de formularios por clics repetidos.

### Validación en Tiempo Real al Seleccionar la Hora (AJAX)
* **Cambio**: En lugar de esperar a que el usuario complete el formulario para informarle que el slot fue tomado, agregamos un controlador interactivo por AJAX en `templates/index.html`.
* **Flujo**: Al hacer clic en un botón de hora, el botón se bloquea temporalmente mostrando *"Verificando..."*. Realiza un `fetch` rápido al endpoint `/api/verificar-slot/`. Si el slot ya no está disponible, se torna de color rojo, se marca como *"Ocupado"*, se deshabilita para siempre y advierte al usuario, ahorrándole tener que rellenar el formulario de diagnóstico en vano.

### Solución a Enlaces de Anclaje Rotos en Subpáginas (Anchor Links)
* **Cambio**: Corregimos los enlaces de navegación del menú desktop y móvil en `base.html` para que utilicen rutas absolutas respecto a la raíz (`/#seccion-servicios` y `/#seccion-reserva`).
* **Motivo**: Al navegar desde páginas secundarias (como Recursos o Contacto), los enlaces relativos intentaban anclarse dentro de la subpágina actual y fallaban. Ahora redirigen al inicio y se desplazan automáticamente a la sección correspondiente.

---

## 5. Nuevas Secciones del Sitio Web 🔗

### Recursos (`/recursos/`)
* Diseñamos una página dedicada con directores oficiales de enlace a plataformas chilenas relevantes (**Registro Social de Hogares, ChileAtiende, Minvu y Poder Judicial**).
* Implementamos un acordeón interactivo y fluido con preguntas frecuentes sobre peritajes, confidencialidad, recopilación de documentos requeridos y la naturaleza del Informe Social.

### Contacto (`/contacto/`)
* Tarjetas operativas claras detallando la modalidad de atención (**100% online vía videollamada para todo Chile** y alcance de visitas domiciliarias presenciales).
* Canales directos e interactivos:
  * Enlace `mailto` directo a `consultas.asesorats@gmail.com`.
  * Botón directo de redirección a **WhatsApp** cargando un mensaje pre-estructurado de cotización profesional.

### Páginas Legales y Footer Corporativo
* Creados los templates de [Términos y Condiciones](file:///D:/Proyectos/Paginas/Ficheros%20Django/asesora-ts/asesorias/templates/legal/terminos.html) y [Política de Privacidad](file:///D:/Proyectos/Paginas/Ficheros%20Django/asesora-ts/asesorias/templates/legal/privacidad.html), eliminando cualquier tipo de emoji para mantener el rigor del secreto profesional del Trabajador Social y cumplir con las normativas legales de Mercado Pago en Chile.
* Rediseñamos el pie de página de la plantilla base en dos niveles responsivos, añadiendo los enlaces legales y el copyright formal con enlace a la firma digital:
  `© 2026 AsesoraTS Chile by Samod — Un producto de We Are Samod` (apuntando a [wearesamod.com](https://wearesamod.com)).

---

## 6. Pruebas de Calidad Realizadas (Testing) 🧪

* Implementamos 5 tests de integración automatizados en `asesorias/tests.py` que validan de punta a punta:
  1. El correcto estado de disponibilidad reportado por la API de validación.
  2. La eliminación en caliente de citas canceladas y prevención de doble reserva en `agendar_cita` (mockeando Mercado Pago).
  3. La expiración automática del comando de consola `expirar_citas` evaluando de forma precisa el nuevo campo `creada_en`.
  4. El flujo de bypass para agendamientos gratuitos de precio $0.
  5. La correcta carga y renderización (HTTP 200) de las nuevas páginas legales corporativas.
* **Resultado del Runner**:
  ```bash
  Ran 5 tests in 1.451s
  OK
  ```

---

## 7. Instrucciones para Despliegue en Producción 🚀

Una vez subidos los cambios al servidor de producción, se deben realizar las siguientes acciones dentro del entorno Docker:

1. **Aplicar Migraciones de Base de Datos**:
   Dado que añadimos el campo `creada_en`, es obligatorio ejecutar:
   ```bash
   docker compose exec web python manage.py migrate
   ```
2. **Programar el Comando de Expiración (Cronjob)**:
   Para que las citas abandonadas en la pasarela de Mercado Pago se liberen a los 30 minutos, se debe registrar el siguiente cronjob en el servidor real (se aconseja ejecutarlo cada 15 minutos):
   ```bash
   */15 * * * * docker compose -f /ruta/al/proyecto/docker-compose.yml exec -T web python manage.py expirar_citas --minutes 30 > /dev/null 2>&1
   ```
