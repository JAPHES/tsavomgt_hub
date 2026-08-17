from datetime import timedelta

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
        self.assertEqual(response.context["summary"]["currently_in_hub"], 1)
        self.assertEqual(response.context["summary"]["visitors_today"], 1)

    def test_todays_completed_visits_and_hours_are_displayed(self):
        start = timezone.now() - timedelta(hours=3)
        self.create_session(
            check_in_at=start,
            check_out_at=start + timedelta(hours=2),
            work_completed="Completed reporting form and validated image submissions.",
            status=AttendanceSession.Status.COMPLETED,
        )
        response = self.client.get(reverse("dashboard:admin"))
        self.assertContains(response, "Completed reporting form")
        self.assertEqual(response.context["summary"]["checked_out_today"], 1)
        self.assertAlmostEqual(response.context["summary"]["hours_today"], 2.0)

    def test_incomplete_sessions_are_displayed(self):
        self.create_session(
            check_in_at=timezone.now() - timedelta(days=1),
            status=AttendanceSession.Status.INCOMPLETE,
        )
        response = self.client.get(reverse("dashboard:admin"))
        self.assertContains(response, "Incomplete Sessions")
        self.assertContains(response, self.user.get_full_name())
        self.assertEqual(response.context["summary"]["incomplete"], 1)

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
