import hashlib
import hmac

import mercadopago
from django.conf import settings


def _sdk():
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        raise RuntimeError(
            "MERCADOPAGO_ACCESS_TOKEN no está configurado. Definilo en el .env."
        )
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def crear_preferencia_pago(pago, credito):
    """
    CU5: crea una preferencia de Checkout Pro en Mercado Pago para que
    el usuario complete el pago (tarjeta, efectivo o dinero en cuenta,
    todo elegido del lado de Mercado Pago). Devuelve el init_point
    (URL) al que hay que redirigir al usuario.
    """
    sdk = _sdk()

    request_data = {
        "items": [
            {
                "title": f"Pago crédito CREDISYSTEM #{credito.id_credito}",
                "quantity": 1,
                "unit_price": float(pago.monto_pagado),
                "currency_id": "ARS",
            }
        ],
        "external_reference": pago.external_reference,
        "notification_url": f"{settings.BACKEND_PUBLIC_URL}/api/pagos/webhook/mercadopago/",
        "back_urls": {
            "success": f"{settings.BACKEND_PUBLIC_URL}/pagos/exito/",
            "failure": f"{settings.BACKEND_PUBLIC_URL}/pagos/error/",
            "pending": f"{settings.BACKEND_PUBLIC_URL}/pagos/pendiente/",
        },
        "auto_return": "approved",
    }

    respuesta = sdk.preference().create(request_data)
    if respuesta["status"] not in (200, 201):
        raise RuntimeError(f"Error creando la preferencia en Mercado Pago: {respuesta}")

    preferencia = respuesta["response"]
    return preferencia["id"], preferencia["init_point"]


def obtener_pago_mp(payment_id):
    """Consulta el detalle de un pago en Mercado Pago por su ID."""
    sdk = _sdk()
    respuesta = sdk.payment().get(payment_id)
    if respuesta["status"] != 200:
        raise RuntimeError(f"No se pudo obtener el pago {payment_id} de Mercado Pago: {respuesta}")
    return respuesta["response"]


def validar_firma_webhook(request):
    """
    Valida el header x-signature que envía Mercado Pago, siguiendo su
    esquema de HMAC-SHA256, para asegurarnos de que la notificación
    realmente viene de Mercado Pago y no de un tercero simulando un
    pago aprobado. Si no hay webhook secret configurado (ej. en
    desarrollo local sin dominio público), se omite la validación.
    """
    if not settings.MERCADOPAGO_WEBHOOK_SECRET:
        return True

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    data_id = request.GET.get("data.id", "") or request.GET.get("id", "")

    partes = dict(p.split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts = partes.get("ts", "")
    firma_recibida = partes.get("v1", "")
    if not ts or not firma_recibida:
        return False

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    firma_calculada = hmac.new(
        settings.MERCADOPAGO_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(firma_calculada, firma_recibida)


MEDIO_PAGO_MP = {
    "credit_card": "credito",
    "debit_card": "debito",
    "ticket": "efectivo",
    "atm": "efectivo",
    "account_money": "billetera",
    "digital_wallet": "billetera",
}
