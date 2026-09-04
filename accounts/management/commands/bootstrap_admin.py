import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = "Create the first administrator from deployment environment variables."

    @transaction.atomic
    def handle(self, *args, **options):
        email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        first_name = os.getenv("INITIAL_ADMIN_FIRST_NAME", "Hub").strip()
        last_name = os.getenv("INITIAL_ADMIN_LAST_NAME", "Administrator").strip()

        if not email and not password:
            self.stdout.write(
                self.style.WARNING(
                    "Initial administrator credentials are not configured; skipping."
                )
            )
            return

        if not email or not password:
            raise CommandError(
                "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together."
            )

        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("INITIAL_ADMIN_EMAIL is not a valid email address.") from exc

        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    "An administrator already exists; bootstrap was safely skipped."
                )
            )
            return

        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                "A non-administrator account already uses INITIAL_ADMIN_EMAIL; "
                "choose a different address or promote the account manually."
            )

        candidate = User(email=email, first_name=first_name, last_name=last_name)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Initial administrator created for {email}.")
        )
