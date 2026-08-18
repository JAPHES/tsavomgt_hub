import csv
import io

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
            check_in_at=timezone.now(),
        )

    def test_innovator_cannot_access_admin_dashboard_or_create_accounts(self):
        self.client.force_login(self.innovator)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 403)
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("innovators:export")).status_code, 403)
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

    def test_innovator_can_view_own_structured_attendance_record(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("attendance:detail", kwargs={"pk": self.other_session.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session timing")
        self.assertContains(response, "Activity record")
        self.assertContains(response, "Back to attendance history")

    def test_innovator_can_view_professional_own_profile(self):
        self.client.force_login(self.innovator)
        response = self.client.get(reverse("innovators:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact details")
        self.assertContains(response, "My project")
        self.assertContains(response, self.innovator.innovator_profile.registration_number)

    def test_administrator_can_access_management_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 200)
        manage_response = self.client.get(reverse("innovators:manage"))
        self.assertEqual(manage_response.status_code, 200)
        self.assertContains(manage_response, "Download innovators")
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:live-attendance")).status_code, 200)
        self.assertEqual(self.client.get(reverse("auditlog:list")).status_code, 200)
        session_response = self.client.get(
            reverse("attendance:admin-detail", kwargs={"pk": self.other_session.pk})
        )
        self.assertContains(session_response, "Correct record")
        self.assertContains(session_response, "Back to innovator record")

    def test_administrator_can_download_all_innovators_as_csv(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("innovators:export"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["Full name", "Email", "Project"])
        self.assertEqual(len(rows), 3)
        self.assertIn(
            [
                self.innovator.get_full_name(),
                self.innovator.email,
                self.innovator.innovator_profile.innovation_project_name,
            ],
            rows,
        )
        self.assertIn(
            [
                self.other.get_full_name(),
                self.other.email,
                self.other.innovator_profile.innovation_project_name,
            ],
            rows,
        )

    def test_administrator_innovator_record_shows_profile_and_attendance_summary(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("innovators:detail", kwargs={"pk": self.other.innovator_profile.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other.get_full_name())
        self.assertContains(response, "Innovation project")
        self.assertContains(response, "Critical account action")
        self.assertContains(response, "Are you sure you want to continue?")
        self.assertContains(response, "Yes, deactivate account")
        self.assertEqual(response.context["attendance_count"], 1)
