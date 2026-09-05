import logging

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string

from accounts.models import User
from accounts.services import issue_temporary_credentials
from attendance.models import AttendanceCorrection, AttendanceSession, HubBooking
from auditlog.models import AuditLog
from auditlog.services import client_ip, record_audit

from .models import InnovatorProfile, InnovatorProject

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    pass


class InnovatorDeletionError(Exception):
    pass


def _delete_profile_photo(storage, name):
    try:
        storage.delete(name)
    except Exception:
        logger.exception("Could not delete innovator profile photo %s.", name)


def _session_keys_for_user(user_id):
    session_keys = []
    for session in Session.objects.all().iterator():
        if str(session.get_decoded().get(SESSION_KEY, "")) == str(user_id):
            session_keys.append(session.session_key)
    return session_keys


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


@transaction.atomic
def permanently_delete_innovator(profile, *, actor, request=None):
    locked_profile = (
        InnovatorProfile.objects.select_for_update().select_related("user").get(pk=profile.pk)
    )
    user = User.objects.select_for_update().get(pk=locked_profile.user_id)
    if actor.role != User.Role.ADMIN:
        raise InnovatorDeletionError("Only an administrator can permanently delete an innovator.")
    if user.role != User.Role.INNOVATOR:
        raise InnovatorDeletionError("Only innovator accounts can be permanently deleted here.")

    project_ids = list(locked_profile.projects.values_list("pk", flat=True))
    booking_ids = list(user.hub_bookings.values_list("pk", flat=True))
    attendance_ids = list(user.attendance_sessions.values_list("pk", flat=True))
    correction_ids = list(
        AttendanceCorrection.objects.filter(
            Q(attendance_id__in=attendance_ids) | Q(administrator=user)
        ).values_list("pk", flat=True)
    )
    session_keys = _session_keys_for_user(user.pk)

    related_audits = Q(actor=user) | Q(
        target_model=User._meta.label,
        target_id=str(user.pk),
    ) | Q(
        target_model=InnovatorProfile._meta.label,
        target_id=str(locked_profile.pk),
    )
    for model, object_ids in (
        (InnovatorProject, project_ids),
        (HubBooking, booking_ids),
        (AttendanceSession, attendance_ids),
        (AttendanceCorrection, correction_ids),
    ):
        if object_ids:
            related_audits |= Q(
                target_model=model._meta.label,
                target_id__in=[str(object_id) for object_id in object_ids],
            )

    deleted_counts = {
        "projects": len(project_ids),
        "bookings": len(booking_ids),
        "attendance_records": len(attendance_ids),
        "attendance_corrections": len(correction_ids),
        "audit_records": AuditLog.objects.filter(related_audits).count(),
        "login_sessions": len(session_keys),
    }
    photo_name = locked_profile.profile_photo.name
    photo_storage = locked_profile.profile_photo.storage if photo_name else None

    AuditLog.objects.filter(related_audits).delete()
    AttendanceCorrection.objects.filter(pk__in=correction_ids).delete()
    AttendanceSession.objects.filter(pk__in=attendance_ids).delete()
    HubBooking.objects.filter(pk__in=booking_ids).delete()
    InnovatorProject.objects.filter(pk__in=project_ids).delete()
    Session.objects.filter(session_key__in=session_keys).delete()
    locked_profile.delete()
    user.delete()

    AuditLog.objects.create(
        actor=actor,
        action=AuditLog.Action.ACCOUNT_DELETED,
        target_model=User._meta.label,
        target_id="",
        target_repr="Deleted innovator account",
        new_values={"deleted_records": deleted_counts},
        reason="Administrator confirmed permanent innovator deletion",
        ip_address=client_ip(request),
    )
    if photo_name:
        transaction.on_commit(
            lambda: _delete_profile_photo(photo_storage, photo_name),
        )
    return deleted_counts


def send_deactivation_email(user):
    context = {
        "user": user,
        "support_email": settings.SUPPORT_EMAIL,
        "assistant_support_email": settings.ASSISTANT_SUPPORT_EMAIL,
        "support_phone": settings.SUPPORT_PHONE,
    }
    text_body = render_to_string("emails/account_deactivation.txt", context)
    html_body = render_to_string("emails/account_deactivation.html", context)
    reply_to = [settings.SUPPORT_EMAIL] if settings.SUPPORT_EMAIL else None
    message = EmailMultiAlternatives(
        "Your Tsavo Hub account has been deactivated",
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        reply_to=reply_to,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
