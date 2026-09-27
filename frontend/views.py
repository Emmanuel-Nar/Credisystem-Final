from django.views.generic import TemplateView


class LandingView(TemplateView):
    template_name = "landing.html"


class LoginView(TemplateView):
    template_name = "login.html"


class RegistroView(TemplateView):
    template_name = "registro.html"


class VerificarEmailView(TemplateView):
    template_name = "verificar_email.html"


class DashboardView(TemplateView):
    template_name = "dashboard.html"


class SimularCreditoView(TemplateView):
    template_name = "simular_credito.html"


class SolicitarCreditoView(TemplateView):
    template_name = "solicitar_credito.html"


class MisCreditosView(TemplateView):
    template_name = "mis_creditos.html"


class EstadoCuentaView(TemplateView):
    template_name = "estado_cuenta.html"


class MisSolicitudesView(TemplateView):
    template_name = "mis_solicitudes.html"


class DetalleSolicitudView(TemplateView):
    template_name = "detalle_solicitud.html"


class DetalleCreditoView(TemplateView):
    template_name = "detalle_credito.html"


class PerfilView(TemplateView):
    template_name = "perfil.html"


class NotificacionesView(TemplateView):
    template_name = "notificaciones.html"


class RecuperarPasswordView(TemplateView):
    template_name = "recuperar_password.html"


class ConfirmarPasswordView(TemplateView):
    template_name = "confirmar_password.html"
