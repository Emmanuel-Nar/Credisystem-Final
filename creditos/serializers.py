import os
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from rest_framework import serializers

from .models import Credito, Cuota, ImputacionPago, Notificacion, Pago, Simulacion, SolicitudCredito, Transaccion


class ImputacionPagoSerializer(serializers.ModelSerializer):
    numero_cuota = serializers.IntegerField(source="cuota.numero", read_only=True)

    class Meta:
        model = ImputacionPago
        fields = ["id_imputacion", "cuota", "numero_cuota", "monto", "fecha_imputacion"]
        read_only_fields = fields


class PagoSerializer(serializers.ModelSerializer):
    imputaciones = ImputacionPagoSerializer(many=True, read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id_pago", "id_credito", "fecha_pago", "monto_pagado",
            "medio_pago", "resultado", "comprobante_url", "imputaciones",
        ]


class CuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cuota
        fields = ["id_cuota", "numero", "importe", "monto_pagado", "fecha_vencimiento", "estado", "fecha_pago"]
        read_only_fields = fields


class CreditoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credito
        fields = [
            "id_credito", "monto_original", "saldo_pendiente", "tasa_interes_anual",
            "plazo_meses", "fecha_otorgamiento", "primer_vencimiento", "estado",
        ]


class CreditoDetalleSerializer(serializers.ModelSerializer):
    """
    CU3: saldo actual + resumen (monto total, saldo pendiente, próximo
    vencimiento) + cuotas pendientes + historial de pagos del crédito.
    """

    cuotas_pendientes = serializers.SerializerMethodField()
    proximo_vencimiento = serializers.SerializerMethodField()
    historial_pagos = PagoSerializer(source="pagos", many=True, read_only=True)
    cuotas = CuotaSerializer(many=True, read_only=True)

    class Meta:
        model = Credito
        fields = [
            "id_credito", "monto_original", "saldo_pendiente", "tasa_interes_anual",
            "plazo_meses", "fecha_otorgamiento", "primer_vencimiento", "estado",
            "cuotas_pendientes", "proximo_vencimiento", "cuotas", "historial_pagos",
        ]

    def get_cuotas_pendientes(self, obj):
        return obj.cuotas.exclude(estado=Cuota.Estado.PAGADA).count()

    def get_proximo_vencimiento(self, obj):
        cuota = obj.cuotas.filter(estado__in=[Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDA]).order_by("fecha_vencimiento").first()
        return cuota.fecha_vencimiento if cuota else None


class EstadoCuentaSerializer(serializers.Serializer):
    saldo_total_pendiente = serializers.DecimalField(max_digits=14, decimal_places=2)
    creditos_activos = serializers.IntegerField()
    cuotas_pagadas = serializers.IntegerField()
    cuotas_pendientes = serializers.IntegerField()
    cuotas_vencidas = serializers.IntegerField()
    proximo_vencimiento = serializers.DateField(allow_null=True)
    total_pagado = serializers.DecimalField(max_digits=14, decimal_places=2)
    creditos = CreditoDetalleSerializer(many=True)
    pagos = PagoSerializer(many=True)


class TransaccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaccion
        fields = ["id_transaccion", "tipo", "fecha", "descripcion", "importe"]


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ["id_notificacion", "tipo", "mensaje", "fecha_envio", "leida"]
        read_only_fields = fields


class SimulacionInputSerializer(serializers.Serializer):
    """CU8: monto y plazo que el usuario quiere simular."""

    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    plazo_meses = serializers.IntegerField(min_value=1)

    def validate_monto(self, value):
        if not (settings.CREDITO_MONTO_MINIMO <= value <= settings.CREDITO_MONTO_MAXIMO):
            raise serializers.ValidationError(
                f"El monto debe estar entre ${settings.CREDITO_MONTO_MINIMO} y "
                f"${settings.CREDITO_MONTO_MAXIMO}."
            )
        return value

    def validate_plazo_meses(self, value):
        if not (settings.CREDITO_PLAZO_MINIMO_MESES <= value <= settings.CREDITO_PLAZO_MAXIMO_MESES):
            raise serializers.ValidationError(
                f"El plazo debe estar entre {settings.CREDITO_PLAZO_MINIMO_MESES} y "
                f"{settings.CREDITO_PLAZO_MAXIMO_MESES} meses."
            )
        return value


class SimulacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Simulacion
        fields = ["id_simulacion", "monto", "plazo_meses", "tasa_anual", "cuota_estim", "fecha"]


class SolicitudCreditoCrearSerializer(serializers.Serializer):
    """
    CU4: formulario de solicitud de crédito. Incluye validación de
    tipo/tamaño del comprobante subido (checklist: restringir subida
    de archivos).
    """

    monto_solicitado = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    plazo_meses = serializers.IntegerField(min_value=1)
    ingresos_mensuales = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    comprobante = serializers.FileField(required=True)

    def validate_comprobante(self, archivo):
        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in settings.SOLICITUD_EXTENSIONES_PERMITIDAS:
            raise serializers.ValidationError(
                f"Formato no permitido. Usá: {', '.join(settings.SOLICITUD_EXTENSIONES_PERMITIDAS)}"
            )

        max_bytes = settings.SOLICITUD_ARCHIVO_MAX_MB * 1024 * 1024
        if archivo.size > max_bytes:
            raise serializers.ValidationError(
                f"El archivo supera el tamaño máximo permitido ({settings.SOLICITUD_ARCHIVO_MAX_MB} MB)."
            )

        # Chequeo básico de contenido real (no solo la extensión declarada)
        firmas_validas = {
            b"%PDF": ".pdf",
            b"\xff\xd8\xff": ".jpg",
            b"\x89PNG": ".png",
        }
        cabecera = archivo.read(8)
        archivo.seek(0)
        if not any(cabecera.startswith(firma) for firma in firmas_validas):
            raise serializers.ValidationError("El contenido del archivo no coincide con un formato permitido.")

        return archivo


class SolicitudCreditoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudCredito
        fields = [
            "id_solicitud", "monto_solicitado", "plazo_meses", "ingresos_mensuales",
            "estado", "fecha_solicitud", "motivo_rechazo", "comprobantes_url",
        ]
        read_only_fields = fields


class IniciarPagoSerializer(serializers.Serializer):
    """CU5: monto a pagar (parcial o total) de un crédito puntual."""

    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    pago_total = serializers.BooleanField(required=False, default=False)


class EvaluacionCrediticiaInputSerializer(serializers.Serializer):
    cuil = serializers.CharField(max_length=11, min_length=11)
    ingresos = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))