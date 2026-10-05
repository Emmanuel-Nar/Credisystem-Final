# Correo de activación con Gmail — 05/10/2026

El proyecto está preparado para usar Gmail, pero el envío real queda pendiente hasta configurar tu cuenta y comprobar la recepción. No se incluyen credenciales ni se enviaron correos reales durante las pruebas.

## 1. Preparar la cuenta de Google

Usá preferentemente una cuenta dedicada al proyecto. Activá la verificación en dos pasos en la seguridad de Google y luego creá una contraseña de aplicación para CREDISYSTEM:

- Seguridad de Google: https://myaccount.google.com/security
- Contraseñas de aplicación: https://myaccount.google.com/apppasswords
- Ayuda oficial: https://support.google.com/accounts/answer/185833?hl=es

La contraseña de aplicación tiene 16 caracteres. No uses tu contraseña normal de Gmail ni la compartas por chat. Algunas cuentas de organizaciones, con Protección Avanzada o configuraciones especiales de verificación no ofrecen esta opción. Si cambiás la contraseña de Google, se revocan las contraseñas de aplicación y deberás generar otra.

## 2. Completar `.env`

El archivo `.env` va en la misma carpeta que `manage.py`. Si ya existe, editá únicamente estas variables y conservá el resto. Si no existe, copiá `.env.example` como `.env` y completá la configuración.

```dotenv
AUTH_CANAL_VERIFICACION=email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
EMAIL_HOST_USER=tu_cuenta@gmail.com
EMAIL_HOST_PASSWORD=tu_contrasena_de_aplicacion
DEFAULT_FROM_EMAIL=CREDISYSTEM <tu_cuenta@gmail.com>
BACKEND_PUBLIC_URL=http://127.0.0.1:8000
```

Reemplazá las direcciones y la contraseña de ejemplo por las tuyas. El remitente debe coincidir con la cuenta configurada. Se admiten los espacios de agrupación que muestra Google en la contraseña de aplicación. Las variables de entorno del servidor tienen prioridad sobre `.env`: revisalas si un cambio no se refleja.

La URL local sirve para abrir los enlaces en la misma computadora donde corre el proyecto. En el hosting, usá la URL pública HTTPS real; de lo contrario, el enlace del correo apuntará al equipo del destinatario. El código de seis dígitos se puede introducir en la pantalla de verificación.

Reiniciá el servidor después de guardar. No subas `.env` a Git ni lo incluyas en archivos compartidos. No hace falta habilitar POP o IMAP para enviar por SMTP.

## 3. Comprobarlo

Desde la carpeta de `manage.py`, con el entorno virtual activo:

```bash
python manage.py probar_correo
```

Esto revisa la configuración local: no conecta a Gmail ni envía mensajes. Para enviar voluntariamente una prueba a una dirección tuya:

```bash
python manage.py probar_correo --enviar-a tu_cuenta@gmail.com
```

Que el servidor acepte el mensaje no garantiza su llegada a la bandeja principal: comprobá la recepción y Spam. Si falla, revisá la contraseña de aplicación, la verificación en dos pasos y que el hosting permita conexiones salientes al puerto 587. No compartas contraseñas al pedir ayuda.

Después, registrá una cuenta de prueba usando un correo al que tengas acceso. Confirmá que llega el código, que la cuenta permanece inactiva antes de verificarlo y que podés iniciar sesión después de activarla.

## Qué cambió

- El correo ahora lee `.env`, además de las variables del servidor, mediante la configuración central existente.
- Gmail usa SMTP autenticado con STARTTLS, puerto 587 y tiempo de espera configurable.
- El canal predeterminado es email, incluso si la cuenta tiene teléfono. WhatsApp continúa como opción explícita.
- Los errores de envío dejan de ocultarse: el registro informa que la cuenta quedó creada pero el correo no pudo enviarse. La cuenta sigue pendiente y permite solicitar un reenvío sin registrarse otra vez.
- El desarrollo sin SMTP distingue el código mostrado en consola de un correo real. En producción, un backend sin envío no confirma éxito.
- Reenvío y recuperación mantienen respuestas genéricas para no revelar si una dirección está registrada. Los fallos se registran en el servidor sin incluir códigos, contraseñas ni el texto del proveedor.
- Pantallas actualizadas para email; contador de reenvío corregido y reintento inmediato cuando falla el envío inicial.
- Nuevo comando `probar_correo` y control de SMTP en `check_production`.

Este remitente se utiliza para activación y recuperación de contraseña. La aprobación de créditos conserva sus notificaciones internas; esta entrega no agrega un correo de aprobación.

## Validación y actualización

Suite completa: **122 pruebas aprobadas**, incluidas 12 nuevas para configuración, fallos, privacidad y reenvío. Las pruebas usan memoria o respuestas simuladas; no validan una entrega real desde Gmail. `check` sin problemas y ninguna migración nueva por este cambio. Base de datos incluida sin modificaciones.

Se conservan BCRA, protección de identidad del perfil, menú y acceso administrativo. Si venís de la versión anterior con perfil protegido, esta actualización no requiere migraciones adicionales; si todavía no instalaste BCRA, seguí primero `LEEME_BCRA_2026-10-02.md`. Conservá tu base de datos y tu `.env` al actualizar una instalación existente; no reemplaces tus datos por la base del ZIP.
