from django.urls import path

from . import views

urlpatterns = [
    path("", views.MisCreditosView.as_view(), name="mis-creditos"),
    path("estado-cuenta/", views.EstadoCuentaView.as_view(), name="estado-cuenta"),
    path("simular/", views.SimularCreditoView.as_view(), name="simular-credito"),
    path("solicitudes/", views.SolicitarCreditoView.as_view(), name="solicitudes-credito"),
    path("solicitudes/<int:id_solicitud>/", views.SolicitudCreditoDetalleView.as_view(), name="solicitud-detalle"),
    path("pagos/<int:id_pago>/", views.PagoDetalleView.as_view(), name="pago-detalle"),
    path("pagos/<int:id_pago>/comprobante/", views.ComprobantePagoView.as_view(), name="comprobante-pago"),
    path("<int:id_credito>/", views.CreditoDetalleView.as_view(), name="credito-detalle"),
    path("<int:id_credito>/pagos/", views.IniciarPagoView.as_view(), name="iniciar-pago"),
]
