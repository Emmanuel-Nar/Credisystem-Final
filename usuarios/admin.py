from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ("id_usuario", "email", "nombre", "apellido", "estado", "is_staff")
    list_filter = ("estado", "biometria_habilitada", "is_staff")
    search_fields = ("email", "nombre", "apellido", "documento")
    ordering = ("id_usuario",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "apellido", "telefono", "documento", "direccion")}),
        ("Estado", {"fields": ("estado", "biometria_habilitada", "is_active", "is_staff", "is_superuser")}),
        ("Permisos", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre", "apellido", "documento", "password1", "password2"),
        }),
    )
