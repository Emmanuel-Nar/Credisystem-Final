import json

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .admin_workflow import procesar_estado_solicitud
from .models import (
    BloqueoCuenta, Credito, Cuota, HistorialSolicitud, ImputacionPago, IntentoAcceso, Notificacion, Pago,
    Simulacion, SolicitudCredito, Transaccion,
)


@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ("id_credito", "id_usuario", "solicitud", "monto_original", "saldo_pendiente", "estado")
    list_filter = ("estado",)
    search_fields = ("id_usuario__email",)
    readonly_fields = ("solicitud",)


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ("id_cuota", "credito", "numero", "importe", "monto_pagado", "fecha_vencimiento", "estado")
    list_filter = ("estado", "fecha_vencimiento")
    search_fields = ("credito__id_usuario__email",)
    readonly_fields = ("credito", "numero", "importe", "monto_pagado", "fecha_vencimiento", "fecha_pago")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("id_pago", "id_credito", "monto_pagado", "medio_pago", "resultado", "fecha_pago", "comprobante_url")
    list_filter = ("medio_pago", "resultado")


@admin.register(ImputacionPago)
class ImputacionPagoAdmin(admin.ModelAdmin):
    list_display = ("id_imputacion", "pago", "cuota", "monto", "fecha_imputacion")
    search_fields = ("pago__id_credito__id_usuario__email",)
    readonly_fields = ("pago", "cuota", "monto", "fecha_imputacion")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ("id_transaccion", "id_usuario", "tipo", "importe", "fecha")
    list_filter = ("tipo",)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("id_notificacion", "id_usuario", "tipo", "leida", "fecha_envio")
    list_filter = ("tipo", "leida")


class SolicitudCreditoAdminForm(forms.ModelForm):
    class Meta:
        model = SolicitudCredito
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("estado") == SolicitudCredito.Estado.RECHAZADA and not (cleaned.get("motivo_rechazo") or "").strip():
            self.add_error("motivo_rechazo", "El motivo de rechazo es obligatorio al rechazar una solicitud.")
        return cleaned


class HistorialSolicitudInline(admin.TabularInline):
    model = HistorialSolicitud
    extra = 0
    can_delete = False
    fields = ("fecha_cambio", "administrador", "estado_anterior", "estado_nuevo", "observacion")
    readonly_fields = fields
    ordering = ("-fecha_cambio",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SolicitudCredito)
class SolicitudCreditoAdmin(admin.ModelAdmin):
    form = SolicitudCreditoAdminForm
    list_display = ("id_solicitud", "id_usuario", "monto_solicitado", "estado", "fecha_solicitud", "credito_generado")
    list_filter = ("estado", "fecha_solicitud")
    search_fields = ("id_usuario__email", "id_usuario__documento")
    readonly_fields = ("id_usuario", "monto_solicitado", "plazo_meses", "ingresos_mensuales", "fecha_solicitud", "comprobantes_url", "credito_generado")
    fields = ("id_usuario", "monto_solicitado", "plazo_meses", "ingresos_mensuales", "fecha_solicitud", "comprobantes_url", "estado", "motivo_rechazo", "credito_generado")
    inlines = (HistorialSolicitudInline,)

    def get_fields(self, request, obj=None):
        campos = list(super().get_fields(request, obj))
        if request.user.is_superuser:
            campos += ["cuil_cuit", "autorizacion_consulta", "bcra_estado", "bcra_fecha", "informe_bcra_privado"]
        return campos

    def get_readonly_fields(self, request, obj=None):
        return tuple(super().get_readonly_fields(request, obj)) + (
            "cuil_cuit", "autorizacion_consulta", "bcra_estado", "bcra_fecha", "informe_bcra_privado",
        )

    @admin.display(description="Evaluación BCRA (uso interno)")
    def informe_bcra_privado(self, obj):
        return format_html('<pre style="white-space:pre-wrap">{}</pre>', json.dumps(obj.bcra_informe, indent=2, ensure_ascii=False))

    def has_delete_permission(self, request, obj=None):
        # Las solicitudes forman parte del historial financiero: solo un
        # superusuario puede eliminarlas desde el panel.
        return bool(request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        # Django exige además is_staff para acceder al admin. Para procesar
        # solicitudes, el operador debe tener el permiso change específico.
        return bool(
            request.user.is_superuser
            or request.user.has_perm("creditos.change_solicitudcredito")
        )

    @admin.display(description="Crédito")
    def credito_generado(self, obj):
        if not obj or not obj.pk:
            return "—"
        try:
            return f"Crédito #{obj.credito_otorgado.id_credito}"
        except Credito.DoesNotExist:
            return "—"

    def save_model(self, request, obj, form, change):
        estado_anterior = None
        if change:
            estado_anterior = SolicitudCredito.objects.get(pk=obj.pk).estado
        super().save_model(request, obj, form, change)
        procesar_estado_solicitud(obj, estado_anterior)
        if estado_anterior is not None and estado_anterior != obj.estado:
            HistorialSolicitud.objects.create(
                solicitud=obj,
                administrador=request.user if request.user.is_authenticated else None,
                estado_anterior=estado_anterior,
                estado_nuevo=obj.estado,
                observacion=obj.motivo_rechazo if obj.estado == SolicitudCredito.Estado.RECHAZADA else None,
            )
            self.message_user(request, "Estado procesado, auditado y cliente notificado.", messages.SUCCESS)


@admin.register(Simulacion)
class SimulacionAdmin(admin.ModelAdmin):
    list_display = ("id_simulacion", "id_usuario", "monto", "plazo_meses", "cuota_estim", "fecha")


@admin.register(IntentoAcceso)
class IntentoAccesoAdmin(admin.ModelAdmin):
    list_display = ("id_intento", "id_usuario", "exito", "ip", "fecha_intento")
    list_filter = ("exito",)


@admin.register(BloqueoCuenta)
class BloqueoCuentaAdmin(admin.ModelAdmin):
    list_display = ("id_bloqueo", "id_usuario", "fecha_inicio", "fecha_fin", "motivo")
