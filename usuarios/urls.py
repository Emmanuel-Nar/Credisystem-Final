from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("registro/", views.RegistroView.as_view(), name="registro-api"),
    path("verificar/", views.VerificarCuentaView.as_view(), name="verificar-cuenta"),
    path("verificar/reenviar/", views.ReenviarCodigoView.as_view(), name="reenviar-codigo"),
    path("verificar/enlace/<str:uidb64>/<str:token>/", views.VerificarEmailEnlaceView.as_view(), name="verificar-email-enlace"),

    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    path("password/recuperar/", views.SolicitarRecuperacionView.as_view(), name="password-recuperar"),
    path("password/cambiar/", views.CambiarPasswordView.as_view(), name="password-cambiar"),
    path("password/confirmar/", views.ConfirmarRecuperacionView.as_view(), name="password-confirmar"),
    path("password/enlace/<str:uidb64>/<str:token>/", views.RecuperacionEnlaceView.as_view(), name="password-enlace"),

    path("perfil/", views.PerfilView.as_view(), name="perfil"),
]
