# CREDISYSTEM — guía de despliegue

Esta versión queda preparada para desplegarse detrás de un proxy HTTPS con Gunicorn y WhiteNoise.
No publiques el archivo `.env`, la base SQLite local ni credenciales de Firebase.

## 1. Variables mínimas de producción

Crea las variables directamente en el panel del hosting. No subas un `.env` productivo al repositorio.

```env
DJANGO_SECRET_KEY=<clave aleatoria de 50+ caracteres, distinta de desarrollo>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=tu-dominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
BACKEND_PUBLIC_URL=https://tu-dominio.com

DB_ENGINE=mysql
DB_NAME=<base>
DB_USER=<usuario-no-root>
DB_PASSWORD=<password>
DB_HOST=<host>
DB_PORT=3306
DB_SSL_MODE=REQUIRED
```

Completa además SMTP, Mercado Pago, Firebase y WhatsApp cuando esos servicios se habiliten. `.env.example` contiene todos los nombres aceptados.

## 2. Build y arranque

Build:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Release/migraciones:

```bash
python manage.py migrate --noinput
```

Arranque:

```bash
gunicorn credisystem.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile - --error-logfile -
```

El `Procfile` ya contiene los comandos de release y web.

## 3. Comprobaciones antes de publicar

Con las variables productivas cargadas:

```bash
python manage.py check
python manage.py check --deploy
python manage.py check_production
python manage.py migrate --plan
python manage.py collectstatic --noinput
```

`check_production` falla si DEBUG sigue activo, falta la URL HTTPS pública o no se configuraron los orígenes CSRF. También avisa si todavía se usa SQLite, consola de email o faltan credenciales de pago.

## 4. Archivos subidos por usuarios

WhiteNoise sirve **archivos estáticos**, no archivos `MEDIA` subidos por clientes. Los comprobantes cargados en `MEDIA_ROOT` necesitan almacenamiento persistente en el proveedor o, preferentemente, almacenamiento de objetos compatible con S3. No uses el disco efímero de un hosting para comprobantes reales.

## 5. Tareas programadas

Ejecutar una vez al día:

```bash
python manage.py enviar_recordatorios_pago
```

Configúralo como Cron Job/Scheduled Job del proveedor. El comando evita recordatorios duplicados del mismo día.

## 6. Health check

Usar:

```text
/api/health/
```

Responde 200 cuando la aplicación puede consultar la base y 503 cuando la base no está disponible.

## 7. Después del primer deploy

1. Abrir `/api/health/` y verificar `status: ok`.
2. Crear el superusuario desde la consola segura del proveedor si todavía no existe.
3. Probar registro/login y permisos del panel.
4. Probar una solicitud completa con datos de prueba.
5. Configurar y validar el webhook público de Mercado Pago antes de pagos reales.
6. Configurar SMTP antes de depender de recuperación/verificación por email.
7. Configurar almacenamiento persistente de `MEDIA` antes de aceptar comprobantes reales.
8. Ejecutar nuevamente `python manage.py check --deploy` tras cualquier cambio de dominio/proxy.

## Rollback

Conservar la versión anterior de la aplicación y realizar backup de la base antes de migraciones productivas. Si un despliegue falla, volver al release anterior; no borres ni edites migraciones que ya hayan sido aplicadas en producción.
