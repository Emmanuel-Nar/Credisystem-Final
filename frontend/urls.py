from django.urls import path

from . import views

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("verificar/", views.VerificarEmailView.as_view(), name="verificar_email"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("simular/", views.SimularCreditoView.as_view(), name="simular_credito"),
    path("solicitar-credito/", views.SolicitarCreditoView.as_view(), name="solicitar_credito"),
    path("mis-creditos/", views.MisCreditosView.as_view(), name="mis_creditos"),
    path("estado-cuenta/", views.EstadoCuentaView.as_view(), name="estado_cuenta"),
    path("mis-solicitudes/", views.MisSolicitudesView.as_view(), name="mis_solicitudes"),
    path("solicitudes/<int:id_solicitud>/", views.DetalleSolicitudView.as_view(), name="detalle_solicitud"),
    path("creditos/<int:id_credito>/", views.DetalleCreditoView.as_view(), name="detalle_credito"),
    path("perfil/", views.PerfilView.as_view(), name="perfil_web"),
    path("notificaciones/", views.NotificacionesView.as_view(), name="notificaciones_web"),
    path("recuperar-password/", views.RecuperarPasswordView.as_view(), name="recuperar_password"),
    path("confirmar-password/", views.ConfirmarPasswordView.as_view(), name="confirmar_password"),
    path("evaluacion-crediticia/", views.EvaluacionCrediticiaView.as_view(), name="evaluacion_crediticia"),
]
