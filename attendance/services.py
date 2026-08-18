from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import AttendanceCorrection, AttendanceSession


class AttendanceError(Exception):
    pass


def _snapshot(session):
    return {
        "check_in_at": session.check_in_at.isoformat() if session.check_in_at else None,
        "check_out_at": session.check_out_at.isoformat() if session.check_out_at else None,
        "status": session.status,
        "work_completed": session.work_completed,
    }


@transaction.atomic
def check_in(innovator, *, project_name, now=None):
    now = now or timezone.now()
    locked_user = User.objects.select_for_update().get(pk=innovator.pk)
    active = (
        AttendanceSession.objects.select_for_update()
        .filter(innovator=locked_user, status=AttendanceSession.Status.ACTIVE)
        .first()
    )
    stale_session = None
    if active:
        if timezone.localdate(active.check_in_at) == timezone.localdate(now):
            raise AttendanceError("You already have an active attendance session.")
        active.status = AttendanceSession.Status.INCOMPLETE
        active.save(update_fields=["status", "updated_at"])
        stale_session = active
        record_audit(
            actor=locked_user,
            action=AuditLog.Action.INCOMPLETE_SESSION_CLOSED,
            target=active,
            previous_values={"status": AttendanceSession.Status.ACTIVE},
            new_values={"status": AttendanceSession.Status.INCOMPLETE},
            reason="Automatically flagged when a new local day began without checkout.",
        )
    session = AttendanceSession(
        innovator=locked_user,
        project_name=project_name.strip(),
        check_in_at=now,
        status=AttendanceSession.Status.ACTIVE,
    )
    session.full_clean()
    try:
        session.save()
    except IntegrityError as exc:
        raise AttendanceError("You already have an active attendance session.") from exc
    return session, stale_session


@transaction.atomic
def check_out(innovator, *, work_completed, challenges_encountered="", now=None):
    now = now or timezone.now()
    locked_user = User.objects.select_for_update().get(pk=innovator.pk)
    session = (
        AttendanceSession.objects.select_for_update()
        .filter(innovator=locked_user, status=AttendanceSession.Status.ACTIVE)
        .first()
    )
    if not session:
        raise AttendanceError("There is no active session to check out from.")
    if now < session.check_in_at:
        raise AttendanceError("Check-out time cannot be earlier than check-in time.")
    session.work_completed = work_completed.strip()
    session.challenges_encountered = challenges_encountered.strip()
    session.check_out_at = now
    session.status = AttendanceSession.Status.COMPLETED
    session.full_clean()
    session.save(
        update_fields=[
            "work_completed",
            "challenges_encountered",
            "check_out_at",
            "status",
            "updated_at",
        ]
    )
    return session


@transaction.atomic
def record_daily_attendance(
    innovator, *, check_in_at, check_out_at, work_completed, challenges_encountered=""
):
    """Record the innovator's completed visit using their validated local times."""
    locked_user = User.objects.select_for_update().get(pk=innovator.pk)
    session = (
        AttendanceSession.objects.select_for_update()
        .filter(innovator=locked_user, status=AttendanceSession.Status.ACTIVE)
        .first()
    )
    if session is None:
        session = AttendanceSession(
            innovator=locked_user,
            project_name=locked_user.innovator_profile.innovation_project_name,
        )
    session.check_in_at = check_in_at
    session.check_out_at = check_out_at
    session.work_completed = work_completed.strip()
    session.challenges_encountered = challenges_encountered.strip()
    session.status = AttendanceSession.Status.COMPLETED
    session.full_clean()
    session.save()
    return session


@transaction.atomic
def correct_attendance(session_id, cleaned_data, *, administrator, request=None):
    session = AttendanceSession.objects.select_for_update().get(pk=session_id)
    previous = _snapshot(session)
    session.check_in_at = cleaned_data["check_in_at"]
    session.check_out_at = cleaned_data.get("check_out_at")
    session.status = cleaned_data["status"]
    session.work_completed = cleaned_data.get("work_completed", "").strip()
    session.correction_reason = cleaned_data["correction_reason"].strip()
    session.corrected_by = administrator
    session.corrected_at = timezone.now()
    try:
        session.full_clean()
        session.save()
    except (ValidationError, IntegrityError) as exc:
        raise AttendanceError("The correction conflicts with attendance rules.") from exc
    new = _snapshot(session)
    AttendanceCorrection.objects.create(
        attendance=session,
        administrator=administrator,
        previous_values=previous,
        new_values=new,
        reason=session.correction_reason,
    )
    record_audit(
        actor=administrator,
        action=AuditLog.Action.ATTENDANCE_CORRECTED,
        target=session,
        previous_values=previous,
        new_values=new,
        reason=session.correction_reason,
        request=request,
    )
    if (
        previous["status"] == AttendanceSession.Status.INCOMPLETE
        and session.status == AttendanceSession.Status.ADMIN_CLOSED
    ):
        record_audit(
            actor=administrator,
            action=AuditLog.Action.INCOMPLETE_SESSION_CLOSED,
            target=session,
            previous_values={"status": previous["status"]},
            new_values={"status": session.status},
            reason=session.correction_reason,
            request=request,
        )
    return session
