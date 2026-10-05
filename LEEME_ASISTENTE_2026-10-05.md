# Asistente de preguntas frecuentes — 05/10/2026

La landing incorpora un botón «¿Necesitás ayuda?» que abre el asistente de CREDISYSTEM. Incluye siete preguntas iniciales, búsqueda por palabras y respuestas editables por el superusuario. Funciona dentro de la página, sin servicios externos de IA ni una API de WhatsApp.

## Instalar la actualización

Hacé una copia de seguridad de tu instalación y conservá tu `.env`, tu base de datos y los archivos subidos. Actualizá el código sin reemplazar tus datos con los del ZIP. Con el entorno virtual activo, desde la carpeta que contiene `manage.py`:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py runserver
```

Las dos migraciones nuevas de `frontend` crean las tablas de preguntas y configuración, y cargan siete preguntas iniciales. No cambian las tablas de clientes o créditos. La base de datos distribuida se mantiene sin modificaciones: hay que ejecutar las migraciones. `collectstatic` actualiza los recursos para instalaciones que sirven los archivos desde `staticfiles`.

## Administrar las preguntas

Ingresá con tu superusuario y abrí el panel administrativo. En la sección Frontend:

- **Preguntas frecuentes:** crear, editar o eliminar preguntas. «Orden» define su posición; «Activa» permite ocultarlas sin borrarlas.
- **Respuesta:** texto plano, admite saltos de línea. Es información pública: no cargar datos personales, contraseñas ni informes BCRA. El HTML se muestra como texto.
- **Destino:** seleccioná uno de los enlaces internos disponibles o «Sin enlace». Los destinos de consultas personales llevan primero al login.
- **Configuración del asistente:** permite activar/desactivar el asistente completo y configurar el WhatsApp de atención.

Los cambios aparecen al recargar la landing. Solo el superusuario puede gestionar este contenido, incluso si se asignan permisos de estos modelos a una cuenta staff.

## Contacto por WhatsApp

Ingresá tu número de atención en formato internacional, solo dígitos, sin `+`, espacios ni guiones. Dejalo vacío si no querés mostrar contacto por WhatsApp.

Al configurarlo aparece «Hablar con una persona por WhatsApp». El usuario abre la conversación y decide si envía un mensaje. No se envía automáticamente ningún dato ni el contenido de las consultas. Este botón no crea un bot dentro de WhatsApp: las respuestas automáticas funcionan en la landing.

## Funcionamiento y alcance

- Preguntas sobre solicitud, documentación, revisión, cuotas, recuperación, código de activación y corrección de datos.
- Búsqueda local por palabras, con o sin tildes. No es una conversación de inteligencia artificial ni recibe consultas libres para responderlas.
- Sin historial guardado, llamadas a proveedores de IA ni consultas a cuentas o BCRA desde el asistente.
- Estados de búsqueda sin resultados y catálogo vacío; nunca recupera preguntas desactivadas como alternativa.
- Ventana adaptada a móvil y escritorio, navegación por teclado y cierre con Escape, botón o fondo.
- Gmail, BCRA, perfiles, menú y acceso administrativo conservados.

## Validación

132 pruebas automáticas aprobadas, incluidas 10 nuevas de publicación, edición, permisos, validación de contacto y escape de contenido. `check` sin problemas, sin migraciones pendientes de generar. Migración probada sobre una copia de la base anterior, conservando sus usuarios. Navegador Chromium verificado a 1280, 390 y 320 px: preguntas, búsqueda, enlaces, cierre, teclado y menú sin errores JavaScript.

## Pendientes en tu instalación

- Aplicar migraciones y recargar la landing.
- Revisar y ajustar las respuestas al funcionamiento y condiciones definitivas del servicio.
- Cargar el número real y comprobar que abre la conversación correcta.
- Corroborar el asistente en tu teléfono.
- Siguen pendientes las pruebas reales de Gmail, BCRA, Mercado Pago y despliegue indicadas en la checklist.
