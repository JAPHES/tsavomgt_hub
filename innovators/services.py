from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from accounts.models import User
from accounts.services import issue_temporary_credentials
from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import InnovatorProfile, InnovatorProject


class ProjectError(Exception):
    pass


@transaction.atomic
def create_innovator(cleaned_data, *, actor, request=None):
    user = User(
        email=cleaned_data["email"],
        first_name=cleaned_data["first_name"].strip(),
        last_name=cleaned_data["last_name"].strip(),
        role=User.Role.INNOVATOR,
        account_status=User.AccountStatus.PENDING,
        is_active=False,
    )
    user.set_unusable_password()
    user.full_clean(exclude=["password"])
    user.save()
    profile = InnovatorProfile.objects.create(
        user=user,
        registration_number=cleaned_data["registration_number"],
        phone_number=cleaned_data["phone_number"],
    )
    issue_temporary_credentials(user, actor=actor, request=request)
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
    }
    new_email = form.cleaned_data["email"]
    email_changed = user.email != new_email
    user.email = new_email
    user.first_name = form.cleaned_data["first_name"].strip()
    user.last_name = form.cleaned_data["last_name"].strip()
    user_fields = ["email", "first_name", "last_name", "date_updated"]
    if email_changed:
        user.email_verified = False
        user.must_change_password = True
        user.account_status = User.AccountStatus.PENDING
        user.is_active = True
        user.set_unusable_password()
        user_fields.extend(
            ["email_verified", "must_change_password", "account_status", "is_active", "password"]
        )
    user.save(update_fields=user_fields)
    profile = form.save()
    if email_changed:
        issue_temporary_credentials(user, actor=actor, request=request, reissued=True)
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
        },
        request=request,
    )
    return profile, email_changed


@transaction.atomic
def create_project(profile, *, name, details, area_of_focus, actor, request=None):
    locked_profile = (
        InnovatorProfile.objects.select_for_update().select_related("user").get(pk=profile.pk)
    )
    if actor.pk != locked_profile.user_id or actor.role != User.Role.INNOVATOR:
        raise ProjectError("You can only add projects to your own innovator profile.")
    if InnovatorProject.objects.filter(
        profile=locked_profile, name__iexact=name.strip()
    ).exists():
        raise ProjectError("You already have a project with this name.")

    project = InnovatorProject(
        profile=locked_profile,
        name=name,
        details=details,
        area_of_focus=area_of_focus,
    )
    project.full_clean(validate_unique=False, validate_constraints=False)
    try:
        project.save()
    except IntegrityError as exc:
        raise ProjectError("You already have a project with this name.") from exc
    record_audit(
        actor=actor,
        action=AuditLog.Action.PROJECT_CREATED,
        target=project,
        new_values={
            "name": project.name,
            "area_of_focus": project.area_of_focus,
        },
        request=request,
    )
    return project


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
