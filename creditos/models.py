from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Credito(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CANCELADO = "cancelado", "Cancelado"
        EN_MORA = "en_mora", "En mora"

    id_credito = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="creditos",
        db_column="id_usuario",
    )
    solicitud = models.OneToOneField(
        "SolicitudCredito",
        on_delete=models.PROTECT,
        related_name="credito_otorgado",
        null=True,
        blank=True,
    )
    monto_original = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    saldo_pendiente = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tasa_interes_anual = models.DecimalField(max_digits=5, decimal_places=2)
    plazo_meses = models.PositiveIntegerField()
    fecha_otorgamiento = models.DateField()
    primer_vencimiento = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)

    class Meta:
        db_table = "credito"
        indexes = [models.Index(fields=["id_usuario", "estado"])]

    def __str__(self):
        return f"Crédito #{self.id_credito} - {self.id_usuario}"


class Pago(models.Model):
    class MedioPago(models.TextChoices):
        DEBITO = "debito", "Débito"
        CREDITO = "credito", "Crédito"
        EFECTIVO = "efectivo", "Efectivo"
        BILLETERA = "billetera", "Billetera virtual"

    class Resultado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    id_pago = models.AutoField(primary_key=True)
    id_credito = models.ForeignKey(
        Credito, on_delete=models.PROTECT, related_name="pagos", db_column="id_credito"
    )
    fecha_pago = models.DateTimeField(auto_now_add=True)
    monto_pagado = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices, blank=True, null=True)
    # Solo la referencia/URL del comprobante emitido por la pasarela (Mercado Pago),
    # nunca datos de tarjeta: eso lo maneja la pasarela, no se persiste acá.
    comprobante_url = models.CharField(max_length=255, blank=True, null=True)
    resultado = models.CharField(
        max_length=20, choices=Resultado.choices, default=Resultado.PENDIENTE
    )

    # Campos para reconciliar la confirmación asincrónica de Mercado Pago
    # (Checkout Pro: se crea una preferencia, el usuario paga en MP, y
    # después llega un webhook). No están en el diccionario de datos
    # original porque ese modelaba un pago síncrono; se agregan acá.
    mp_preference_id = models.CharField(max_length=100, blank=True, null=True)
    mp_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    external_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        db_table = "pago"
        indexes = [models.Index(fields=["id_credito", "fecha_pago"])]

    def __str__(self):
        return f"Pago #{self.id_pago} - Crédito #{self.id_credito_id}"


class Transaccion(models.Model):
    class Tipo(models.TextChoices):
        PAGO = "pago", "Pago"
        SOLICITUD = "solicitud", "Solicitud"
        DESEMBOLSO = "desembolso", "Desembolso"
        SIMULACION = "simulacion", "Simulación"

    id_transaccion = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transacciones",
        db_column="id_usuario",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = "transaccion"
        indexes = [models.Index(fields=["id_usuario", "fecha"])]

    def __str__(self):
        return f"Transacción #{self.id_transaccion} ({self.tipo})"


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        VENCIMIENTO = "vencimiento", "Vencimiento"
        PROMOCION = "promocion", "Promoción"
        ESTADO_SOLICITUD = "estado_solicitud", "Estado de solicitud"

    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
        db_column="id_usuario",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    mensaje = models.CharField(max_length=255)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    class Meta:
        db_table = "notificacion"
        indexes = [models.Index(fields=["id_usuario", "leida"])]

    def __str__(self):
        return f"Notificación #{self.id_notificacion} - {self.tipo}"


class SolicitudCredito(models.Model):
    class Estado(models.TextChoices):
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"
        EN_REVISION = "en_revision", "En revisión"

    id_solicitud = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes",
        db_column="id_usuario",
    )
    monto_solicitado = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    plazo_meses = models.PositiveIntegerField()
    ingresos_mensuales = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.EN_REVISION
    )
    cuil_cuit = models.CharField(max_length=11, blank=True, default="")
    autorizacion_consulta = models.BooleanField(default=False)
    id_envio = models.UUIDField(null=True, blank=True, editable=False)
    bcra_estado = models.CharField(max_length=20, default="no_consultado", editable=False)
    bcra_fecha = models.DateTimeField(null=True, blank=True, editable=False)
    bcra_informe = models.JSONField(default=dict, blank=True, editable=False)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    motivo_rechazo = models.CharField(max_length=255, blank=True, null=True)
    # Ruta a los archivos subidos (comprobantes de ingresos). La validación de
    # tipo/tamaño de archivo se hace en el serializer, no acá.
    comprobantes_url = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "solicitud_credito"
        constraints = [models.UniqueConstraint(fields=["id_usuario", "id_envio"], name="uq_solicitud_usuario_envio")]
        indexes = [models.Index(fields=["id_usuario", "estado"])]

    def __str__(self):
        return f"Solicitud #{self.id_solicitud} - {self.estado}"


class HistorialSolicitud(models.Model):
    id_historial = models.AutoField(primary_key=True)
    solicitud = models.ForeignKey(
        SolicitudCredito,
        on_delete=models.CASCADE,
        related_name="historial_administrativo",
    )
    administrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cambios_solicitudes",
        null=True,
        blank=True,
    )
    estado_anterior = models.CharField(max_length=20, choices=SolicitudCredito.Estado.choices)
    estado_nuevo = models.CharField(max_length=20, choices=SolicitudCredito.Estado.choices)
    observacion = models.CharField(max_length=255, blank=True, null=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_solicitud"
        ordering = ["-fecha_cambio", "-id_historial"]
        indexes = [models.Index(fields=["solicitud", "fecha_cambio"])]

    def __str__(self):
        return f"Solicitud #{self.solicitud_id}: {self.estado_anterior} → {self.estado_nuevo}"


class Simulacion(models.Model):
    id_simulacion = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="simulaciones",
        db_column="id_usuario",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    plazo_meses = models.PositiveIntegerField()
    tasa_anual = models.DecimalField(max_digits=5, decimal_places=2)
    cuota_estim = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "simulacion"

    def __str__(self):
        return f"Simulación #{self.id_simulacion} - {self.id_usuario_id}"


class IntentoAcceso(models.Model):
    """
    Registro de cada intento de login (exitoso o no). Base para el
    bloqueo por intentos fallidos y para monitoreo/auditoría de accesos.
    """

    id_intento = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="intentos_acceso",
        db_column="id_usuario",
        null=True,
        blank=True,
    )
    fecha_intento = models.DateTimeField(auto_now_add=True)
    exito = models.BooleanField()
    ip = models.GenericIPAddressField()
    motivo_fallo = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "intento_acceso"
        indexes = [models.Index(fields=["id_usuario", "fecha_intento"])]

    def __str__(self):
        return f"Intento #{self.id_intento} - {'OK' if self.exito else 'FALLIDO'}"


class BloqueoCuenta(models.Model):
    id_bloqueo = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bloqueos",
        db_column="id_usuario",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    motivo = models.CharField(max_length=100)

    class Meta:
        db_table = "bloqueo_cuenta"
        indexes = [models.Index(fields=["id_usuario", "fecha_fin"])]

    def __str__(self):
        return f"Bloqueo #{self.id_bloqueo} - {self.id_usuario_id}"

class Cuota(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADA = "pagada", "Pagada"
        VENCIDA = "vencida", "Vencida"

    id_cuota = models.AutoField(primary_key=True)
    credito = models.ForeignKey(Credito, on_delete=models.PROTECT, related_name="cuotas")
    numero = models.PositiveIntegerField()
    importe = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_pago = models.DateTimeField(blank=True, null=True)
    monto_pagado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = "cuota"
        ordering = ["numero"]
        constraints = [models.UniqueConstraint(fields=["credito", "numero"], name="uq_cuota_credito_numero")]
        indexes = [models.Index(fields=["credito", "estado", "fecha_vencimiento"])]

    def __str__(self):
        return f"Cuota {self.numero}/{self.credito.plazo_meses} - Crédito #{self.credito_id}"


class ImputacionPago(models.Model):
    id_imputacion = models.AutoField(primary_key=True)
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, related_name="imputaciones")
    cuota = models.ForeignKey(Cuota, on_delete=models.PROTECT, related_name="imputaciones")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_imputacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "imputacion_pago"
        constraints = [
            models.UniqueConstraint(fields=["pago", "cuota"], name="uq_imputacion_pago_cuota")
        ]
        indexes = [models.Index(fields=["pago", "cuota"], name="imputacion__pago_id_6dca2e_idx")]

    def __str__(self):
        return f"Pago #{self.pago_id} → Cuota #{self.cuota_id}: ${self.monto}"
