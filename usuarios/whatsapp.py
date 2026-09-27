import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def normalizar_telefono_whatsapp(telefono):
    digitos = re.sub(r"\D", "", telefono or "")
    if digitos.startswith("00"):
        digitos = digitos[2:]

    if digitos.startswith("54"):
        nacional = digitos[2:]
        if nacional.startswith("9"):
            return "54" + nacional
        nacional = nacional.lstrip("0")
        nacional = re.sub(r"^(\d{2,4})15", r"\1", nacional)
        return "549" + nacional

    nacional = digitos.lstrip("0")
    nacional = re.sub(r"^(\d{2,4})15", r"\1", nacional)
    if len(nacional) == 10:
        return "549" + nacional

    return digitos


def enviar_codigo_whatsapp(telefono, codigo):
    token = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    template_name = settings.WHATSAPP_TEMPLATE_NAME
    api_version = settings.WHATSAPP_API_VERSION

    if not token or not phone_number_id or not template_name:
        logger.warning("WhatsApp no configurado: faltan variables de entorno.")
        return False

    destinatario = normalizar_telefono_whatsapp(telefono)
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"

    components = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": str(codigo)}],
        }
    ]
    if settings.WHATSAPP_TEMPLATE_OTP_BUTTON:
        components.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": str(codigo)}],
            }
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
            "components": components,
        },
    }

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        logger.error("WhatsApp API HTTP %s: %s", exc.code, detalle)
    except (URLError, TimeoutError) as exc:
        logger.error("No se pudo conectar con WhatsApp API: %s", exc)
    return False
