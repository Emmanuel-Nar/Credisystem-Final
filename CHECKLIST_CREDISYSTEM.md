# Checklist maestra — CREDISYSTEM

Actualizada: 20/09/2026

## Implementado
- [x] Frontend integrado con Django templates, CSS, JS, imágenes y logo.
- [x] Registro, inicio de sesión, verificación y recuperación de contraseña.
- [x] Panel administrativo de Django operativo.
- [x] Simulación y solicitud de créditos.
- [x] Carga y validación de comprobantes.
- [x] Precalificación automática de solicitudes.
- [x] Créditos otorgados y detalle de crédito.
- [x] Notificaciones dentro del sistema.
- [x] Integración base con Mercado Pago y webhook.
- [x] Integración de WhatsApp preparada a nivel código/configuración.
- [x] Historial de solicitudes del cliente y pantalla de detalle.
- [x] Motivo de rechazo visible para el cliente.
- [x] Acceso a "Mis solicitudes" desde dashboard y menús desktop/mobile.
- [x] Corregida colisión de URL de notificaciones API/frontend.
- [x] Pruebas automáticas verificadas localmente: 14/14 OK antes de esta etapa.
- [x] Gestión administrativa de solicitudes desde Django Admin.
- [x] Motivo de rechazo obligatorio al rechazar desde administración.
- [x] Notificación automática al cliente ante cambios administrativos de estado.
- [x] Generación automática del crédito al aprobar manualmente.
- [x] Prevención de créditos/desembolsos duplicados mediante relación única solicitud → crédito.
- [x] Motivo de rechazo se limpia al volver una solicitud a revisión/aprobada.

## Pendiente de prueba
- [ ] Ejecutar `python manage.py migrate` por la nueva relación solicitud → crédito.
- [ ] Ejecutar `python manage.py check` y `python manage.py test` (ahora deben encontrarse 17 tests).
- [ ] Probar en Django Admin: revisión → aprobada y comprobar crédito/notificación.
- [ ] Probar en Django Admin: revisión → rechazada y comprobar obligatoriedad del motivo/notificación.
- [ ] Envío real de WhatsApp con número definitivo y credenciales productivas.
- [ ] Flujo completo de Mercado Pago con credenciales y webhook públicos/productivos.

## Siguiente paso
- [ ] Historial/auditoría de cambios administrativos: quién cambió una solicitud, estado anterior/nuevo, fecha y motivo.

## Después
- [ ] Mejoras de seguridad y permisos del panel.
- [ ] Revisión final responsive y UX.
- [ ] Pruebas integrales del flujo registro → solicitud → aprobación/rechazo → crédito → pago.
- [ ] Preparación para despliegue/producción.

## Gestión administrativa validada — 20/09/2026
- [x] Aprobar/rechazar solicitudes desde Django Admin.
- [x] Motivo de rechazo obligatorio.
- [x] Generación de crédito al aprobar y prevención de duplicados.
- [x] Notificación al cliente por cambio de estado.
- [x] Validado localmente por el usuario: 17/17 tests OK.

## Auditoría administrativa — etapa actual
- [x] Modelo de historial por solicitud.
- [x] Registro de administrador responsable.
- [x] Registro de estado anterior y estado nuevo.
- [x] Fecha/hora automática del cambio.
- [x] Motivo de rechazo guardado como observación cuando corresponde.
- [x] Historial visible y de solo lectura dentro de la solicitud en Django Admin.
- [x] Migración `0005_historialsolicitud` incluida.
- [x] Tres pruebas automáticas nuevas agregadas (total esperado: 20 tests).
- [x] Validado localmente por el usuario: 20/20 tests OK.

## Seguridad y permisos del panel administrativo — etapa actual
- [x] Clientes normales sin acceso al panel `/admin/`.
- [x] Operadores staff necesitan el permiso `change_solicitudcredito` para procesar solicitudes.
- [x] Eliminación de solicitudes restringida a superusuarios para preservar trazabilidad.
- [x] Campos financieros/origen de la solicitud continúan protegidos como solo lectura.
- [x] Cuatro pruebas automáticas de permisos agregadas (total esperado: 24 tests).
- [x] Validado localmente por el usuario: 24/24 tests OK.

## Perfil y actualización segura de datos del cliente — etapa actual
- [x] Consulta autenticada del perfil propio.
- [x] Edición limitada a nombre, apellido, teléfono y dirección.
- [x] Email, documento, estado, biometría y datos push protegidos como solo lectura.
- [x] Normalización y validación del teléfono.
- [x] Nombre/apellido no admiten valores vacíos o demasiado cortos.
- [x] Documento visible pero no editable en la interfaz.
- [x] Dirección incorporada a la pantalla de perfil.
- [x] Cinco pruebas automáticas agregadas (total esperado: 29 tests).
- [x] Validado localmente por el usuario: 29/29 tests OK.

## Próximo paso
- [ ] Gestión de cuotas, vencimientos y estado de cuenta.

## Corrección de validación — Perfil seguro
- [x] Separados los nombres de ruta API (`perfil`) y frontend (`perfil_web`) para evitar que `reverse("perfil")` resuelva la vista HTML.
- [x] Enlaces del frontend actualizados a `perfil_web`.
- [ ] Ejecutar `python manage.py check` y `python manage.py test` en el entorno local; objetivo: 29/29 tests OK.

## Cuotas y vencimientos — etapa #34
- [x] Entidad `Cuota` vinculada al crédito.
- [x] Número de cuota, importe, fecha de vencimiento y estado individual.
- [x] Estados: pendiente, pagada y vencida.
- [x] Generación automática del cronograma al aprobar/otorgar un crédito.
- [x] Prevención de duplicación del cronograma.
- [x] Vencimientos mensuales respetando el calendario.
- [x] Detalle del crédito expone cuotas reales, cantidad pendiente y próximo vencimiento.
- [x] Cuotas visibles en Django Admin con campos financieros protegidos.
- [x] Migración `0006_cuota` incluida.
- [x] Cuatro tests automáticos nuevos (total esperado: 33 tests).
- [ ] Ejecutar `python manage.py migrate`, `python manage.py check` y `python manage.py test`; objetivo: 33/33 OK.

## Siguiente paso
- [ ] #35 Registro de pagos: imputar pagos confirmados a cuotas y actualizar saldo/estado del crédito.

## Registro de pagos — etapa #35
- [x] Pago confirmado se procesa de forma transaccional e idempotente.
- [x] Imputación automática a las cuotas más antiguas pendientes/vencidas.
- [x] Soporte de pagos parciales mediante `monto_pagado` por cuota.
- [x] Una cuota pasa a `PAGADA` únicamente cuando completa su importe.
- [x] Un pago puede cubrir más de una cuota y conserva el detalle de cada imputación.
- [x] Saldo y estado del crédito se actualizan al confirmar el pago.
- [x] Historial de imputaciones visible desde la API de pagos y Django Admin.
- [x] Prevención de doble imputación/doble descuento ante webhooks repetidos.
- [x] Migración `0007_registro_pagos_cuotas` incluida.
- [x] Cuatro tests nuevos agregados (total esperado: 37 tests).
- [ ] Ejecutar `python manage.py migrate`, `python manage.py check` y `python manage.py test`; objetivo: 37/37 OK.

## Siguiente paso
- [ ] #36 Estado de cuenta y saldo pendiente: resumen financiero consolidado para el cliente.

## Estado de cuenta y saldo pendiente — etapa #36
- [x] Endpoint autenticado con resumen financiero consolidado del cliente.
- [x] Saldo total pendiente y cantidad de créditos activos.
- [x] Resumen de cuotas pagadas, pendientes y vencidas.
- [x] Próximo vencimiento calculado desde las cuotas reales.
- [x] Total pagado calculado únicamente con pagos aprobados.
- [x] Historial de pagos confirmados incluido en el estado de cuenta.
- [x] Detalle de créditos propios incluido sin exponer información de otros usuarios.
- [x] Nueva pantalla `Estado de cuenta` accesible desde dashboard y menú de usuario.
- [x] Cuatro tests automáticos nuevos (total esperado: 41 tests).
- [ ] Ejecutar `python manage.py check` y `python manage.py test`; objetivo: 41/41 OK.

## Siguiente paso
- [ ] #37 Comprobantes: consulta/descarga segura de comprobantes de pagos confirmados.

## Comprobantes de pago — etapa #37
- [x] Comprobante disponible únicamente para pagos aprobados.
- [x] Acceso restringido al titular del crédito; comprobantes ajenos devuelven 404.
- [x] Comprobante imprimible con pago, crédito, cliente, fecha, importe, medio y referencia.
- [x] Acción `Imprimir / Guardar PDF` desde el navegador sin almacenar datos sensibles.
- [x] Acceso al comprobante desde el historial de pagos del Estado de cuenta.
- [x] Encabezados privados/no-store para reducir cacheo de información financiera.
- [x] Cuatro tests automáticos nuevos (total esperado: 45 tests).
- [ ] Ejecutar `python manage.py check` y `python manage.py test`; objetivo: 45/45 OK.

## Siguiente paso
- [ ] #38 Recordatorios de vencimiento: automatizar avisos previos y de mora evitando duplicados.

## Recordatorios de vencimiento — etapa #38
- [x] Recordatorios basados en las cuotas reales del crédito.
- [x] Aviso automático 3 días antes del vencimiento.
- [x] Detección de cuotas vencidas y cambio automático a estado `VENCIDA`.
- [x] Crédito pasa a `EN_MORA` cuando se detecta una cuota vencida.
- [x] No se generan avisos para cuotas ya pagadas.
- [x] Prevención de recordatorios duplicados para la misma cuota durante el mismo día.
- [x] Compatibilidad con créditos antiguos que todavía no tengan cronograma de cuotas.
- [x] Reutiliza el sistema central de notificaciones/push; queda preparado para sumar WhatsApp cuando se habilite el número.
- [x] Comando ejecutable con `python manage.py enviar_recordatorios_pago`, apto para programar diariamente en producción.
- [x] Cuatro tests nuevos agregados (total esperado: 49 tests).
- [x] Ejecutado y validado: `python manage.py check` y `python manage.py test` — 49/49 OK.

## Siguiente paso
- [ ] #39 Seguridad para producción.

## Seguridad para producción — etapa #39
- [x] `SECRET_KEY`, `DEBUG`, hosts y orígenes CSRF configurables por entorno.
- [x] La configuración `.env` se lee realmente mediante `python-decouple`.
- [x] Producción rechaza una `SECRET_KEY` insegura o demasiado corta.
- [x] HTTPS, HSTS, cookies Secure/HttpOnly/SameSite y protección de framing activadas con `DEBUG=False`.
- [x] Soporte seguro para proxy HTTPS mediante `SECURE_PROXY_SSL_HEADER`.
- [x] JWT con access corto, refresh rotativo y blacklist tras rotación.
- [x] Throttling global y límite específico de login conservados.
- [x] Health check deja de exponer el texto interno de excepciones de base de datos.
- [x] `.env.example` ampliado sin credenciales reales y `.env` permanece ignorado por Git.
- [x] CORS no se abre globalmente: el frontend actual es same-origin.
- [x] `python manage.py check` y `python manage.py test` validados — 49/49 OK. Configuración de producción y protecciones verificadas; `check --deploy` requiere variables de producción reales.

## Siguiente paso
- [x] #40 Validaciones y manejo global de errores.

## Validaciones y manejo global de errores — etapa #40
- [x] Páginas controladas para errores 400, 403, 404 y 500.
- [x] Respuestas JSON seguras para errores bajo `/api/`.
- [x] Los mensajes al cliente no exponen excepciones ni detalles internos.
- [x] Handler global DRF conserva errores esperados de validación/autenticación y controla excepciones inesperadas.
- [x] Registro interno de excepciones API inesperadas mediante logging.
- [x] Cinco tests nuevos agregados (total esperado: 54 tests).
- [x] `python manage.py check` y `python manage.py test` validados — 54/54 OK.

## Siguiente paso
- [x] #41 Tests integrales finales.

## Tests integrales finales — etapa #41
- [x] Flujo integral aprobación → crédito → cuotas → pago → estado de cuenta cubierto automáticamente.
- [x] Flujo de rechazo con motivo validado: no genera crédito y sí notifica al cliente.
- [x] Reprocesamiento de aprobación validado como idempotente: no duplica crédito, cuotas ni desembolso.
- [x] Recordatorio de mora integrado: cuota vencida, crédito en mora y aviso sin duplicados.
- [x] Aislamiento entre clientes validado en detalle de crédito y estado de cuenta.
- [x] Cinco tests integrales nuevos agregados (total esperado: 59 tests).
- [x] `python manage.py check` y `python manage.py test` validados — 59/59 OK.

## Siguiente paso
- [x] #42 Revisión responsive móvil.

## Revisión responsive móvil — etapa #42
- [x] Header y navegación móvil reforzados para 980/720/480 px.
- [x] Dashboard principal pasa de dos columnas a una columna en tablet/móvil.
- [x] Resumen de crédito adapta sus dos columnas a una en móvil.
- [x] Tablas extensas conservan todos los datos mediante desplazamiento horizontal táctil.
- [x] Tarjetas de crédito, paneles, botones, pestañas, notificaciones y footer adaptados a pantallas pequeñas.
- [x] Formularios, OTP y tipografía ajustados para evitar desbordes en teléfonos angostos.
- [x] Cambios limitados al frontend; sin migraciones ni cambios de backend.
- [x] Ejecutado y validado: `python manage.py check` y `python manage.py test` — 59/59 OK.

## Siguiente paso
- [x] #43 Revisión final UI/UX.


## Revisión final UI/UX — etapa #43
- [x] Jerarquía visual y superficies unificadas en paneles, tarjetas y encabezados.
- [x] Botones, inputs, textareas, placeholders y estados activos/focus normalizados.
- [x] Feedback visual de alertas, badges, estados vacíos y tablas refinado.
- [x] Navegación de usuario y menú móvil mejorados con estados ARIA y soporte de teclado/Escape.
- [x] Focus visible reforzado para navegación por teclado.
- [x] Soporte `prefers-reduced-motion` agregado para usuarios que reducen animaciones.
- [x] Ajustes finales de legibilidad y espaciado en móvil sin alterar backend ni base de datos.
- [ ] Ejecutar `python manage.py check` y `python manage.py test`; objetivo: 59/59 OK.
- [ ] Revisión visual final en desktop y móvil (390/430 px) antes del deploy.

## Siguiente paso
- [ ] #44 Preparación para producción / deploy.

## Preparación para producción / deploy — etapa #44
- [x] Gunicorn y WhiteNoise incluidos y configurados para producción.
- [x] `Procfile` endurecido con workers, timeout y logs a stdout/stderr.
- [x] Variables de producción documentadas sin incluir secretos reales.
- [x] Guía `DEPLOY.md` agregada con build, migraciones, arranque, health check y rollback.
- [x] Comando `python manage.py check_production` agregado para detectar configuración productiva incompleta.
- [x] `check_production` exige DEBUG=False, URL pública HTTPS y orígenes CSRF; además advierte sobre SQLite, SMTP y Mercado Pago incompletos.
- [x] Estrategia de estáticos documentada: `collectstatic` + WhiteNoise.
- [x] Persistencia de archivos `MEDIA` documentada: requiere volumen persistente u object storage en producción.
- [x] Recordatorios de vencimiento documentados como tarea programada diaria.
- [x] Health check `/api/health/` documentado para la plataforma de hosting.
- [x] README corregido a Django 5.2 LTS y estado actual de 59 tests.
- [ ] Ejecutar localmente `python manage.py check` y `python manage.py test`; objetivo: 59/59 OK.
- [ ] Ejecutar `python manage.py check --deploy` y `python manage.py check_production` cuando exista dominio/hosting y variables productivas reales.
- [ ] Configurar almacenamiento persistente de `MEDIA` antes de aceptar comprobantes reales en producción.

## Siguiente paso
- [ ] #45 Manual completo de CREDISYSTEM.
