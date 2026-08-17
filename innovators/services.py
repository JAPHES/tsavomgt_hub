from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

from accounts.models import User
from accounts.services import issue_activation_otp
from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import InnovatorProfile


@transaction.atomic
def create_innovator(cleaned_data, *, actor, request=None):
    user = User(
        email=cleaned_data["email"],
        first_name=cleaned_data["first_name"].strip(),
        last_name=cleaned_data["last_name"].strip(),
        role=User.Role.INNOVATOR,
        account_status=cleaned_data["account_status"],
        is_active=False,
    )
    user.set_unusable_password()
    user.full_clean(exclude=["password"])
    user.save()
    profile = InnovatorProfile.objects.create(
        user=user,
        registration_number=cleaned_data["registration_number"],
        phone_number=cleaned_data["phone_number"],
        innovation_project_name=cleaned_data["innovation_project_name"],
    )
    issue_activation_otp(user, actor=actor, request=request)
    record_audit(
        actor=actor,
        action=AuditLog.Action.ACCOUNT_CREATED,
        target=user,
        new_values={
            "email": user.email,
            "registration_number": profile.registration_number,
            "role": user.role,
            "account_status": user.account_status,
        },
        request=request,
    )
    return profile


@transaction.atomic
def update_innovator(form, *, actor, request=None):
    profile = form.instance
    user = User.objects.select_for_update().get(pk=profile.user_id)
    previous = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "registration_number": profile.registration_number,
        "project": profile.innovation_project_name,
    }
    new_email = form.cleaned_data["email"]
    email_changed = user.email != new_email
    user.email = new_email
    user.first_name = form.cleaned_data["first_name"].strip()
    user.last_name = form.cleaned_data["last_name"].strip()
    user_fields = ["email", "first_name", "last_name", "date_updated"]
    if email_changed:
        user.email_verified = False
        user.activation_completed = False
        user.account_status = User.AccountStatus.PENDING
        user.is_active = False
        user.set_unusable_password()
        user_fields.extend(
            ["email_verified", "activation_completed", "account_status", "is_active", "password"]
        )
    user.save(update_fields=user_fields)
    profile = form.save()
    if email_changed:
        issue_activation_otp(user, actor=actor, request=request)
    record_audit(
        actor=actor,
        action=AuditLog.Action.ACCOUNT_UPDATED,
        target=user,
        previous_values=previous,
        new_values={
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registration_number": profile.registration_number,
            "project": profile.innovation_project_name,
        },
        request=request,
    )
    return profile, email_changed


def send_deactivation_email(user):
    context = {"user": user}
    text_body = render_to_string("emails/account_deactivation.txt", context)
    html_body = render_to_string("emails/account_deactivation.html", context)
    message = EmailMultiAlternatives(
        "Your Tsavo Hub account has been deactivated",
        text_body,
        None,
        [user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
