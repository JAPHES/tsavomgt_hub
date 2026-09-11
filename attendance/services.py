import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditLog
from auditlog.services import record_audit

from .models import HubBooking


logger = logging.getLogger(__name__)


class BookingError(Exception):
    pass


class BookingNotificationError(BookingError):
    pass


@transaction.atomic
def create_booking(innovator, *, visit_date, arrival_time, purpose):
    locked_user = User.objects.select_for_update().get(pk=innovator.pk)
    if locked_user.role != User.Role.INNOVATOR:
        raise BookingError("Only innovators can make hub bookings.")
    if visit_date < timezone.localdate():
        raise BookingError("Choose today or a future date.")
    if HubBooking.objects.filter(
        innovator=locked_user,
        visit_date=visit_date,
    ).exclude(status=HubBooking.Status.CANCELLED).exists():
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
def update_booking(innovator, booking, *, visit_date, arrival_time, purpose, request=None):
    locked_booking = HubBooking.objects.select_for_update().get(pk=booking.pk)
    if innovator.role != User.Role.INNOVATOR or locked_booking.innovator_id != innovator.pk:
        raise BookingError("You can only update your own hub bookings.")
    if locked_booking.status != HubBooking.Status.BOOKED:
        raise BookingError("Only a booking awaiting admission can be updated.")
    if visit_date < timezone.localdate():
        raise BookingError("Choose today or a future date.")
    duplicate = HubBooking.objects.filter(
        innovator=innovator,
        visit_date=visit_date,
    ).exclude(status=HubBooking.Status.CANCELLED).exclude(pk=locked_booking.pk)
    if duplicate.exists():
        raise BookingError("You already have a hub booking for this date.")

    previous_values = {
        "visit_date": locked_booking.visit_date.isoformat(),
        "arrival_time": locked_booking.arrival_time.isoformat(),
        "purpose": locked_booking.purpose,
    }
    locked_booking.visit_date = visit_date
    locked_booking.arrival_time = arrival_time
    locked_booking.purpose = purpose.strip()
    locked_booking.full_clean(validate_unique=False, validate_constraints=False)
    try:
        locked_booking.save(
            update_fields=["visit_date", "arrival_time", "purpose", "updated_at"]
        )
    except IntegrityError as exc:
        raise BookingError("You already have a hub booking for this date.") from exc
    record_audit(
        actor=innovator,
        action=AuditLog.Action.BOOKING_UPDATED,
        target=locked_booking,
        previous_values=previous_values,
        new_values={
            "visit_date": locked_booking.visit_date.isoformat(),
            "arrival_time": locked_booking.arrival_time.isoformat(),
            "purpose": locked_booking.purpose,
        },
        request=request,
    )
    return locked_booking


@transaction.atomic
def admit_booking(administrator, booking, *, now=None, request=None):
    now = now or timezone.now()
    locked_booking = HubBooking.objects.select_for_update().get(pk=booking.pk)
    if administrator.role != User.Role.ADMIN:
        raise BookingError("Only an administrator can admit a hub booking.")
    if locked_booking.status == HubBooking.Status.ADMITTED:
        raise BookingError("This innovator has already been admitted for this booking.")
    if locked_booking.status == HubBooking.Status.CANCELLED:
        raise BookingError("A cancelled booking cannot be admitted.")
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


@transaction.atomic
def cancel_booking(administrator, booking, *, reason, now=None, request=None):
    now = now or timezone.now()
    reason = " ".join(reason.split())
    locked_booking = HubBooking.objects.select_for_update().get(pk=booking.pk)
    if administrator.role != User.Role.ADMIN:
        raise BookingError("Only an administrator can cancel a hub booking.")
    if locked_booking.status == HubBooking.Status.ADMITTED:
        raise BookingError("An admitted booking cannot be cancelled.")
    if locked_booking.status == HubBooking.Status.CANCELLED:
        raise BookingError("This booking has already been cancelled.")
    if len(reason) < 10:
        raise BookingError("Give a clear reason for cancelling this booking.")

    locked_booking.status = HubBooking.Status.CANCELLED
    locked_booking.cancelled_at = now
    locked_booking.cancelled_by = administrator
    locked_booking.cancellation_reason = reason
    locked_booking.full_clean()
    locked_booking.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "updated_at",
        ]
    )
    record_audit(
        actor=administrator,
        action=AuditLog.Action.BOOKING_CANCELLED,
        target=locked_booking,
        previous_values={"status": HubBooking.Status.BOOKED},
        new_values={
            "status": HubBooking.Status.CANCELLED,
            "cancelled_at": now.isoformat(),
        },
        reason=reason,
        request=request,
    )
    return locked_booking


def send_booking_cancellation_email(booking):
    user = booking.innovator
    context = {
        "booking": booking,
        "user": user,
        "booking_history_url": f"{settings.SITE_URL}{reverse('attendance:booking-history')}",
        "support_email": settings.SUPPORT_EMAIL,
        "assistant_support_email": settings.ASSISTANT_SUPPORT_EMAIL,
        "support_phone": settings.SUPPORT_PHONE,
    }
    text_body = render_to_string("emails/booking_cancelled.txt", context)
    html_body = render_to_string("emails/booking_cancelled.html", context)
    reply_to = [settings.SUPPORT_EMAIL] if settings.SUPPORT_EMAIL else None
    message = EmailMultiAlternatives(
        f"Your Tsavo Hub visit on {booking.visit_date:%d %B %Y} was cancelled",
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        reply_to=reply_to,
    )
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception(
            "Booking-cancellation email delivery failed for booking_id=%s.",
            booking.pk,
        )
        raise BookingNotificationError(
            "The booking was cancelled, but the notification email could not be delivered."
        ) from exc
