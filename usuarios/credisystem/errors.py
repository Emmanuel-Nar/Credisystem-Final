import logging

from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def _wants_json(request):
    path = getattr(request, "path", "")
    accept = request.headers.get("Accept", "") if hasattr(request, "headers") else ""
    return path.startswith("/api/") or "application/json" in accept.lower()


def _response(request, status_code, title, message, template_name):
    if _wants_json(request):
        return JsonResponse(
            {"error": {"status": status_code, "title": title, "message": message}},
            status=status_code,
        )
    return render(
        request,
        template_name,
        {"error_status": status_code, "error_title": title, "error_message": message},
        status=status_code,
    )


def bad_request(request, exception=None):
    return _response(request, 400, "Solicitud inválida", "Revisá los datos enviados e intentá nuevamente.", "errors/400.html")


def permission_denied(request, exception=None):
    return _response(request, 403, "Acceso denegado", "No tenés permisos para acceder a este recurso.", "errors/403.html")


def page_not_found(request, exception=None):
    return _response(request, 404, "Página no encontrada", "El recurso solicitado no existe o ya no está disponible.", "errors/404.html")


def server_error(request):
    return _response(request, 500, "Error interno", "Ocurrió un problema inesperado. Intentá nuevamente más tarde.", "errors/500.html")


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get("request")
    view = context.get("view")
    logger.exception(
        "Error no controlado en API",
        exc_info=exc,
        extra={
            "path": getattr(request, "path", ""),
            "view": view.__class__.__name__ if view else "",
        },
    )
    from rest_framework.response import Response
    return Response(
        {"detail": "Ocurrió un problema inesperado. Intentá nuevamente más tarde."},
        status=500,
    )
