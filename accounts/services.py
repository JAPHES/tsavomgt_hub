import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import AccountActivationOTP, User


class OTPVerificationError(Exception):
    pass


class OTPResendCooldown(Exception):
    pass


GENERIC_OTP_ERROR = "The activation code is invalid or has expired. Request a new code if needed."


def generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_activation_email(user, raw_otp, *, resent):
    context = {
        "user": user,
        "otp": raw_otp,
        "expires_minutes": settings.OTP_EXPIRY_MINUTES,
    }
    template_base = "emails/otp_resend" if resent else "emails/account_activation"
    subject = "Your new Tsavo Hub activation code" if resent else "Activate your Tsavo Hub account"
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def issue_activation_otp(user, *, resent=False, actor=None, request=None, enforce_cooldown=True):
    now = timezone.now()
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if (
            locked_user.activation_completed
            or locked_user.account_status == User.AccountStatus.INACTIVE
        ):
            raise OTPVerificationError(GENERIC_OTP_ERROR)
        previous = locked_user.activation_otps.order_by("-date_sent").first()
        if resent and enforce_cooldown and previous:
            available_at = previous.date_sent + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
            if now < available_at:
                raise OTPResendCooldown("Please wait before requesting another activation code.")
        locked_user.activation_otps.filter(used_at__isnull=True, invalidated_at__isnull=True).update(
            invalidated_at=now
        )
        raw_otp = generate_otp()
        otp = AccountActivationOTP.objects.create(
            user=locked_user,
            otp_hash=make_password(raw_otp),
            expires_at=now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
            resend_count=(previous.resend_count + 1) if previous and resent else 0,
            resent_from=previous if resent else None,
        )
        transaction.on_commit(
            lambda: _send_activation_email(locked_user, raw_otp, resent=resent)
        )
        if resent:
            record_audit(
                actor=actor,
                action=AuditLog.Action.OTP_RESENT,
                target=locked_user,
                new_values={"sent_at": now.isoformat()},
                request=request,
            )
    return otp


def verify_activation_otp(email, raw_otp):
    now = timezone.now()
    incorrect = False
    with transaction.atomic():
        try:
            user = User.objects.select_for_update().get(email__iexact=email.strip())
        except User.DoesNotExist as exc:
            raise OTPVerificationError(GENERIC_OTP_ERROR) from exc
        otp = user.activation_otps.select_for_update().order_by("-date_sent").first()
        if (
            otp is None
            or otp.used_at is not None
            or otp.invalidated_at is not None
            or now >= otp.expires_at
            or otp.attempt_count >= settings.OTP_MAX_ATTEMPTS
        ):
            raise OTPVerificationError(GENERIC_OTP_ERROR)
        if not check_password(raw_otp, otp.otp_hash):
            otp.attempt_count += 1
            otp.save(update_fields=["attempt_count"])
            incorrect = True
    if incorrect:
        raise OTPVerificationError(GENERIC_OTP_ERROR)
    return user, otp


def complete_activation(user_id, otp_id, password, *, request=None):
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        otp = AccountActivationOTP.objects.select_for_update().get(pk=otp_id, user=user)
        if (
            not otp.is_usable
            or otp.attempt_count >= settings.OTP_MAX_ATTEMPTS
            or user.account_status == User.AccountStatus.INACTIVE
        ):
            raise OTPVerificationError(GENERIC_OTP_ERROR)
        user.set_password(password)
        user.is_active = True
        user.email_verified = True
        user.activation_completed = True
        user.account_status = User.AccountStatus.ACTIVE
        user.save(
            update_fields=[
                "password",
                "is_active",
                "email_verified",
                "activation_completed",
                "account_status",
                "date_updated",
            ]
        )
        otp.used_at = now
        otp.save(update_fields=["used_at"])
        record_audit(
            actor=user,
            action=AuditLog.Action.ACCOUNT_ACTIVATED,
            target=user,
            new_values={"account_status": User.AccountStatus.ACTIVE, "email_verified": True},
            request=request,
        )
    return user
