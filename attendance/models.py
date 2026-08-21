from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class AttendanceSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        INCOMPLETE = "INCOMPLETE", "Incomplete"
        ADMIN_CLOSED = "ADMIN_CLOSED", "Closed by administrator"

    innovator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_sessions"
    )
    project_name = models.CharField(max_length=200)
    work_completed = models.TextField(blank=True)
    challenges_encountered = models.TextField(blank=True)
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corrected_attendance_sessions",
    )
    correction_reason = models.TextField(blank=True)
    corrected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-check_in_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["innovator"],
                condition=Q(status="ACTIVE"),
                name="unique_active_session_per_innovator",
            ),
            models.CheckConstraint(
                condition=Q(check_out_at__isnull=True) | Q(check_out_at__gte=F("check_in_at")),
                name="checkout_not_before_checkin",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "check_in_at"]),
            models.Index(fields=["innovator", "check_in_at"]),
        ]

    def clean(self):
        errors = {}
        if self.innovator_id and self.innovator.role != self.innovator.Role.INNOVATOR:
            errors["innovator"] = "Attendance can only be recorded for an innovator."
        if self.check_out_at and self.check_out_at < self.check_in_at:
            errors["check_out_at"] = "Check-out time cannot be earlier than check-in time."
        if self.status == self.Status.COMPLETED and not self.check_out_at:
            errors["check_out_at"] = "A completed session requires a check-out time."
        if self.status == self.Status.ACTIVE and self.check_out_at:
            errors["status"] = "An active session cannot have a check-out time."
        if errors:
            raise ValidationError(errors)

    @property
    def duration(self):
        if not self.check_out_at or self.check_out_at < self.check_in_at:
            return None
        return self.check_out_at - self.check_in_at

    @property
    def duration_hours(self):
        duration = self.duration
        return duration.total_seconds() / 3600 if duration else 0

    @property
    def local_date(self):
        return timezone.localtime(self.check_in_at).date()

    def __str__(self):
        return f"{self.innovator} - {timezone.localtime(self.check_in_at):%Y-%m-%d %H:%M}"


class AttendanceCorrection(models.Model):
    attendance = models.ForeignKey(
        AttendanceSession, on_delete=models.PROTECT, related_name="corrections"
    )
    administrator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_corrections"
    )
    previous_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Correction to session {self.attendance_id} by {self.administrator}"


class HubBooking(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        ADMITTED = "ADMITTED", "Admitted"

    innovator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hub_bookings",
    )
    visit_date = models.DateField()
    arrival_time = models.TimeField()
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)
    admitted_at = models.DateTimeField(null=True, blank=True)
    admitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="admitted_hub_bookings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-visit_date", "-arrival_time", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["innovator", "visit_date"],
                name="unique_daily_booking_per_innovator",
                violation_error_message="You already have a hub booking for this date.",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="BOOKED", admitted_at__isnull=True, admitted_by__isnull=True)
                    | Q(
                        status="ADMITTED",
                        admitted_at__isnull=False,
                        admitted_by__isnull=False,
                    )
                ),
                name="booking_admission_fields_match_status",
            ),
        ]
        indexes = [
            models.Index(fields=["visit_date", "status", "arrival_time"]),
            models.Index(fields=["innovator", "visit_date"]),
        ]

    def clean(self):
        errors = {}
        if self.innovator_id and self.innovator.role != self.innovator.Role.INNOVATOR:
            errors["innovator"] = "Hub bookings can only be made for an innovator."
        if self.status == self.Status.BOOKED and (self.admitted_at or self.admitted_by_id):
            errors["status"] = "A booked visit cannot contain admission details."
        if self.status == self.Status.ADMITTED:
            if not self.admitted_at:
                errors["admitted_at"] = "An admitted booking requires an admission time."
            if not self.admitted_by_id:
                errors["admitted_by"] = "An admitted booking requires an administrator."
            elif self.admitted_by.role != self.admitted_by.Role.ADMIN:
                errors["admitted_by"] = "Only an administrator can admit a booking."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.innovator} - {self.visit_date:%Y-%m-%d} at {self.arrival_time:%H:%M}"
