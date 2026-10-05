from django.contrib import admin

from .models import ConfiguracionAsistente, PreguntaFrecuente


class SoloSuperusuarioAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(PreguntaFrecuente)
class PreguntaFrecuenteAdmin(SoloSuperusuarioAdmin):
    list_display = ['pregunta', 'orden', 'activa', 'destino']
    list_editable = ['orden', 'activa']
    list_filter = ['activa']
    search_fields = ['pregunta', 'respuesta']
    fields = ['pregunta', 'respuesta', 'destino', 'orden', 'activa']


@admin.register(ConfiguracionAsistente)
class ConfiguracionAsistenteAdmin(SoloSuperusuarioAdmin):
    fields = ['activo', 'numero_whatsapp']

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not ConfiguracionAsistente.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
