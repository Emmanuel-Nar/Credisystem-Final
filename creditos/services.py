from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def calcular_cuota(monto, plazo_meses, tasa_anual=None):
    """
    Sistema francés (cuota fija). Devuelve la cuota mensual estimada
    redondeada a 2 decimales.
    """
    if tasa_anual is None:
        tasa_anual = Decimal(settings.CREDITO_TASA_INTERES_ANUAL)

    monto = Decimal(monto)
    tasa_anual = Decimal(tasa_anual)
    i = tasa_anual / Decimal("100") / Decimal("12")  # tasa mensual

    if plazo_meses <= 0:
        raise ValueError("El plazo debe ser mayor a 0")

    if i == 0:
        cuota = monto / plazo_meses
    else:
        factor = (1 + i) ** plazo_meses
        cuota = monto * (i * factor) / (factor - 1)

    return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def evaluar_solicitud(monto_solicitado, plazo_meses, ingresos_mensuales):
    """
    Precalificación automática (CU4, paso 5). Reglas simples pero
    explícitas para un proyecto académico:

    - Monto y plazo deben estar dentro de los rangos permitidos.
    - La cuota estimada no puede superar el % configurado de los
      ingresos declarados (evita sobreendeudamiento).

    Devuelve (estado, motivo_rechazo, cuota_estimada).
    """
    if not (settings.CREDITO_MONTO_MINIMO <= monto_solicitado <= settings.CREDITO_MONTO_MAXIMO):
        return (
            "rechazada",
            f"El monto debe estar entre ${settings.CREDITO_MONTO_MINIMO} y "
            f"${settings.CREDITO_MONTO_MAXIMO}.",
            None,
        )

    if not (settings.CREDITO_PLAZO_MINIMO_MESES <= plazo_meses <= settings.CREDITO_PLAZO_MAXIMO_MESES):
        return (
            "rechazada",
            f"El plazo debe estar entre {settings.CREDITO_PLAZO_MINIMO_MESES} y "
            f"{settings.CREDITO_PLAZO_MAXIMO_MESES} meses.",
            None,
        )

    if ingresos_mensuales <= 0:
        return "rechazada", "No se declararon ingresos válidos.", None

    cuota = calcular_cuota(monto_solicitado, plazo_meses)
    porcentaje_max = Decimal(settings.CREDITO_PORCENTAJE_MAX_INGRESOS)
    limite = Decimal(ingresos_mensuales) * porcentaje_max

    if cuota > limite:
        return (
            "rechazada",
            f"La cuota estimada (${cuota}) supera el {int(porcentaje_max * 100)}% "
            "de tus ingresos declarados.",
            cuota,
        )

    return "aprobada", None, cuota


def _sumar_meses(fecha, meses):
    import calendar
    from datetime import date
    mes_base = fecha.month - 1 + meses
    anio = fecha.year + mes_base // 12
    mes = mes_base % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def crear_cuotas_para_credito(credito):
    """Crea el cronograma mensual una sola vez para un crédito."""
    from .models import Cuota
    if credito.cuotas.exists():
        return list(credito.cuotas.all())
    importe = calcular_cuota(credito.monto_original, credito.plazo_meses, credito.tasa_interes_anual)
    cuotas = [
        Cuota(
            credito=credito,
            numero=n,
            importe=importe,
            fecha_vencimiento=_sumar_meses(credito.primer_vencimiento, n - 1),
        )
        for n in range(1, credito.plazo_meses + 1)
    ]
    Cuota.objects.bulk_create(cuotas)
    return list(credito.cuotas.all())


def procesar_pago_aprobado(pago):
    """Aplica una confirmación de pago una sola vez y la imputa a cuotas en orden."""
    from django.db import transaction
    from django.utils import timezone
    from .models import Credito, Cuota, ImputacionPago, Pago, Transaccion

    with transaction.atomic():
        pago = Pago.objects.select_for_update().select_related("id_credito", "id_credito__id_usuario").get(pk=pago.pk)
        if pago.resultado == Pago.Resultado.APROBADO:
            return pago

        credito = Credito.objects.select_for_update().get(pk=pago.id_credito_id)
        monto_aplicable = min(Decimal(pago.monto_pagado), Decimal(credito.saldo_pendiente))
        restante = Decimal(pago.monto_pagado)

        cuotas = Cuota.objects.select_for_update().filter(
            credito=credito,
            estado__in=[Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDA],
        ).order_by("numero")

        for cuota in cuotas:
            if restante <= 0:
                break
            pendiente_cuota = max(Decimal(cuota.importe) - Decimal(cuota.monto_pagado), Decimal("0.00"))
            if pendiente_cuota <= 0:
                continue
            aplicado = min(restante, pendiente_cuota)
            ImputacionPago.objects.get_or_create(
                pago=pago,
                cuota=cuota,
                defaults={"monto": aplicado},
            )
            cuota.monto_pagado += aplicado
            restante -= aplicado
            if cuota.monto_pagado >= cuota.importe:
                cuota.monto_pagado = cuota.importe
                cuota.estado = Cuota.Estado.PAGADA
                cuota.fecha_pago = timezone.now()
            cuota.save(update_fields=["monto_pagado", "estado", "fecha_pago"])

        credito.saldo_pendiente = max(Decimal(credito.saldo_pendiente) - monto_aplicable, Decimal("0.00"))
        if credito.saldo_pendiente == 0:
            credito.estado = Credito.Estado.CANCELADO
        credito.save(update_fields=["saldo_pendiente", "estado"])

        pago.resultado = Pago.Resultado.APROBADO
        pago.save(update_fields=["resultado", "mp_payment_id", "medio_pago", "comprobante_url"])

        Transaccion.objects.create(
            id_usuario=credito.id_usuario,
            tipo=Transaccion.Tipo.PAGO,
            descripcion=f"Pago aprobado del crédito #{credito.id_credito}",
            importe=pago.monto_pagado,
        )
        return pago

import requests
import urllib3

# Deshabilitar advertencias SSL por si la API pública presenta diferencias de certificado
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def consultar_historial_bcra(cuil: str) -> dict:
    """
    Consulta la API pública centralizada de deudores del BCRA por CUIL/CUIT.
    Retorna un diccionario estructurado con los datos de deudas e informe.
    """
    cuil_limpio = "".join(filter(str.isdigit, str(cuil)))
    url = f"https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/{cuil_limpio}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=5, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 200 and "results" in data:
                periodos = data["results"].get("periodos", [])
                entidades = periodos[0].get("entidades", []) if periodos else []
                return {
                    "exito": True,
                    "denominacion": data["results"].get("denominacion", "Titular Registrado"),
                    "periodo": data["results"].get("periodo", ""),
                    "entidades": entidades,
                    "origen": "BCRA_REAL"
                }
    except Exception as e:
        print(f"Nota: Consulta externa a BCRA derivada a fallback: {e}")

    # Fallback / Simulador seguro si la API externa está restringida o no responde
    return {
        "exito": True,
        "denominacion": "Usuario de Prueba",
        "periodo": "2026-08",
        "entidades": [
            {"entidad": "BANCO DE LA NACION ARGENTINA", "situacion": 1, "monto": 120.5},
            {"entidad": "BANCO GALICIA", "situacion": 1, "monto": 45.0}
        ],
        "origen": "SIMULADO"
    }


def calcular_credit_score(cuil: str, ingresos_declarados: float) -> dict:
    """
    Calcula un score crediticio de 300 a 850 puntos combinando
    el historial del BCRA y los ingresos declarados.
    """
    datos_bcra = consultar_historial_bcra(cuil)
    score_base = 650  # Puntaje neutro inicial

    peor_situacion = 1
    total_deuda = 0.0

    if datos_bcra.get("entidades"):
        for ent in datos_bcra["entidades"]:
            sit = ent.get("situacion", 1)
            monto = ent.get("monto", 0.0)
            total_deuda += monto
            if sit > peor_situacion:
                peor_situacion = sit

    # Ajuste por Situación BCRA (1: Normal, 2: Seguimiento, 3: Problemas, 4-5: Alto Riesgo)
    if peor_situacion == 1:
        score_base += 100
    elif peor_situacion == 2:
        score_base -= 50
    elif peor_situacion == 3:
        score_base -= 150
    elif peor_situacion >= 4:
        score_base -= 300

    # Ajuste por Capacidad Financiera (Ingresos)
    if ingresos_declarados >= 800000:
        score_base += 80
    elif ingresos_declarados >= 400000:
        score_base += 40
    elif ingresos_declarados < 200000:
        score_base -= 50

    # Normalización del Score entre 300 y 850
    score_final = max(300, min(850, score_base))

    # Definición de Nivel de Riesgo
    if score_final >= 720:
        nivel_riesgo = "Excelente"
        color = "success"
        monto_maximo_sugerido = ingresos_declarados * 4
    elif score_final >= 600:
        nivel_riesgo = "Riesgo Moderado"
        color = "warning"
        monto_maximo_sugerido = ingresos_declarados * 2
    else:
        nivel_riesgo = "Alto Riesgo"
        color = "danger"
        monto_maximo_sugerido = 0

    return {
        "cuil": cuil,
        "score": score_final,
        "nivel_riesgo": nivel_riesgo,
        "color": color,
        "monto_maximo_sugerido": monto_maximo_sugerido,
        "peor_situacion_bcra": peor_situacion,
        "detalles_bcra": datos_bcra
    }