import csv
import io
from datetime import time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceSession, HubBooking
from innovators.models import InnovatorProject

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
        self.other_booking = HubBooking.objects.create(
            innovator=self.other,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Test the AgriSense monitoring prototype in the hub.",
        )

    def test_innovator_cannot_access_admin_dashboard_or_create_accounts(self):
        self.client.force_login(self.innovator)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 403)
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("innovators:export")).status_code, 403)
        self.assertEqual(
            self.client.get(
                f"/attendance/session/{self.other_session.pk}/correct/"
            ).status_code,
            404,
        )

    def test_innovator_cannot_see_another_innovators_bookings(self):
        self.client.force_login(self.innovator)
        response = self.client.get(reverse("attendance:booking-history"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "AgriSense monitoring prototype")

    def test_innovator_can_view_own_structured_booking_history(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("attendance:booking-history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hub booking history")
        self.assertContains(response, "AgriSense monitoring prototype")

    def test_innovator_can_view_professional_own_profile(self):
        self.client.force_login(self.innovator)
        response = self.client.get(reverse("innovators:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact details")
        self.assertContains(response, "My project portfolio")
        self.assertContains(response, self.innovator.innovator_profile.registration_number)

    def test_administrator_can_access_management_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 200)
        manage_response = self.client.get(reverse("innovators:manage"))
        self.assertEqual(manage_response.status_code, 200)
        self.assertContains(manage_response, "Download innovators")
        self.assertContains(manage_response, 'class="innovator-directory-page"')
        self.assertContains(manage_response, "<th>Name</th>", html=True)
        self.assertContains(manage_response, "<th>Registration</th>", html=True)
        self.assertContains(manage_response, "<th>Status</th>", html=True)
        self.assertNotContains(manage_response, "<th>Projects</th>", html=True)
        self.assertContains(manage_response, "View innovator")
        self.assertContains(manage_response, 'class="hub-footer')
        rendered_html = manage_response.content.decode()
        self.assertLess(
            rendered_html.index('class="innovator-directory-page"'),
            rendered_html.index('class="hub-footer'),
        )
        self.assertEqual(self.client.get(reverse("innovators:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("innovators:projects")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:bookings")).status_code, 200)
        self.assertEqual(self.client.get(reverse("auditlog:list")).status_code, 200)
        session_response = self.client.get(
            reverse("attendance:admin-detail", kwargs={"pk": self.other_session.pk})
        )
        self.assertNotContains(session_response, "Correct record")
        self.assertContains(session_response, "Back to innovator record")

    def test_administrator_can_download_all_innovators_as_csv(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("innovators:export"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["Full name", "Email", "Projects", "Areas of focus"])
        self.assertEqual(len(rows), 3)
        self.assertIn(
            [
                self.innovator.get_full_name(),
                self.innovator.email,
                self.innovator.innovator_profile.innovation_project_name,
                "Climate technology",
            ],
            rows,
        )
        self.assertIn(
            [
                self.other.get_full_name(),
                self.other.email,
                self.other.innovator_profile.innovation_project_name,
                "Climate technology",
            ],
            rows,
        )

    def test_main_pages_include_responsive_shell_and_mobile_table_markup(self):
        self.client.force_login(self.admin)

        for route_name in (
            "dashboard:admin",
            "dashboard:bookings",
            "innovators:manage",
            "auditlog:list",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'name="viewport" content="width=device-width, initial-scale=1"',
                )
                self.assertContains(response, 'data-bs-target="#hubSidebar"')
                self.assertContains(response, "mobile-card-table")

        self.client.force_login(self.innovator)
        for route_name in (
            "dashboard:innovator",
            "attendance:booking-history",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-bs-target="#hubSidebar"')
                self.assertContains(response, "mobile-card-table")

        projects_response = self.client.get(reverse("innovators:projects"))
        self.assertEqual(projects_response.status_code, 200)
        self.assertContains(projects_response, 'data-bs-target="#hubSidebar"')
        self.assertContains(projects_response, 'class="project-card-list"')

    def test_administrator_innovator_record_shows_profile_and_booking_summary(self):
        InnovatorProject.objects.create(
            profile=self.other.innovator_profile,
            name="Market Bridge",
            details="A produce market matching platform for smallholder farmers.",
            area_of_focus="Agricultural technology",
        )
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("innovators:detail", kwargs={"pk": self.other.innovator_profile.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other.get_full_name())
        self.assertContains(response, "Project portfolio")
        self.assertContains(response, "Climate technology")
        self.assertContains(response, "Market Bridge")
        self.assertContains(response, "Agricultural technology")
        self.assertContains(response, "produce market matching platform")
        self.assertContains(response, "Critical account action")
        self.assertContains(response, "Are you sure you want to continue?")
        self.assertContains(response, "Yes, deactivate account")
        self.assertNotContains(response, "Total visits")
        self.assertNotContains(response, "First login")
        self.assertNotContains(response, "Email access")
        self.assertEqual(response.context["booking_count"], 1)
