# Correcciones de menú y login — 28/09/2026

## Qué cambia

- El menú hamburguesa ahora se muestra al abrirlo. La causa era que `.mobile-menu` tenía `display: none` y la clase `.open` no lo cambiaba.
- Cierra con el botón, Escape, el fondo, un enlace o al pasar a escritorio. Mantiene el estado ARIA y evita enfocar sus enlaces mientras está cerrado.
- Desde `/login/`, ingresá el **email y contraseña de tu superusuario existente**: se abre `/admin/` sin volver a pedir las credenciales.
- Los clientes siguen entrando a su dashboard, al simulador pendiente o a una ruta interna válida. Una cuenta marcada solamente como staff no obtiene sesión administrativa mediante este formulario. Se conservan los permisos de staff ya definidos para el acceso directo tradicional de Django Admin.
- La ruta web exige CSRF y comprueba el rol en el servidor. No toma permisos enviados por el navegador. El login API original sigue disponible para JWT.
- El admin usa su sesión de Django y su botón de cerrar sesión. El formulario permite volver a ingresar aunque exista un token cliente anterior.
- Las URLs de CSS y JavaScript incluyen una versión nueva para renovar la caché.

## Cómo usar la versión consolidada

1. Detené `runserver` con Ctrl+C y guardá una copia de tu carpeta actual.
2. Descomprimí este ZIP en una ubicación nueva. Ahora contiene **una sola carpeta `crediFINAL`**, con un único `manage.py`. No lo descomprimas dentro de otra carpeta de proyecto existente.
3. Copiá tu `.env` y, si corresponde, tu carpeta `media` a la nueva carpeta. Si seguiste cargando datos después de enviarnos el ZIP, conservá tu `db.sqlite3` local más reciente. La base incluida aquí es la copia exterior original, sin modificaciones, que contenía todos los registros de la interior más algunos registros de acceso/tokens.
4. Abrí una terminal en la carpeta donde está `manage.py` y activá tu entorno virtual. Si necesitás uno nuevo en Windows, ejecutá:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

5. Ejecutá:

```bat
python manage.py check
python manage.py test
python manage.py runserver
```

6. Abrí `http://127.0.0.1:8000/login/` y recargá con Ctrl+F5. Ingresá con el email y contraseña del superusuario para entrar al admin; los clientes ingresan a su dashboard.
7. Si todavía no tenés un superusuario, crealo con `python manage.py createsuperuser`. Esta actualización no requiere nuevas migraciones ni resetear usuarios.

## Qué se conservó de cada copia

- El código compartido, incluida la última corrección del menú y login y la checklist completa.
- De la copia interior: la variante corregida de `estado_cuenta.html` y el archivo adicional `api_v3.js`. El sitio sigue usando `api_v2.js`, actualizado para el login administrativo.
- De la exterior: `db.sqlite3`, cuyos registros incluyen íntegramente los de la base interior.
- Una sola estructura de proyecto; ya no existe `crediFINAL/crediFINAL/`.

## Validación

- `python manage.py check`: sin problemas.
- `python manage.py test`: 78/78 OK (67 existentes y 11 nuevas).
- Las pruebas nuevas cubren acceso directo al admin, cuentas cliente/staff, manipulación de rol, contraseña incorrecta, cuenta inactiva, CSRF, origen externo, compatibilidad JWT, cambio de cuenta y cierre de sesión administrativo.
- La base de datos entregada se conserva tal como estaba en el ZIP original; las pruebas usan bases separadas.
- Prueba en Chromium: menú a 390/430/768/980 px, cierre y cambio a escritorio, login cliente, cierre de sesión, login superusuario, entrada y salida del admin; sin errores JavaScript.
