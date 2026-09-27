from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Valida la configuración mínima necesaria antes de desplegar CREDISYSTEM."

    def handle(self, *args, **options):
        errors = []
        warnings = []

        if settings.DEBUG:
            errors.append("DJANGO_DEBUG debe ser False.")

        hosts = list(settings.ALLOWED_HOSTS)
        if not hosts:
            errors.append("DJANGO_ALLOWED_HOSTS no puede estar vacío.")
        if any(host in {"localhost", "127.0.0.1", "*"} for host in hosts):
            warnings.append("DJANGO_ALLOWED_HOSTS contiene localhost/127.0.0.1/*; usa el dominio real en producción.")

        public_url = getattr(settings, "BACKEND_PUBLIC_URL", "")
        parsed = urlparse(public_url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append("BACKEND_PUBLIC_URL debe ser una URL pública HTTPS válida.")

        trusted = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []))
        if not trusted:
            errors.append("DJANGO_CSRF_TRUSTED_ORIGINS debe incluir el origen HTTPS público.")
        elif any(not origin.startswith("https://") for origin in trusted):
            errors.append("Todos los DJANGO_CSRF_TRUSTED_ORIGINS deben usar https:// en producción.")

        database = settings.DATABASES["default"]
        if database.get("ENGINE", "").endswith("sqlite3"):
            warnings.append("La base activa es SQLite. Para un deploy persistente configura MySQL y almacenamiento persistente.")

        if not getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", ""):
            warnings.append("MERCADOPAGO_ACCESS_TOKEN no está configurado; los pagos reales no funcionarán.")
        if not getattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", ""):
            warnings.append("MERCADOPAGO_WEBHOOK_SECRET no está configurado; falta validar el webhook productivo.")
        if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
            warnings.append("SMTP no está configurado; los correos se imprimirán en consola.")

        for message in warnings:
            self.stdout.write(self.style.WARNING(f"ADVERTENCIA: {message}"))

        if errors:
            for message in errors:
                self.stderr.write(self.style.ERROR(f"ERROR: {message}"))
            raise CommandError(f"Configuración de producción incompleta: {len(errors)} error(es).")

        self.stdout.write(self.style.SUCCESS("Configuración mínima de producción: OK"))
