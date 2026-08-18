import secrets
import string

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import User


class TemporaryCredentialError(Exception):
    pass


def generate_temporary_password(length=18):
    """Return a strong password with characters from every required category."""
    if length < 12:
        raise ValueError("Temporary passwords must contain at least 12 characters.")
    groups = (string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*")
    characters = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    characters.extend(secrets.choice(alphabet) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def _send_temporary_credentials_email(user, temporary_password, *, login_url, reissued):
    context = {
        "user": user,
        "temporary_password": temporary_password,
        "login_url": login_url,
        "reissued": reissued,
    }
    subject = (
        "Your new Tsavo Hub temporary login credentials"
        if reissued
        else "Your Tsavo Hub login credentials"
    )
    text_body = render_to_string("emails/account_credentials.txt", context)
    html_body = render_to_string("emails/account_credentials.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def issue_temporary_credentials(user, *, actor=None, request=None, reissued=False):
    login_path = reverse("accounts:login")
    login_url = request.build_absolute_uri(login_path) if request else login_path
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.account_status == User.AccountStatus.INACTIVE:
            raise TemporaryCredentialError(
                "Restore account access before issuing temporary login credentials."
            )
        if reissued and not locked_user.must_change_password:
            raise TemporaryCredentialError(
                "Temporary login credentials can only be reissued before the first-login password change."
            )
        temporary_password = generate_temporary_password()
        locked_user.set_password(temporary_password)
        locked_user.must_change_password = True
        locked_user.email_verified = False
        locked_user.account_status = User.AccountStatus.PENDING
        locked_user.is_active = True
        locked_user.save(
            update_fields=[
                "password",
                "must_change_password",
                "email_verified",
                "account_status",
                "is_active",
                "date_updated",
            ]
        )
        transaction.on_commit(
            lambda: _send_temporary_credentials_email(
                locked_user,
                temporary_password,
                login_url=login_url,
                reissued=reissued,
            )
        )
        if reissued:
            record_audit(
                actor=actor,
                action=AuditLog.Action.TEMPORARY_CREDENTIALS_REISSUED,
                target=locked_user,
                new_values={"must_change_password": True},
                request=request,
            )
    return locked_user


def complete_first_login_password_change(user_id, password, *, request=None):
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        if not user.must_change_password or user.account_status == User.AccountStatus.INACTIVE:
            raise TemporaryCredentialError("This temporary-password session is no longer valid.")
        user.set_password(password)
        user.is_active = True
        user.email_verified = True
        user.must_change_password = False
        user.account_status = User.AccountStatus.ACTIVE
        user.save(
            update_fields=[
                "password",
                "is_active",
                "email_verified",
                "must_change_password",
                "account_status",
                "date_updated",
            ]
        )
        record_audit(
            actor=user,
            action=AuditLog.Action.ACCOUNT_ACTIVATED,
            target=user,
            new_values={
                "account_status": User.AccountStatus.ACTIVE,
                "email_verified": True,
                "must_change_password": False,
            },
            request=request,
        )
    return user
