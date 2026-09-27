import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    """
    Inicializa la app de Firebase una sola vez (lazy). Si no hay
    credenciales configuradas (proyecto académico corriendo sin ese
    servicio armado todavía), devuelve None y el envío se degrada a un
    no-op silencioso en vez de romper el flujo principal.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not settings.FCM_CREDENTIALS_PATH:
        return None

    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate(settings.FCM_CREDENTIALS_PATH)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def enviar_push(usuario, titulo, mensaje):
    """
    Envía una notificación push al dispositivo del usuario (CU7).
    No lanza excepción si falla: una notificación push es un canal
    adicional, nunca debe tumbar la operación principal (pago,
    solicitud, etc.) si Firebase no responde.
    """
    if not usuario.notificaciones_push_activas or not usuario.push_token:
        return False

    app = _get_firebase_app()
    if app is None:
        logger.info("[push-noop] %s -> %s: %s", usuario.email, titulo, mensaje)
        return False

    try:
        from firebase_admin import messaging

        mensaje_fcm = messaging.Message(
            notification=messaging.Notification(title=titulo, body=mensaje),
            token=usuario.push_token,
        )
        messaging.send(mensaje_fcm, app=app)
        return True
    except Exception:
        logger.exception("Error enviando push a %s", usuario.email)
        return False
