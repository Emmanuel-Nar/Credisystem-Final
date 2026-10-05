# Ajuste vigente: asistente de preguntas frecuentes (05/10/2026)

La landing incorpora un asistente con siete preguntas, búsqueda local y respuestas editables por el superusuario. WhatsApp de contacto configurable desde administración. Seguí `LEEME_ASISTENTE_2026-10-05.md`: **esta entrega requiere `python manage.py migrate` y `python manage.py collectstatic --noinput`**. Suite vigente: **132 pruebas aprobadas**.

# Ajuste vigente: envío de códigos con Gmail (05/10/2026)

Configurá tu cuenta mediante `LEEME_GMAIL_2026-10-05.md`. El proyecto lee SMTP desde `.env`, distingue fallos de envío y permite comprobar la configuración con `python manage.py probar_correo`. El envío real queda pendiente de tus credenciales y una prueba de recepción. Se conservan BCRA, perfil protegido, menú y login administrativo.

# Ajuste vigente: identidad protegida en el perfil

Nombre, apellido y DNI no se pueden modificar desde la cuenta del cliente; email sigue protegido. Solo se actualizan teléfono, dirección y, desde Seguridad, la contraseña. Ver `LEEME_PERFIL_2026-10-02.md`. Se mantiene toda la integración BCRA de la entrega anterior.

# Última actualización: validación privada BCRA (02/10/2026)

Antes de ejecutar, seguí `LEEME_BCRA_2026-10-02.md`: instalá las dependencias y aplicá `python manage.py migrate`. La suite vigente tiene **132 tests**. La integración agrega CUIL/CUIT, verificación interna y animación en la solicitud, conservando el login administrativo y el menú corregido.

# CREDISYSTEM

Aplicación web para gestión de créditos personales: registro y autenticación segura,
simulación y solicitud de crédito con precalificación automática, pagos integrados con
Mercado Pago, historial de transacciones y notificaciones.

Proyecto académico — Práctica Profesionalizante 2, Tecnicatura Superior en Desarrollo de
Software, Escuela Superior N.º 49 "Cap. Gral. J. J. de Urquiza".

**Integrantes:** Cámara Facundo (Frontend) · Nardone Emmanuel (Backend)

---

## Stack

- **Backend:** Django 5.2 LTS + Django REST Framework
- **Base de datos:** MySQL (SQLite como fallback automático en desarrollo)
- **Autenticación:** JWT (`djangorestframework-simplejwt`)
- **Pagos:** API de Mercado Pago (Checkout Pro)
- **Notificaciones push:** Firebase Cloud Messaging
- **Frontend:** Django Templates + HTML/CSS/JS vanilla
- **Producción:** Gunicorn + WhiteNoise

---

## Estructura del proyecto

```
credisystem/
├── credisystem/          # settings, urls raíz, wsgi/asgi
├── usuarios/              # autenticación: Usuario, registro, login, JWT, bloqueo, recuperación
├── creditos/               # créditos, pagos, solicitudes, simulaciones, notificaciones
│   └── management/commands/enviar_recordatorios_pago.py
├── frontend/               # templates + static (HTML/CSS/JS)
├── manage.py
├── requirements.txt
├── Procfile                 # despliegue (Render/Railway/Heroku)
├── .env.example
└── .gitignore
```

---

## Puesta en marcha (desarrollo local)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # completar al menos DJANGO_SECRET_KEY

python manage.py migrate
python manage.py createsuperuser # opcional, para entrar a /admin/
python manage.py runserver
```

La app queda disponible en `http://127.0.0.1:8000/`. Sin `DB_ENGINE=mysql` en el `.env`,
usa SQLite automáticamente — no hace falta tener MySQL instalado para desarrollar.

### Correr los tests

```bash
python manage.py test
```

110 tests cubren los módulos funcionales, los flujos integrales, el login web administrativo y la validación BCRA.
La versión actual incluye las correcciones de menú y login y está consolidada en una sola carpeta. Consultá CHECKLIST_CREDISYSTEM.md y LEEME_CORRECCIONES_2026-09-28.md.

### Generar recordatorios de pago (CU7)

Pensado para correr una vez al día vía cron o Celery beat:

```bash
python manage.py enviar_recordatorios_pago
```

---

## Variables de entorno relevantes

Ver `.env.example` para el listado completo. Las más importantes:

| Variable | Uso |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django (generar una larga y random) |
| `DJANGO_DEBUG` | `False` en producción |
| `DB_ENGINE=mysql` | Activa MySQL (si no está seteada, usa SQLite) |
| `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT` | Credenciales de MySQL |
| `MERCADOPAGO_ACCESS_TOKEN` | Access token de la cuenta de Mercado Pago |
| `MERCADOPAGO_WEBHOOK_SECRET` | Secret para validar la firma del webhook |
| `BACKEND_PUBLIC_URL` | URL pública del backend (Mercado Pago necesita poder pegarle al webhook) |
| `FCM_CREDENTIALS_PATH` | Ruta al `credentials.json` de Firebase (opcional) |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP real (si no se configura, los emails se imprimen en consola) |

---

## Endpoints de la API

Base: `/api/`

### Autenticación (`/api/auth/`)

| Método | Endpoint | CU | Descripción |
|---|---|---|---|
| POST | `registro/` | CU1 | Crea la cuenta (inactiva) y envía código |
| POST | `verificar/` | CU1 | Activa la cuenta con el código |
| POST | `verificar/reenviar/` | CU1 | Reenvía el código de verificación |
| POST | `login/` | CU2, CU10 | Login; bloquea tras 5 intentos fallidos en 15 min |
| POST | `token/refresh/` | — | Renueva el access token |
| POST | `logout/` | — | Invalida el refresh token |
| POST | `password/recuperar/` | CU9 | Pide el email, envía código |
| POST | `password/confirmar/` | CU9 | Valida código y define nueva contraseña |
| GET/PATCH | `perfil/` | — | Ver/editar el perfil propio |

### Créditos (`/api/creditos/`)

| Método | Endpoint | CU | Descripción |
|---|---|---|---|
| GET | `` | — | Lista los créditos del usuario |
| GET | `<id_credito>/` | CU3 | Saldo, resumen y pagos de un crédito |
| POST | `simular/` | CU8 | Calcula la cuota estimada |
| POST | `solicitudes/` | CU4 | Solicita un crédito (con comprobante); precalifica automático |
| GET | `solicitudes/` | — | Historial de solicitudes |
| GET | `solicitudes/<id>/` | — | Detalle de una solicitud |
| POST | `<id_credito>/pagos/` | CU5 | Inicia un pago (Mercado Pago) |
| GET | `pagos/<id_pago>/` | CU5 | Estado de un pago |

### Transacciones y notificaciones

| Método | Endpoint | CU | Descripción |
|---|---|---|---|
| GET | `/api/transacciones/?tipo=&fecha_desde=&fecha_hasta=` | CU6 | Historial filtrable |
| GET | `/api/notificaciones/?leida=` | CU7 | Notificaciones del usuario |
| PATCH | `/api/notificaciones/<id>/leer/` | CU7 | Marca una como leída |
| POST | `/api/notificaciones/leer-todas/` | CU7 | Marca todas como leídas |
| POST | `/api/pagos/webhook/mercadopago/` | CU5 | Webhook de confirmación de Mercado Pago |

### Frontend (páginas)

`/login/` · `/registro/` · `/verificar/` · `/recuperar-password/` · `/confirmar-recuperacion/`
· `/dashboard/` · `/simular/` · `/nuevo-credito/` · `/pagos/` · `/historial/` · `/notificaciones/`

---

## Checklist de seguridad aplicado

| Ítem | Cómo está resuelto |
|---|---|
| Ocultar claves API / eliminar secretos de Git | Todo sale de `.env` (nunca hardcodeado); `.gitignore` excluye `.env` |
| Clave pública de DB | Usuario de MySQL con permisos acotados (nunca root), configurable por env |
| Cifrar datos sensibles | Contraseñas hasheadas (PBKDF2 de Django); JWT firmado; HTTPS forzado en producción |
| Autenticación del servidor | JWT en cada endpoint (`IsAuthenticated` por default); nunca se confía en datos del cliente |
| Restringir acceso a registros | Todo queryset se filtra por `request.user`; acceso cruzado devuelve 404, no 403 |
| Bloquear manipulación de campos | Serializers explícitos, nunca `fields = '__all__'` con inputs del usuario |
| Proteger cookies de sesión | `SESSION_COOKIE_SECURE`, `HTTPONLY` activados en producción |
| Hashear contraseñas | `AbstractBaseUser` + `set_password()` (nunca texto plano) |
| Limitar intentos de login | 5 intentos → bloqueo de 15 min (`IntentoAcceso`/`BloqueoCuenta`, CU10) |
| Protección anti-bots | Throttling de DRF (`anon`, `login` scopes) |
| Monitorizar consultas de DB | `IntentoAcceso` registra cada intento de login (éxito/fallo, IP, motivo) |
| Validar todas las entradas | Serializers de DRF en cada endpoint; validación de firma HMAC en el webhook |
| Escapar contenido de usuario | Autoescape de Django templates (activo por default) |
| Restringir subida de archivos | Extensión + tamaño + firma binaria real del archivo (CU4) |
| Limitar respuestas de API | Paginación por default (20 ítems) |
| Cabeceras de seguridad | `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`, HSTS (producción) |
| Forzar HTTPS | `SECURE_SSL_REDIRECT = True` cuando `DEBUG=False` |
| Escanear dependencias | Ver sección "Antes de entregar" más abajo |

---

## Despliegue (Render, Railway o similar)

La guía operativa completa está en `DEPLOY.md`. Antes de publicar ejecuta también
`python manage.py check_production` con las variables productivas cargadas.

1. **Base de datos MySQL**: crear una instancia gratuita (Railway, Aiven, PlanetScale, etc.)
   y anotar host/usuario/password/db name.
2. **Variables de entorno** en la plataforma de hosting: todas las de `.env.example`, con
   `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=<tu-dominio>.onrender.com`,
   `BACKEND_PUBLIC_URL=https://<tu-dominio>.onrender.com`, `DB_ENGINE=mysql` + credenciales.
3. **Build command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
4. **Start command**: ya definido en `Procfile` (`gunicorn credisystem.wsgi`).
5. **Mercado Pago**: configurar el `MERCADOPAGO_ACCESS_TOKEN` de la cuenta de prueba
   (sandbox) primero. En el panel de Mercado Pago, la `notification_url` se arma sola con
   `BACKEND_PUBLIC_URL` — solo hay que verificar que el dominio sea accesible públicamente
   (no funciona con `localhost`).
6. **Firebase (opcional)**: subir el `credentials.json` como secret file de la plataforma y
   apuntar `FCM_CREDENTIALS_PATH` a esa ruta. Si se omite, las notificaciones push no se
   envían pero el resto del sistema funciona igual (quedan guardadas en la base).

## Antes de entregar

- [x] Escaneado con `pip-audit`: se detectó y corrigió una vulnerabilidad en Pillow (11.0.0 → 12.3.0). Django, DRF, Mercado Pago SDK, Firebase Admin, gunicorn y whitenoise no presentan CVEs conocidos a la fecha.
- [ ] Probar el flujo de pago real contra el sandbox de Mercado Pago (acá solo se testeó mockeado)
- [ ] Generar un `DJANGO_SECRET_KEY` nuevo para producción (no reusar el de desarrollo)
- [ ] Confirmar que `.env` nunca quedó trackeado por Git (`git log --all --full-history -- .env`)
- [ ] Correr `python manage.py test` una última vez
- [ ] Repetir `pip-audit -r requirements.txt` antes de la entrega final (las vulnerabilidades se descubren todo el tiempo)

### Etapa #36 — Estado de cuenta
Se agregó `/api/creditos/estado-cuenta/` y la pantalla `/estado-cuenta/` con saldo consolidado, créditos activos, cuotas por estado, próximo vencimiento y pagos aprobados. Esta etapa no requiere una migración nueva. Validar localmente con `python manage.py check` y `python manage.py test` (41 tests esperados).
