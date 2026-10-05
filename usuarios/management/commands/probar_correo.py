from smtplib import SMTPException

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email


class Command(BaseCommand):
    help = "Comprueba la configuración local de correo. Solo envía un mensaje si se indica --enviar-a."

    def add_arguments(self, parser):
        parser.add_argument("--enviar-a", help="Dirección propia que recibirá el correo de prueba.")

    def handle(self, *args, **options):
        if not settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") or not settings.EMAIL_HOST:
            raise CommandError("SMTP no está configurado. Completá EMAIL_HOST y las credenciales en .env.")
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError("Faltan EMAIL_HOST_USER o EMAIL_HOST_PASSWORD en .env.")
        if not (settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL):
            raise CommandError("Activá TLS o SSL antes de conectar el correo.")
        destinatario = options.get("enviar_a")
        if not destinatario:
            self.stdout.write(self.style.SUCCESS("Configuración local presente. No se verificó la conexión y no se envió ningún mensaje."))
            return
        try:
            validate_email(destinatario)
        except ValidationError:
            raise CommandError("Ingresá un email de destino válido.") from None
        try:
            enviados = send_mail(
                "Prueba de correo - CREDISYSTEM",
                "Este es un mensaje de prueba solicitado desde CREDISYSTEM para comprobar su configuración de correo.",
                None, [destinatario], fail_silently=False,
            )
        except (SMTPException, OSError, ValueError) as exc:
            raise CommandError(f"No se pudo enviar ({type(exc).__name__}). Revisá las credenciales y la conexión; no compartas la contraseña.") from None
        if enviados != 1:
            raise CommandError("El servidor no confirmó el envío del mensaje.")
        self.stdout.write(self.style.SUCCESS("El servidor aceptó el mensaje. Comprobá su recepción y la carpeta Spam."))
