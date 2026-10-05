# CREDISYSTEM — Validación privada de solicitudes con BCRA

Actualización: 02/10/2026. Base: nuestra versión consolidada del 28/09/2026.

## Cómo actualizar en Windows

1. Cerrá el servidor. Guardá una copia de tu proyecto actual y de su base de datos.
2. Extraé este ZIP en una carpeta nueva. Dentro hay una sola carpeta `crediFINAL` con `manage.py`.
3. Si estuviste trabajando después de la última entrega, copiá a esta carpeta tu `db.sqlite3` más reciente, tu configuración `.env` y tu carpeta `media`. No reemplaces tus datos recientes con la base incluida en el ZIP.
4. Abrí una terminal en la carpeta que contiene `manage.py`. Creá y activá el entorno si todavía no lo tenés:

```bat
python -m venv .venv
.venv\Scripts\activate
```

5. Instalá las dependencias y aplicá la migración antes de abrir la aplicación:

```bat
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

En un servidor publicado también ejecutá `python manage.py collectstatic --noinput` y reiniciá el servicio. En MySQL, respaldá la base del servidor antes de migrar; no copies SQLite sobre ella.

La base incluida conserva los datos de la entrega anterior. La nueva migración agrega campos e índice único; no elimina usuarios, créditos, pagos ni solicitudes. Se verificó su aplicación sobre una copia y se conservaron todos los registros anteriores.

## Flujo del cliente

1. Inicia sesión y abre **Solicitar crédito**.
2. Completa monto, plazo, ingresos y su CUIL/CUIT; adjunta un comprobante y autoriza la consulta.
3. Ve una animación con **“Aguardá unos momentos. Estamos verificando tu solicitud.”** durante el procesamiento real.
4. Recibe un mensaje de aprobación, revisión o rechazo. El mensaje permanece visible y ofrece el acceso a sus créditos o solicitudes; no hay redirección automática que lo oculte.

El cliente no recibe el informe BCRA, las entidades, los importes de deudas ni un puntaje. No existe una pantalla ni un endpoint público de consulta al BCRA. Las respuestas de creación, listado, detalle y notificaciones tampoco incluyen ese informe.

## Criterio inicial de decisión

Es una política interna de este proyecto; el BCRA informa datos y no aprueba créditos de CREDISYSTEM.

| Condición | Resultado |
|---|---|
| Monto/plazo fuera del rango o cuota superior al 30% de los ingresos, conforme a las reglas existentes | Rechazada por las reglas locales; no se consulta al BCRA |
| CUIL/CUIT inválido, ajeno al documento personal de la cuenta, falta de autorización o archivo inválido | Se pide corregir el formulario; no se crea una solicitud |
| Reglas locales cumplidas, identificación personal coincidente, último período válido, todas las entidades en situación 1, sin días de atraso ni observaciones | Aprobada; se genera el crédito y sus cuotas |
| Situaciones distintas de 1, refinanciaciones, recategorización, observaciones jurídicas, información en revisión o judicializada, o atrasos | En revisión administrativa; no se genera crédito automáticamente |
| BCRA sin registros, datos incompletos/inconsistentes, período futuro o de más de 3 meses, error de conexión, certificado, timeout o límite de consultas | En revisión administrativa; no se fabrica un resultado |
| CUIT de una persona jurídica | En revisión para verificar representación y titularidad antes del otorgamiento |

Se comprueban formato, prefijo y dígito verificador del CUIL/CUIT. La coincidencia con el DNI declarado es una comprobación de consistencia, no una verificación documental de identidad. Las solicitudes anteriores no se reevalúan ni cambian de estado con la migración.

No se incorporó el score arbitrario de 300 a 850 del ZIP comparado: la decisión usa las reglas explícitas de esta tabla y los datos reales disponibles. El importe de deuda del BCRA se convierte de miles de pesos a pesos con `Decimal` para el informe interno; no se confunde deuda total con cuota mensual.

## Panel del superusuario

Ingresá con el superusuario desde el login habitual y abrí **Solicitudes de crédito**. Dentro de cada solicitud nueva se muestran CUIL/CUIT, autorización, fecha de consulta, estado técnico e informe de uso interno. Solo el superusuario ve esos campos; una cuenta staff con permiso de gestionar solicitudes sigue sin ver el informe BCRA.

Las solicitudes pendientes se resuelven mediante la gestión administrativa existente. El cambio de estado queda en su historial y notifica al cliente. La migración no agrega un reintento automático de consultas: para una solicitud en revisión, el administrador debe verificar la información antes de decidir. No escribir datos del informe privado en el campo **motivo de rechazo**, porque ese motivo sí se muestra al cliente.

## Correcciones incluidas

- Conexión HTTPS con verificación de certificados y límites de espera; no se silencian advertencias SSL.
- Sin deudas ficticias, aprobación de respaldo ni modo de demostración dentro del flujo real.
- Validaciones en el servidor, aunque se evadan las del navegador.
- Informe privado excluido de los serializers y restringido en el panel.
- Identificador de envío y restricción única por usuario para que un reintento no genere otro crédito. El navegador conserva ese identificador si no puede confirmar la respuesta.
- Creación de solicitud, transacciones y crédito dentro de una transacción. Si falla, se revierte y se elimina el archivo recién subido.
- Configurado el almacenamiento `default` de Django, que faltaba y bloqueaba la subida del comprobante.
- Conservados el menú hamburguesa, el acceso del superusuario, las validaciones de redirección y las 78 pruebas anteriores.

## Configuración y archivos principales

- `creditos/bcra.py`: conexión, validación de respuesta y criterio de revisión/aprobación.
- `creditos/serializers.py`: datos obligatorios, autorización, CUIL/CUIT y comprobante.
- `creditos/views.py`: integración en la solicitud y protección ante envíos repetidos.
- `creditos/models.py` y migración `0009_evaluacion_bcra_privada.py`: persistencia interna y campos para solicitudes anteriores.
- `creditos/admin.py`: acceso restringido al informe.
- `frontend/templates/solicitar_credito.html`, `static/js/solicitud_credito.js` y `static/css/solicitud_credito.css`: formulario, espera y mensajes.
- `creditos/test_bcra.py`: pruebas nuevas con respuestas externas controladas.

No se necesita una clave de API. El servidor necesita salida HTTPS a `api.bcra.gob.ar`. Si el hosting bloquea esa salida, las solicitudes aptas localmente quedarán en revisión. La antigüedad máxima se configura mediante `BCRA_ANTIGUEDAD_MAXIMA_MESES` (por defecto, 3).

Referencia del contrato de la API: https://www.bcra.gob.ar/archivos/Catalogo/Content/files/pdf/central-deudores-v1.pdf

## Verificación de esta entrega

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check --dry-run`: sin cambios pendientes de generar.
- `python manage.py test`: **106 pruebas aprobadas**, incluidas 28 nuevas.
- Chromium en celular y escritorio: autorización obligatoria, animación durante la espera, aprobación, revisión por falla del servicio y revisión por observaciones, enlaces y ausencia de errores JavaScript.
- Migración sobre una copia de la base: todos los registros previos conservados.

Las respuestas del BCRA se controlaron en las pruebas; no se consultaron personas reales. Queda pendiente comprobar la conexión y una solicitud autorizada real desde tu instalación o hosting. Esta entrega no incorpora biometría ni modifica el funcionamiento de Mercado Pago.
