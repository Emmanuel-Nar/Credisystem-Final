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
