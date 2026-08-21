from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import HubBooking


class BookingError(Exception):
    pass


@transaction.atomic
def create_booking(innovator, *, visit_date, arrival_time, purpose):
    locked_user = User.objects.select_for_update().get(pk=innovator.pk)
    if locked_user.role != User.Role.INNOVATOR:
        raise BookingError("Only innovators can make hub bookings.")
    if visit_date < timezone.localdate():
        raise BookingError("Choose today or a future date.")
    if HubBooking.objects.filter(innovator=locked_user, visit_date=visit_date).exists():
        raise BookingError("You already have a hub booking for this date.")

    booking = HubBooking(
        innovator=locked_user,
        visit_date=visit_date,
        arrival_time=arrival_time,
        purpose=purpose.strip(),
    )
    booking.full_clean(validate_unique=False, validate_constraints=False)
    try:
        booking.save()
    except IntegrityError as exc:
        raise BookingError("You already have a hub booking for this date.") from exc
    return booking


@transaction.atomic
def admit_booking(administrator, booking, *, now=None, request=None):
    now = now or timezone.now()
    locked_booking = HubBooking.objects.select_for_update().select_related(
        "innovator", "admitted_by"
    ).get(pk=booking.pk)
    if administrator.role != User.Role.ADMIN:
        raise BookingError("Only an administrator can admit a hub booking.")
    if locked_booking.status == HubBooking.Status.ADMITTED:
        raise BookingError("This innovator has already been admitted for this booking.")
    if locked_booking.visit_date != timezone.localdate(now):
        raise BookingError("Only today's bookings can be admitted.")

    locked_booking.status = HubBooking.Status.ADMITTED
    locked_booking.admitted_at = now
    locked_booking.admitted_by = administrator
    locked_booking.full_clean()
    locked_booking.save(update_fields=["status", "admitted_at", "admitted_by", "updated_at"])
    record_audit(
        actor=administrator,
        action=AuditLog.Action.BOOKING_ADMITTED,
        target=locked_booking,
        previous_values={"status": HubBooking.Status.BOOKED},
        new_values={"status": HubBooking.Status.ADMITTED, "admitted_at": now.isoformat()},
        request=request,
    )
    return locked_booking
