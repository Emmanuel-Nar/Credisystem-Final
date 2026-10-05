from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Credito, Cuota, Notificacion, Pago, Simulacion, SolicitudCredito, Transaccion
from .serializers import (
    CreditoDetalleSerializer,
    CreditoListSerializer,
    EstadoCuentaSerializer,
    IniciarPagoSerializer,
    NotificacionSerializer,
    PagoSerializer,
    SimulacionInputSerializer,
    SimulacionSerializer,
    SolicitudCreditoCrearSerializer,
    SolicitudCreditoSerializer,
    TransaccionSerializer,
)
from .services import calcular_cuota, crear_cuotas_para_credito, evaluar_solicitud, procesar_pago_aprobado
from .notificaciones import notificar
from . import mercadopago_service
from .bcra import evaluar_bcra
from .admin_workflow import procesar_estado_solicitud


class MisCreditosView(generics.ListAPIView):
    """Lista los créditos del usuario autenticado (no de otros usuarios)."""

    serializer_class = CreditoListSerializer

    def get_queryset(self):
        return Credito.objects.filter(id_usuario=self.request.user).order_by("-fecha_otorgamiento")


class CreditoDetalleView(generics.RetrieveAPIView):
    """
    CU3: saldo y resumen de un crédito puntual, con su historial de pagos.
    Restringido al dueño del crédito: si pertenece a otro usuario, 404
    (no se filtra por pk sobre toda la tabla, sino sobre el queryset ya
    acotado al usuario autenticado).
    """

    serializer_class = CreditoDetalleSerializer
    lookup_url_kwarg = "id_credito"

    def get_queryset(self):
        return Credito.objects.filter(id_usuario=self.request.user).prefetch_related("pagos")


class EstadoCuentaView(APIView):
    """Resumen financiero consolidado del usuario autenticado."""

    def get(self, request):
        creditos = (
            Credito.objects.filter(id_usuario=request.user)
            .prefetch_related("cuotas", "pagos", "pagos__imputaciones", "pagos__imputaciones__cuota")
            .order_by("-fecha_otorgamiento", "-id_credito")
        )
        cuotas = Cuota.objects.filter(credito__id_usuario=request.user)
        pagos_aprobados = Pago.objects.filter(
            id_credito__id_usuario=request.user, resultado=Pago.Resultado.APROBADO
        ).order_by("-fecha_pago")

        saldo_total = sum((c.saldo_pendiente for c in creditos), Decimal("0.00"))
        proxima = cuotas.filter(
            estado__in=[Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDA]
        ).order_by("fecha_vencimiento", "numero").first()
        total_pagado = pagos_aprobados.aggregate(total=Sum("monto_pagado"))["total"] or Decimal("0.00")

        data = {
            "saldo_total_pendiente": saldo_total,
            "creditos_activos": creditos.filter(estado=Credito.Estado.ACTIVO).count(),
            "cuotas_pagadas": cuotas.filter(estado=Cuota.Estado.PAGADA).count(),
            "cuotas_pendientes": cuotas.filter(estado=Cuota.Estado.PENDIENTE).count(),
            "cuotas_vencidas": cuotas.filter(estado=Cuota.Estado.VENCIDA).count(),
            "proximo_vencimiento": proxima.fecha_vencimiento if proxima else None,
            "total_pagado": total_pagado,
            "creditos": creditos,
            "pagos": pagos_aprobados,
        }
        return Response(EstadoCuentaSerializer(data).data)


class HistorialTransaccionesView(generics.ListAPIView):
    """
    CU6: historial de transacciones del usuario, filtrable por tipo
    (?tipo=pago|solicitud|desembolso|simulacion) y rango de fechas
    (?fecha_desde=YYYY-MM-DD&fecha_hasta=YYYY-MM-DD).
    """

    serializer_class = TransaccionSerializer

    def get_queryset(self):
        qs = Transaccion.objects.filter(id_usuario=self.request.user).order_by("-fecha")

        tipo = self.request.query_params.get("tipo")
        if tipo:
            tipos_validos = {choice.value for choice in Transaccion.Tipo}
            if tipo not in tipos_validos:
                raise ValidationError({"tipo": f"Valor inválido. Opciones: {sorted(tipos_validos)}"})
            qs = qs.filter(tipo=tipo)

        fecha_desde = self.request.query_params.get("fecha_desde")
        if fecha_desde:
            fecha = parse_date(fecha_desde)
            if not fecha:
                raise ValidationError({"fecha_desde": "Formato esperado: YYYY-MM-DD"})
            qs = qs.filter(fecha__gte=make_aware(datetime.combine(fecha, datetime.min.time())))

        fecha_hasta = self.request.query_params.get("fecha_hasta")
        if fecha_hasta:
            fecha = parse_date(fecha_hasta)
            if not fecha:
                raise ValidationError({"fecha_hasta": "Formato esperado: YYYY-MM-DD"})
            qs = qs.filter(fecha__lte=make_aware(datetime.combine(fecha, datetime.max.time())))

        return qs


class SimularCreditoView(APIView):
    """
    CU8: el usuario ingresa monto y plazo, el sistema calcula y muestra
    la cuota estimada, y queda guardada la simulación (por si continúa
    con la solicitud real después).
    """

    def post(self, request):
        serializer = SimulacionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        monto = serializer.validated_data["monto"]
        plazo_meses = serializer.validated_data["plazo_meses"]

        cuota = calcular_cuota(monto, plazo_meses)

        simulacion = Simulacion.objects.create(
            id_usuario=request.user,
            monto=monto,
            plazo_meses=plazo_meses,
            tasa_anual=Decimal(settings.CREDITO_TASA_INTERES_ANUAL),
            cuota_estim=cuota,
        )
        Transaccion.objects.create(
            id_usuario=request.user,
            tipo=Transaccion.Tipo.SIMULACION,
            descripcion=f"Simulación de crédito por ${monto} a {plazo_meses} meses",
            importe=monto,
        )

        return Response(SimulacionSerializer(simulacion).data, status=status.HTTP_201_CREATED)


class SolicitarCreditoView(generics.ListAPIView):
    """
    CU4: listar las solicitudes del usuario (GET) y crear una nueva (POST).
    La creación incluye precalificación automática: si se aprueba, se
    otorga el crédito en el momento (desembolso); si no, queda rechazada
    con motivo. En ambos casos se notifica al usuario.
    """

    serializer_class = SolicitudCreditoSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return SolicitudCredito.objects.filter(id_usuario=self.request.user).order_by("-fecha_solicitud")

    def post(self, request):
        entrada = SolicitudCreditoCrearSerializer(data=request.data, context={"request": request})
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        existente = SolicitudCredito.objects.filter(id_usuario=request.user, id_envio=datos["id_envio"]).first()
        if existente:
            return Response(SolicitudCreditoSerializer(existente).data)

        estado, motivo_rechazo, _ = evaluar_solicitud(
            datos["monto_solicitado"], datos["plazo_meses"], datos["ingresos_mensuales"]
        )
        informe = {"estado": "no_consultado", "motivo": "reglas_locales"}
        fecha_consulta = None
        if estado == SolicitudCredito.Estado.APROBADA:
            estado, informe = evaluar_bcra(datos["cuil_cuit"])
            fecha_consulta = timezone.now()

        ruta_guardada = None
        try:
            with transaction.atomic():
                # Serializa los envíos de una cuenta y evita duplicados al reintentar.
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                existente = SolicitudCredito.objects.filter(id_usuario=request.user, id_envio=datos["id_envio"]).first()
                if existente:
                    return Response(SolicitudCreditoSerializer(existente).data)
                archivo = datos["comprobante"]
                extension = archivo.name.rsplit(".", 1)[-1].lower()
                ruta_guardada = default_storage.save(f"comprobantes/{uuid4().hex}.{extension}", archivo)
                solicitud = SolicitudCredito.objects.create(
                    id_usuario=request.user,
                    monto_solicitado=datos["monto_solicitado"],
                    plazo_meses=datos["plazo_meses"],
                    ingresos_mensuales=datos["ingresos_mensuales"],
                    cuil_cuit=datos["cuil_cuit"], autorizacion_consulta=True,
                    id_envio=datos["id_envio"], bcra_estado=informe["estado"],
                    bcra_fecha=fecha_consulta, bcra_informe=informe,
                    estado=estado, motivo_rechazo=motivo_rechazo,
                    comprobantes_url=ruta_guardada,
                )
                Transaccion.objects.create(
                    id_usuario=request.user, tipo=Transaccion.Tipo.SOLICITUD,
                    descripcion=f"Solicitud de crédito #{solicitud.pk}",
                    importe=datos["monto_solicitado"],
                )
                procesar_estado_solicitud(solicitud)
        except Exception:
            if ruta_guardada:
                default_storage.delete(ruta_guardada)
            raise
        return Response(SolicitudCreditoSerializer(solicitud).data, status=status.HTTP_201_CREATED)


class SolicitudCreditoDetalleView(generics.RetrieveAPIView):
    """Detalle de una solicitud puntual, acotado al dueño."""

    serializer_class = SolicitudCreditoSerializer
    lookup_url_kwarg = "id_solicitud"

    def get_queryset(self):
        return SolicitudCredito.objects.filter(id_usuario=self.request.user)


class IniciarPagoView(APIView):
    """
    CU5 (pasos 1-3): el usuario elige monto (parcial o total) para un
    crédito propio. Se crea el Pago en estado "pendiente" y una
    preferencia de Checkout Pro en Mercado Pago; se devuelve la URL
    (init_point) a la que hay que redirigir al usuario para pagar.
    El medio de pago concreto (tarjeta, efectivo, billetera) lo define
    Mercado Pago del lado de su checkout, no acá.
    """

    def post(self, request, id_credito):
        credito = Credito.objects.filter(id_usuario=request.user, id_credito=id_credito).first()
        if credito is None:
            return Response({"detail": "Crédito no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if credito.estado != Credito.Estado.ACTIVO:
            return Response(
                {"detail": "Este crédito no admite pagos en su estado actual."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IniciarPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        monto = credito.saldo_pendiente if serializer.validated_data["pago_total"] else serializer.validated_data["monto"]

        if monto > credito.saldo_pendiente:
            return Response(
                {"detail": "El monto no puede superar el saldo pendiente."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pago = Pago.objects.create(
            id_credito=credito,
            monto_pagado=monto,
            resultado=Pago.Resultado.PENDIENTE,
            external_reference=f"pago-{uuid4().hex}",
        )

        try:
            preference_id, init_point = mercadopago_service.crear_preferencia_pago(pago, credito)
        except RuntimeError as exc:
            pago.delete()
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        pago.mp_preference_id = preference_id
        pago.save(update_fields=["mp_preference_id"])

        return Response(
            {
                "id_pago": pago.id_pago,
                "estado": pago.resultado,
                "init_point": init_point,
            },
            status=status.HTTP_201_CREATED,
        )


class ComprobantePagoView(APIView):
    """Genera un comprobante imprimible para un pago aprobado del usuario autenticado."""

    def get(self, request, id_pago):
        try:
            pago = Pago.objects.select_related("id_credito", "id_credito__id_usuario").get(
                pk=id_pago, id_credito__id_usuario=request.user
            )
        except Pago.DoesNotExist:
            return Response({"detail": "Comprobante no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pago.resultado != Pago.Resultado.APROBADO:
            return Response(
                {"detail": "El comprobante está disponible únicamente para pagos aprobados."},
                status=status.HTTP_409_CONFLICT,
            )

        usuario = pago.id_credito.id_usuario
        referencia = pago.mp_payment_id or pago.external_reference or f"PAGO-{pago.id_pago}"
        fecha = timezone.localtime(pago.fecha_pago).strftime("%d/%m/%Y %H:%M")
        monto = f"{pago.monto_pagado:.2f}"
        html = f"""<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>Comprobante #{pago.id_pago}</title>
<style>body{{font-family:Arial,sans-serif;max-width:720px;margin:40px auto;padding:24px;color:#222}}h1{{margin-bottom:4px}}.dato{{padding:10px 0;border-bottom:1px solid #ddd}}@media print{{button{{display:none}}}}</style></head>
<body><h1>CREDISYSTEM</h1><p>Comprobante de pago</p>
<div class=\"dato\"><b>Comprobante:</b> #{pago.id_pago}</div>
<div class=\"dato\"><b>Cliente:</b> {usuario.nombre} {usuario.apellido}</div>
<div class=\"dato\"><b>Crédito:</b> #{pago.id_credito_id}</div>
<div class=\"dato\"><b>Fecha:</b> {fecha}</div>
<div class=\"dato\"><b>Importe:</b> $ {monto}</div>
<div class=\"dato\"><b>Medio:</b> {pago.get_medio_pago_display() if pago.medio_pago else '—'}</div>
<div class=\"dato\"><b>Referencia:</b> {referencia}</div>
<p>Estado: Pago aprobado</p><button onclick=\"window.print()\">Imprimir / Guardar PDF</button></body></html>"""
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="comprobante-pago-{pago.id_pago}.html"'
        response["Cache-Control"] = "private, no-store"
        return response


class PagoDetalleView(generics.RetrieveAPIView):
    """Consultar el estado de un pago propio (para hacer polling desde el frontend)."""

    serializer_class = PagoSerializer
    lookup_url_kwarg = "id_pago"

    def get_queryset(self):
        return Pago.objects.filter(id_credito__id_usuario=self.request.user)


class WebhookMercadoPagoView(APIView):
    """
    CU5 (pasos 4-6): Mercado Pago llama a esta URL cuando cambia el
    estado de un pago. Acá se valida la notificación, se consulta el
    detalle real del pago (nunca se confía en el estado que venga en
    el payload del webhook, siempre se re-consulta a la API) y se
    actualiza el Pago, el saldo del Crédito, la Transacción y se
    genera la Notificación al usuario.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not mercadopago_service.validar_firma_webhook(request):
            return Response({"detail": "Firma inválida."}, status=status.HTTP_401_UNAUTHORIZED)

        payment_id = request.data.get("data", {}).get("id") or request.GET.get("data.id")
        tipo = request.data.get("type") or request.GET.get("type")

        if tipo != "payment" or not payment_id:
            # Otros tipos de notificación (merchant_order, etc.) se ignoran
            return Response(status=status.HTTP_200_OK)

        try:
            detalle = mercadopago_service.obtener_pago_mp(payment_id)
        except RuntimeError:
            return Response(status=status.HTTP_502_BAD_GATEWAY)

        external_reference = detalle.get("external_reference")
        pago = Pago.objects.filter(external_reference=external_reference).select_related("id_credito").first()
        if pago is None:
            return Response(status=status.HTTP_200_OK)  # notificación no correspondiente a este sistema

        if pago.resultado != Pago.Resultado.PENDIENTE:
            return Response(status=status.HTTP_200_OK)  # ya procesado, evita duplicar el efecto

        estado_mp = detalle.get("status")  # approved | rejected | pending | in_process...
        pago.mp_payment_id = str(payment_id)
        pago.medio_pago = mercadopago_service.MEDIO_PAGO_MP.get(detalle.get("payment_type_id"))
        pago.comprobante_url = detalle.get("transaction_details", {}).get("external_resource_url") or ""

        if estado_mp == "approved":
            # Primero se persisten los metadatos de Mercado Pago; el servicio
            # transaccional aplica saldo, cuotas, imputaciones y resultado.
            pago.save(update_fields=["mp_payment_id", "medio_pago", "comprobante_url"])
            pago = procesar_pago_aprobado(pago)
            credito = pago.id_credito
            credito.refresh_from_db()
            notificar(
                credito.id_usuario,
                Notificacion.Tipo.VENCIMIENTO,
                f"Tu pago de ${pago.monto_pagado} fue aprobado. Saldo pendiente: ${credito.saldo_pendiente}.",
            )
        elif estado_mp in ("rejected", "cancelled"):
            pago.resultado = Pago.Resultado.RECHAZADO
            notificar(
                pago.id_credito.id_usuario,
                Notificacion.Tipo.VENCIMIENTO,
                f"Tu pago de ${pago.monto_pagado} no pudo procesarse. Podés reintentarlo.",
            )
        # si sigue "pending"/"in_process", se deja el Pago en PENDIENTE

        pago.save()
        return Response(status=status.HTTP_200_OK)


class NotificacionesView(generics.ListAPIView):
    """
    CU7: historial de notificaciones del usuario. Filtrable por
    ?leida=true / ?leida=false. Ordenadas de la más reciente a la más
    vieja.
    """

    serializer_class = NotificacionSerializer

    def get_queryset(self):
        qs = Notificacion.objects.filter(id_usuario=self.request.user).order_by("-fecha_envio")
        leida = self.request.query_params.get("leida")
        if leida is not None:
            qs = qs.filter(leida=leida.lower() == "true")
        return qs


class MarcarNotificacionLeidaView(APIView):
    """Marca una notificación puntual del usuario como leída."""

    def patch(self, request, id_notificacion):
        notificacion = Notificacion.objects.filter(
            id_usuario=request.user, id_notificacion=id_notificacion
        ).first()
        if notificacion is None:
            return Response({"detail": "Notificación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        notificacion.leida = True
        notificacion.save(update_fields=["leida"])
        return Response(NotificacionSerializer(notificacion).data)


class MarcarTodasLeidasView(APIView):
    """Marca todas las notificaciones pendientes del usuario como leídas."""

    def post(self, request):
        actualizadas = Notificacion.objects.filter(id_usuario=request.user, leida=False).update(leida=True)
        return Response({"actualizadas": actualizadas})
