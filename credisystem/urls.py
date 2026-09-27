"""
URL configuration for credisystem project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
from django.db import connection
from django.http import JsonResponse


def health_db(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "database": "connected"})
    except Exception as exc:
        return JsonResponse({"status": "error", "database": "disconnected"}, status=503)
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.db import connection
from django.http import JsonResponse


def health_db(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "database": "connected"})
    except Exception as exc:
        return JsonResponse({"status": "error", "database": "disconnected"}, status=503)

from creditos.views import (
    HistorialTransaccionesView,
    MarcarNotificacionLeidaView,
    MarcarTodasLeidasView,
    NotificacionesView,
    WebhookMercadoPagoView,
)

urlpatterns = [
    path('api/health/', health_db, name='health-db'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('usuarios.urls')),
    path('api/creditos/', include('creditos.urls')),
    path('api/transacciones/', HistorialTransaccionesView.as_view(), name='historial-transacciones'),
    path('api/pagos/webhook/mercadopago/', WebhookMercadoPagoView.as_view(), name='webhook-mercadopago'),
    path('api/notificaciones/', NotificacionesView.as_view(), name='notificaciones'),
    path('api/notificaciones/leer-todas/', MarcarTodasLeidasView.as_view(), name='notificaciones-leer-todas'),
    path('api/notificaciones/<int:id_notificacion>/leer/', MarcarNotificacionLeidaView.as_view(), name='notificacion-leer'),

    path('', include('frontend.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "credisystem.errors.bad_request"
handler403 = "credisystem.errors.permission_denied"
handler404 = "credisystem.errors.page_not_found"
handler500 = "credisystem.errors.server_error"
