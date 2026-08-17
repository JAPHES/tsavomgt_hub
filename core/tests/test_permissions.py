from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceSession

from .factories import create_admin, create_innovator


class PermissionTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.innovator = create_innovator()
        self.other = create_innovator(
            email="other@students.ttu.ac.ke",
            registration_number="TTU/INN/002",
            first_name="Peter",
            last_name="Mwashighadi",
        )
        self.other_session = AttendanceSession.objects.create(
            innovator=self.other,
            project_name="AgriSense",
            planned_activity="Test moisture sensor calibration in the lab.",
            check_in_at=timezone.now(),
        )

    def test_innovator_cannot_access_admin_dashboard_or_create_accounts(self):
        self.client.force_login(self.innovator)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 403)
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("attendance:correct", kwargs={"pk": self.other_session.pk})
            ).status_code,
            403,
        )

    def test_innovator_cannot_see_another_innovators_attendance(self):
        self.client.force_login(self.innovator)
        response = self.client.get(
            reverse("attendance:detail", kwargs={"pk": self.other_session.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_administrator_can_access_management_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 200)
        self.assertEqual(self.client.get(reverse("innovators:manage")).status_code, 200)
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:live-attendance")).status_code, 200)
        self.assertEqual(self.client.get(reverse("auditlog:list")).status_code, 200)
