# Perfil con identidad protegida — 02/10/2026

## Qué cambió

Nombre y apellido ahora son de solo lectura. DNI y email ya estaban bloqueados y continúan así. La pantalla informa que las correcciones de identidad deben solicitarse a administración.

El cliente puede modificar teléfono y dirección, y cambiar la contraseña desde la pestaña Seguridad. El formulario solo envía teléfono y dirección. Si se intenta alterar nombre, apellido, documento o email por fuera de la pantalla, la API rechaza el cambio con estado 400; tampoco guarda otros campos de esa petición.

Los datos se siguen solicitando al crear una cuenta. Un administrador con los permisos correspondientes puede corregirlos desde Usuarios en el panel, luego de verificar la corrección solicitada. El perfil del cliente nunca habilita esa edición por tener una sesión iniciada.

## Cómo actualizar

1. Cerrá el servidor y respaldá el proyecto y la base de datos actuales.
2. Extraé el ZIP en una carpeta nueva. Conservá tu base más reciente, `.env` y `media`; no sustituyas tus datos actuales por una copia anterior.
3. Si ya instalaste la entrega BCRA, este ajuste de perfil no agrega dependencias ni migraciones. Reiniciá el servidor y recargá el perfil con Ctrl+F5.
4. Si todavía no instalaste la entrega BCRA, seguí primero `LEEME_BCRA_2026-10-02.md`, incluida la instalación de dependencias y `python manage.py migrate`.

## Pruebas

110 pruebas aprobadas, incluidas 4 nuevas de protección de identidad. Se comprobó en navegador móvil que los campos estén bloqueados, que teléfono y dirección se guarden, que una petición directa no altere la identidad y que la pestaña de contraseña siga disponible. No hay nuevas migraciones pendientes de generar.

Se conservaron los datos de la base incluida, la evaluación BCRA, su informe privado, la animación, el menú hamburguesa y el login del superusuario. La checklist maestra está actualizada.
