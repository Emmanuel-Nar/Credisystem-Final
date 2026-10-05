"""Consulta privada al BCRA. Nunca fabrica datos ni desactiva TLS."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

BCRA_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas"
PREFIJOS_PERSONA = {"20", "23", "24", "27"}
PREFIJOS_EMPRESA = {"30", "33", "34"}
OBSERVACIONES = (
    "refinanciaciones", "recategorizacionOblig", "situacionJuridica",
    "irrecDisposicionTecnica", "enRevision", "procesoJud",
)


def normalizar_cuil_cuit(valor):
    valor = str(valor).strip()
    if not re.fullmatch(r"[0-9]{11}|[0-9]{2}-[0-9]{8}-[0-9]", valor):
        raise ValidationError("Ingresá un CUIL/CUIT de 11 dígitos, con o sin guiones.")
    numero = valor.replace("-", "")
    suma = sum(int(d) * p for d, p in zip(numero[:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    verificador = (11 - suma % 11) % 11
    if numero[:2] not in PREFIJOS_PERSONA | PREFIJOS_EMPRESA or verificador == 10 or verificador != int(numero[-1]):
        raise ValidationError("El CUIL/CUIT ingresado no es válido. Revisá sus dígitos.")
    return numero


def _resultado(estado, motivo, **datos):
    return {"estado": estado, "motivo": motivo, **datos}


def consultar_bcra(cuil_cuit):
    numero = normalizar_cuil_cuit(cuil_cuit)
    try:
        respuesta = requests.get(
            f"{BCRA_URL}/{numero}",
            headers={"Accept": "application/json", "User-Agent": "Credisystem/1.0"},
            timeout=(3.05, 8), verify=True, allow_redirects=False,
        )
        datos = respuesta.json()
        if not isinstance(datos, dict):
            raise ValueError("Formato inesperado")
        if respuesta.status_code == 404 and datos.get("status") == 404:
            return _resultado("sin_datos", "sin_registros")
        if respuesta.status_code != 200 or datos.get("status") != 200:
            return _resultado("no_disponible", "servicio_no_disponible")
        resultado = datos["results"]
        if not isinstance(resultado, dict) or str(resultado["identificacion"]) != numero:
            raise ValueError("Identificación no coincidente")
        periodos = resultado["periodos"]
        if not isinstance(periodos, list):
            raise ValueError("Períodos inválidos")
        if not periodos:
            return _resultado("sin_datos", "sin_periodos")
        for periodo in periodos:
            if not re.fullmatch(r"[0-9]{6}", str(periodo["periodo"])):
                raise ValueError("Período inválido")
            datetime.strptime(periodo["periodo"], "%Y%m")
        ultimo = max(periodos, key=lambda p: p["periodo"])
        fecha_periodo = datetime.strptime(ultimo["periodo"], "%Y%m").date()
        hoy = timezone.localdate()
        antiguedad = (hoy.year - fecha_periodo.year) * 12 + hoy.month - fecha_periodo.month
        entidades = ultimo["entidades"]
        if not isinstance(entidades, list):
            raise ValueError("Entidades inválidas")
        if not entidades:
            return _resultado("sin_datos", "sin_entidades", periodo=ultimo["periodo"])
        informe = []
        for entidad in entidades:
            situacion = entidad["situacion"]
            if type(situacion) is not int or situacion not in range(1, 7):
                raise ValueError("Situación inválida")
            monto = Decimal(str(entidad["monto"]))
            if not monto.is_finite() or monto < 0:
                raise ValueError("Monto inválido")
            observaciones = {campo: entidad[campo] for campo in OBSERVACIONES}
            if any(type(v) is not bool for v in observaciones.values()):
                raise ValueError("Observaciones inválidas")
            dias = entidad["diasAtrasoPago"]
            if type(dias) is not int or dias < 0:
                raise ValueError("Atraso inválido")
            if not isinstance(entidad["entidad"], str):
                raise ValueError("Entidad inválida")
            informe.append({
                "entidad": entidad["entidad"][:250], "situacion": situacion,
                "monto_pesos": str(monto * 1000), "dias_atraso": dias,
                "observaciones": observaciones,
            })
        normal = all(e["situacion"] == 1 and e["dias_atraso"] == 0 and not any(e["observaciones"].values()) for e in informe)
        vigente = 0 <= antiguedad <= settings.BCRA_ANTIGUEDAD_MAXIMA_MESES
        return _resultado(
            "consultado", "normal" if normal and vigente else "requiere_revision",
            periodo=ultimo["periodo"], vigente=vigente,
            peor_situacion=max(e["situacion"] for e in informe), entidades=informe,
        )
    except requests.RequestException:
        return _resultado("no_disponible", "error_conexion")
    except (ValueError, KeyError, TypeError, InvalidOperation, OverflowError):
        return _resultado("no_disponible", "respuesta_invalida")


def evaluar_bcra(cuil_cuit):
    """Política interna conservadora; no es un score ni una aprobación del BCRA."""
    informe = consultar_bcra(cuil_cuit)
    if cuil_cuit[:2] in PREFIJOS_EMPRESA:
        informe["decision"] = "revision_titularidad_empresa"
        return "en_revision", informe
    if informe["estado"] == "consultado" and informe["motivo"] == "normal":
        informe["decision"] = "apta"
        return "aprobada", informe
    informe["decision"] = "revision_manual"
    return "en_revision", informe
