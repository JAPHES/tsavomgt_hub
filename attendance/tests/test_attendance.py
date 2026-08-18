from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.factories import create_admin, create_innovator

from attendance.models import AttendanceSession
from attendance.services import AttendanceError, check_in, check_out


class AttendanceServiceTests(TestCase):
    def setUp(self):
        self.user = create_innovator()

    def test_successful_check_in_uses_server_time(self):
        now = timezone.now()
        session, stale = check_in(
            self.user,
            project_name="BlueWatch",
            now=now,
        )
        self.assertIsNone(stale)
        self.assertEqual(session.check_in_at, now)
        self.assertEqual(session.status, AttendanceSession.Status.ACTIVE)

    def test_duplicate_active_check_in_is_prevented(self):
        check_in(
            self.user,
            project_name="BlueWatch",
        )
        with self.assertRaises(AttendanceError):
            check_in(
                self.user,
                project_name="BlueWatch",
            )
        self.assertEqual(
            AttendanceSession.objects.filter(status=AttendanceSession.Status.ACTIVE).count(), 1
        )

    def test_database_constraint_rejects_two_active_sessions(self):
        AttendanceSession.objects.create(
            innovator=self.user,
            project_name="BlueWatch",
            check_in_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceSession.objects.create(
                innovator=self.user,
                project_name="Second",
                check_in_at=timezone.now(),
            )

    def test_successful_checkout_and_duration(self):
        start = timezone.now() - timedelta(hours=2, minutes=15)
        session, _ = check_in(
            self.user,
            project_name="BlueWatch",
            now=start,
        )
        finished = start + timedelta(hours=2, minutes=15)
        session = check_out(
            self.user,
            work_completed="Completed the form and tested image submissions.",
            challenges_encountered="Slow test network.",
            now=finished,
        )
        self.assertEqual(session.status, AttendanceSession.Status.COMPLETED)
        self.assertEqual(session.check_out_at, finished)
        self.assertEqual(session.duration, timedelta(hours=2, minutes=15))
        self.assertAlmostEqual(session.duration_hours, 2.25)

    def test_checkout_without_active_session_is_prevented(self):
        with self.assertRaises(AttendanceError):
            check_out(self.user, work_completed="No active work could be completed today.")

    def test_checkout_time_validation(self):
        start = timezone.now()
        check_in(
            self.user,
            project_name="BlueWatch",
            now=start,
        )
        with self.assertRaises(AttendanceError):
            check_out(
                self.user,
                work_completed="This should fail due to its checkout time.",
                now=start - timedelta(minutes=1),
            )
        invalid = AttendanceSession(
            innovator=self.user,
            project_name="Invalid",
            check_in_at=start,
            check_out_at=start - timedelta(minutes=1),
            status=AttendanceSession.Status.COMPLETED,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_previous_day_active_session_is_marked_incomplete(self):
        yesterday = timezone.now() - timedelta(days=1)
        previous = AttendanceSession.objects.create(
            innovator=self.user,
            project_name="Old project",
            check_in_at=yesterday,
        )
        new_session, stale = check_in(
            self.user,
            project_name="BlueWatch",
            now=timezone.now(),
        )
        previous.refresh_from_db()
        self.assertEqual(stale, previous)
        self.assertEqual(previous.status, AttendanceSession.Status.INCOMPLETE)
        self.assertEqual(new_session.status, AttendanceSession.Status.ACTIVE)
        self.assertIsNone(previous.check_out_at)


class AttendanceAdministratorReadOnlyTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.user = create_innovator()
        self.session = AttendanceSession.objects.create(
            innovator=self.user,
            project_name="BlueWatch",
            check_in_at=timezone.now() - timedelta(days=1),
            status=AttendanceSession.Status.INCOMPLETE,
        )
        self.client.force_login(self.admin)

    def test_administrator_can_view_record_without_correction_action(self):
        response = self.client.get(
            reverse("attendance:admin-detail", kwargs={"pk": self.session.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session timing")
        self.assertNotContains(response, "Correct record")

    def test_removed_correction_url_cannot_modify_record(self):
        original_check_in = self.session.check_in_at
        correction_url = f"/attendance/session/{self.session.pk}/correct/"
        response = self.client.post(
            correction_url,
            {
                "check_in_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                "status": AttendanceSession.Status.COMPLETED,
                "work_completed": "Attempted modification",
                "correction_reason": "Attempted correction",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.session.refresh_from_db()
        self.assertEqual(self.session.check_in_at, original_check_in)
        self.assertEqual(self.session.status, AttendanceSession.Status.INCOMPLETE)


class AttendanceViewTests(TestCase):
    def setUp(self):
        self.user = create_innovator()
        self.client.force_login(self.user)

    def test_attendance_history_uses_centered_records_layout(self):
        response = self.client.get(reverse("attendance:history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="attendance-history-heading"')
        self.assertContains(response, "Official session times and documented activities")
        self.assertContains(response, "0 attendance records")

    def test_innovator_cannot_supply_checkin_timestamp(self):
        fake_time = timezone.now() - timedelta(days=100)
        response = self.client.post(
            reverse("attendance:check-in"),
            {
                "project_name": "BlueWatch",
                "check_in_at": fake_time.isoformat(),
            },
        )
        self.assertRedirects(response, reverse("dashboard:innovator"))
        session = AttendanceSession.objects.get(innovator=self.user)
        self.assertGreater(session.check_in_at, timezone.now() - timedelta(minutes=1))

    def test_checkout_form_does_not_modify_checkin_timestamp(self):
        session, _ = check_in(
            self.user,
            project_name="BlueWatch",
        )
        original = session.check_in_at
        response = self.client.post(
            reverse("attendance:check-out"),
            {
                "work_completed": "Completed and tested the reporting workflow successfully.",
                "challenges_encountered": "",
                "check_in_at": (timezone.now() - timedelta(days=10)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.check_in_at, original)
