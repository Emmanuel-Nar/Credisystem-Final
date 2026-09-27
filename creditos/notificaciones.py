from .models import Notificacion
from .push_service import enviar_push

_TITULOS_POR_TIPO = {
    Notificacion.Tipo.VENCIMIENTO: "Recordatorio de pago",
    Notificacion.Tipo.PROMOCION: "Novedad de CREDISYSTEM",
    Notificacion.Tipo.ESTADO_SOLICITUD: "Estado de tu solicitud",
}


def notificar(usuario, tipo, mensaje):
    """
    Punto único para generar una notificación: la persiste (queda en el
    historial del usuario, CU7) y además intenta el envío push si el
    usuario lo tiene activado. El push es best-effort: si falla, la
    notificación igual queda guardada.
    """
    notificacion = Notificacion.objects.create(id_usuario=usuario, tipo=tipo, mensaje=mensaje)
    enviar_push(usuario, _TITULOS_POR_TIPO.get(tipo, "CREDISYSTEM"), mensaje)
    return notificacion
