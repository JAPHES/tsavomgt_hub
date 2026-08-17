from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditlog.models import AuditLog
from core.tests.factories import create_admin, create_innovator

from attendance.forms import AttendanceCorrectionForm
from attendance.models import AttendanceCorrection, AttendanceSession
from attendance.services import AttendanceError, check_in, check_out, correct_attendance


class AttendanceServiceTests(TestCase):
    def setUp(self):
        self.user = create_innovator()

    def test_successful_check_in_uses_server_time(self):
        now = timezone.now()
        session, stale = check_in(
            self.user,
            project_name="BlueWatch",
            planned_activity="Develop and test the dumpsite reporting form.",
            now=now,
        )
        self.assertIsNone(stale)
        self.assertEqual(session.check_in_at, now)
        self.assertEqual(session.status, AttendanceSession.Status.ACTIVE)

    def test_duplicate_active_check_in_is_prevented(self):
        check_in(
            self.user,
            project_name="BlueWatch",
            planned_activity="Develop and test the dumpsite reporting form.",
        )
        with self.assertRaises(AttendanceError):
            check_in(
                self.user,
                project_name="BlueWatch",
                planned_activity="Attempt a duplicate active check in.",
            )
        self.assertEqual(
            AttendanceSession.objects.filter(status=AttendanceSession.Status.ACTIVE).count(), 1
        )

    def test_database_constraint_rejects_two_active_sessions(self):
        AttendanceSession.objects.create(
            innovator=self.user,
            project_name="BlueWatch",
            planned_activity="First valid activity description.",
            check_in_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceSession.objects.create(
                innovator=self.user,
                project_name="Second",
                planned_activity="Second invalid active session.",
                check_in_at=timezone.now(),
            )

    def test_successful_checkout_and_duration(self):
        start = timezone.now() - timedelta(hours=2, minutes=15)
        session, _ = check_in(
            self.user,
            project_name="BlueWatch",
            planned_activity="Develop and test the dumpsite reporting form.",
            now=start,
        )
        finished = start + timedelta(hours=2, minutes=15)
        session = check_out(
            self.user,
            work_completed="Completed the form and tested image submissions.",
            challenges_encountered="Slow test network.",
            next_step="Deploy to staging.",
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
            planned_activity="Develop and test the dumpsite reporting form.",
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
            planned_activity="Validate reversed timestamps in the model.",
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
            planned_activity="Work that was not checked out correctly.",
            check_in_at=yesterday,
        )
        new_session, stale = check_in(
            self.user,
            project_name="BlueWatch",
            planned_activity="Start a valid activity on the new local day.",
            now=timezone.now(),
        )
        previous.refresh_from_db()
        self.assertEqual(stale, previous)
        self.assertEqual(previous.status, AttendanceSession.Status.INCOMPLETE)
        self.assertEqual(new_session.status, AttendanceSession.Status.ACTIVE)
        self.assertIsNone(previous.check_out_at)


class AttendanceCorrectionTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.user = create_innovator()
        self.session = AttendanceSession.objects.create(
            innovator=self.user,
            project_name="BlueWatch",
            planned_activity="Record a deliberately incomplete visit.",
            check_in_at=timezone.now() - timedelta(days=1),
            status=AttendanceSession.Status.INCOMPLETE,
        )

    def test_administrator_correction_records_history_and_audit(self):
        checkout = self.session.check_in_at + timedelta(hours=3)
        corrected = correct_attendance(
            self.session.pk,
            {
                "check_in_at": self.session.check_in_at,
                "check_out_at": checkout,
                "status": AttendanceSession.Status.ADMIN_CLOSED,
                "work_completed": "Administrator confirmed the work from signed notes.",
                "correction_reason": "Confirmed against the signed physical attendance register.",
            },
            administrator=self.admin,
        )
        self.assertEqual(corrected.check_out_at, checkout)
        self.assertEqual(corrected.corrected_by, self.admin)
        self.assertEqual(AttendanceCorrection.objects.filter(attendance=corrected).count(), 1)
        audit = AuditLog.objects.get(
            action=AuditLog.Action.ATTENDANCE_CORRECTED, target_id=str(corrected.pk)
        )
        self.assertEqual(audit.actor, self.admin)
        self.assertIn("physical attendance", audit.reason)

    def test_correction_requires_reason(self):
        form = AttendanceCorrectionForm(
            data={
                "check_in_at": timezone.localtime(self.session.check_in_at).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "check_out_at": "",
                "status": AttendanceSession.Status.INCOMPLETE,
                "work_completed": "",
                "correction_reason": "",
            },
            instance=self.session,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("correction_reason", form.errors)


class AttendanceViewTests(TestCase):
    def setUp(self):
        self.user = create_innovator()
        self.client.force_login(self.user)

    def test_innovator_cannot_supply_checkin_timestamp(self):
        fake_time = timezone.now() - timedelta(days=100)
        response = self.client.post(
            reverse("attendance:check-in"),
            {
                "project_name": "BlueWatch",
                "planned_activity": "Develop the reporting workflow and test uploads.",
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
            planned_activity="Develop the reporting workflow and test uploads.",
        )
        original = session.check_in_at
        response = self.client.post(
            reverse("attendance:check-out"),
            {
                "work_completed": "Completed and tested the reporting workflow successfully.",
                "challenges_encountered": "",
                "next_step": "Deploy the workflow.",
                "check_in_at": (timezone.now() - timedelta(days=10)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.check_in_at, original)
