from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceSession
from core.tests.factories import create_admin, create_innovator


class AdministratorDashboardTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.user = create_innovator()
        self.client.force_login(self.admin)

    def create_session(self, **overrides):
        values = {
            "innovator": self.user,
            "project_name": "BlueWatch",
            "planned_activity": "Develop the dumpsite reporting form and test uploads.",
            "check_in_at": timezone.now() - timedelta(hours=2),
            "status": AttendanceSession.Status.ACTIVE,
        }
        values.update(overrides)
        return AttendanceSession.objects.create(**values)

    def test_current_visitors_are_displayed_and_summary_is_accurate(self):
        self.create_session()
        response = self.client.get(reverse("dashboard:admin"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.get_full_name())
        self.assertEqual(
            response.context["summary"], {"active_innovators": 1, "attended_today": 1}
        )

    def test_completed_visits_are_displayed_on_todays_dashboard(self):
        start = timezone.now() - timedelta(hours=3)
        self.create_session(
            check_in_at=start,
            check_out_at=start + timedelta(hours=2),
            work_completed="Completed reporting form and validated image submissions.",
            status=AttendanceSession.Status.COMPLETED,
        )
        response = self.client.get(reverse("dashboard:admin"))
        self.assertContains(response, "Completed reporting form")
        self.assertEqual(response.context["summary"]["attended_today"], 1)

    def test_incomplete_sessions_are_not_displayed_on_live_dashboard(self):
        self.create_session(
            check_in_at=timezone.now() - timedelta(days=1),
            status=AttendanceSession.Status.INCOMPLETE,
        )
        response = self.client.get(reverse("dashboard:admin"))
        self.assertNotContains(response, "Incomplete Sessions")
        self.assertNotContains(response, self.user.get_full_name())
        self.assertEqual(response.context["summary"]["attended_today"], 0)

    def test_filter_uses_only_innovator_name_and_returns_correct_records(self):
        matching = self.create_session(status=AttendanceSession.Status.INCOMPLETE)
        other_user = create_innovator(
            email="other@example.com",
            registration_number="TTU/INN/007",
            project="AgriSense",
            first_name="Peter",
            last_name="Mwangi",
        )
        AttendanceSession.objects.create(
            innovator=other_user,
            project_name="AgriSense",
            planned_activity="Calibrate the soil moisture sensing prototype.",
            check_in_at=timezone.now(),
            status=AttendanceSession.Status.ACTIVE,
        )
        response = self.client.get(
            reverse("dashboard:live-attendance"),
            {"innovator_name": "Amina Juma"},
        )
        self.assertEqual(list(response.context["form"].fields), ["innovator_name"])
        self.assertEqual(list(response.context["page_obj"].object_list), [matching])
        self.assertContains(response, "BlueWatch")
        self.assertNotContains(response, "AgriSense")


class InnovatorDashboardTests(TestCase):
    def test_innovator_sees_active_session_and_week_totals(self):
        user = create_innovator()
        start = timezone.now() - timedelta(hours=1)
        AttendanceSession.objects.create(
            innovator=user,
            project_name="BlueWatch",
            planned_activity="Build the reporting form interface and validation.",
            check_in_at=start,
            check_out_at=start + timedelta(minutes=30),
            work_completed="Built and tested the interface validation.",
            status=AttendanceSession.Status.COMPLETED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:innovator"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["visits_this_week"], 1)
        self.assertAlmostEqual(response.context["hours_this_week"], 0.5)

    def test_innovator_can_submit_required_daily_attendance_form(self):
        user = create_innovator()
        self.client.force_login(user)
        local_now = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(18, 0)),
            timezone.get_current_timezone(),
        )
        with patch("attendance.forms.timezone.localtime", return_value=local_now):
            response = self.client.post(
                reverse("dashboard:innovator"),
                {
                    "arrival_time": "10:00",
                    "departure_time": "12:00",
                    "work_completed": "Completed the reporting form and tested all required validations.",
                    "challenges_encountered": "",
                },
            )
        session = AttendanceSession.objects.get(innovator=user)
        self.assertRedirects(
            response, reverse("attendance:detail", kwargs={"pk": session.pk})
        )
        self.assertEqual(session.status, AttendanceSession.Status.COMPLETED)
        self.assertEqual(timezone.localtime(session.check_in_at).strftime("%H:%M"), "10:00")
        self.assertEqual(timezone.localtime(session.check_out_at).strftime("%H:%M"), "12:00")
        self.assertEqual(session.challenges_encountered, "")

    def test_daily_attendance_requires_times_and_work_and_valid_order(self):
        user = create_innovator()
        self.client.force_login(user)
        response = self.client.post(
            reverse("dashboard:innovator"),
            {
                "arrival_time": "15:00",
                "departure_time": "14:00",
                "work_completed": "",
                "challenges_encountered": "Optional challenge",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departure time must be later than arrival time")
        self.assertIn("work_completed", response.context["attendance_form"].errors)
        self.assertFalse(AttendanceSession.objects.filter(innovator=user).exists())
