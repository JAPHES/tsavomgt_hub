from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceSession, HubBooking
from attendance.services import BookingError, admit_booking, create_booking
from auditlog.models import AuditLog
from core.tests.factories import create_admin, create_innovator


class HubBookingServiceTests(TestCase):
    def setUp(self):
        self.innovator = create_innovator()
        self.admin = create_admin()

    def test_booking_is_created_with_trimmed_purpose(self):
        visit_date = timezone.localdate() + timedelta(days=1)
        booking = create_booking(
            self.innovator,
            visit_date=visit_date,
            arrival_time=time(10, 15),
            purpose="  Test the sensor calibration workflow.  ",
        )

        self.assertEqual(booking.visit_date, visit_date)
        self.assertEqual(booking.purpose, "Test the sensor calibration workflow.")
        self.assertEqual(booking.status, HubBooking.Status.BOOKED)

    def test_duplicate_daily_booking_is_rejected_by_service_and_database(self):
        visit_date = timezone.localdate() + timedelta(days=1)
        create_booking(
            self.innovator,
            visit_date=visit_date,
            arrival_time=time(9, 0),
            purpose="Test the first version of the monitoring device.",
        )
        with self.assertRaises(BookingError):
            create_booking(
                self.innovator,
                visit_date=visit_date,
                arrival_time=time(14, 0),
                purpose="Continue testing the monitoring device in the hub.",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            HubBooking.objects.create(
                innovator=self.innovator,
                visit_date=visit_date,
                arrival_time=time(15, 0),
                purpose="Attempt a duplicate booking at the database boundary.",
            )

    def test_past_booking_is_rejected(self):
        with self.assertRaises(BookingError):
            create_booking(
                self.innovator,
                visit_date=timezone.localdate() - timedelta(days=1),
                arrival_time=time(10, 0),
                purpose="Attempt to create a booking in the past.",
            )

    def test_admission_uses_server_time_and_creates_audit_record(self):
        booking = create_booking(
            self.innovator,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Build and validate the booking admission workflow.",
        )
        now = timezone.now()
        admitted = admit_booking(self.admin, booking, now=now)

        self.assertEqual(admitted.status, HubBooking.Status.ADMITTED)
        self.assertEqual(admitted.admitted_at, now)
        self.assertEqual(admitted.admitted_by, self.admin)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                action=AuditLog.Action.BOOKING_ADMITTED,
                target_id=str(booking.pk),
            ).exists()
        )

    def test_future_booking_cannot_be_admitted(self):
        booking = create_booking(
            self.innovator,
            visit_date=timezone.localdate() + timedelta(days=1),
            arrival_time=time(10, 0),
            purpose="Prepare a future device validation session.",
        )
        with self.assertRaises(BookingError):
            admit_booking(self.admin, booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, HubBooking.Status.BOOKED)

    def test_innovator_cannot_admit_a_booking(self):
        booking = create_booking(
            self.innovator,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Confirm that admission remains an administrator action.",
        )
        with self.assertRaises(BookingError):
            admit_booking(self.innovator, booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, HubBooking.Status.BOOKED)

    def test_admitted_status_requires_admission_details(self):
        booking = HubBooking(
            innovator=self.innovator,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Validate admission field consistency.",
            status=HubBooking.Status.ADMITTED,
        )
        with self.assertRaises(ValidationError):
            booking.full_clean()


class BookingViewTests(TestCase):
    def setUp(self):
        self.innovator = create_innovator()
        self.client.force_login(self.innovator)

    def test_booking_history_is_scoped_to_logged_in_innovator(self):
        own_booking = HubBooking.objects.create(
            innovator=self.innovator,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Test the innovator's own device prototype.",
        )
        other = create_innovator(
            email="other@example.com", registration_number="TTU/INN/009"
        )
        HubBooking.objects.create(
            innovator=other,
            visit_date=timezone.localdate(),
            arrival_time=time(11, 0),
            purpose="This other innovator booking must remain private.",
        )

        response = self.client.get(reverse("attendance:booking-history"))

        self.assertEqual(list(response.context["page_obj"].object_list), [own_booking])
        self.assertContains(response, "own device prototype")
        self.assertNotContains(response, "must remain private")

    def test_old_self_attendance_endpoints_are_removed(self):
        self.assertEqual(self.client.get("/attendance/check-in/").status_code, 404)
        self.assertEqual(self.client.get("/attendance/check-out/").status_code, 404)


class LegacyAttendanceRetentionTests(TestCase):
    def test_administrator_can_still_view_a_legacy_attendance_record(self):
        administrator = create_admin()
        innovator = create_innovator()
        session = AttendanceSession.objects.create(
            innovator=innovator,
            project_name="BlueWatch",
            check_in_at=timezone.now() - timedelta(days=2),
            status=AttendanceSession.Status.INCOMPLETE,
        )
        self.client.force_login(administrator)

        response = self.client.get(
            reverse("attendance:admin-detail", kwargs={"pk": session.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session timing")
