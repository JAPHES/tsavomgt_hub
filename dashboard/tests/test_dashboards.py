from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import HubBooking
from auditlog.models import AuditLog
from core.tests.factories import create_admin, create_innovator
from innovators.models import InnovatorProject
from innovators.services import ProjectError, create_project


class AdministratorDashboardTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.user = create_innovator()
        self.client.force_login(self.admin)

    def create_booking(self, **overrides):
        values = {
            "innovator": self.user,
            "visit_date": timezone.localdate(),
            "arrival_time": time(10, 0),
            "purpose": "Build and test the BlueWatch sensor dashboard.",
        }
        values.update(overrides)
        return HubBooking.objects.create(**values)

    def test_todays_bookings_are_displayed_with_summary(self):
        self.create_booking()
        response = self.client.get(reverse("dashboard:admin"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.get_full_name())
        self.assertContains(response, "Build and test the BlueWatch")
        self.assertEqual(
            response.context["summary"],
            {
                "active_innovators": 1,
                "bookings_today": 1,
                "awaiting_admission": 1,
                "admitted_today": 0,
            },
        )

    def test_future_bookings_are_not_shown_in_todays_queue(self):
        self.create_booking(visit_date=timezone.localdate() + timedelta(days=1))
        response = self.client.get(reverse("dashboard:admin"))

        self.assertNotContains(response, self.user.get_full_name())
        self.assertEqual(response.context["summary"]["bookings_today"], 0)

    def test_administrator_can_admit_todays_booking_once(self):
        booking = self.create_booking()
        response = self.client.post(
            reverse("dashboard:admit-booking", kwargs={"pk": booking.pk})
        )

        self.assertRedirects(response, reverse("dashboard:admin"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, HubBooking.Status.ADMITTED)
        self.assertEqual(booking.admitted_by, self.admin)
        self.assertIsNotNone(booking.admitted_at)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.BOOKING_ADMITTED,
                target_id=str(booking.pk),
            ).exists()
        )

        second_response = self.client.post(
            reverse("dashboard:admit-booking", kwargs={"pk": booking.pk}), follow=True
        )
        self.assertContains(second_response, "already been admitted")
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.BOOKING_ADMITTED).count(), 1
        )

    def test_admission_endpoint_is_post_only(self):
        booking = self.create_booking()
        response = self.client.get(
            reverse("dashboard:admit-booking", kwargs={"pk": booking.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_filter_returns_bookings_for_matching_innovator_name(self):
        matching = self.create_booking()
        other_user = create_innovator(
            email="other@example.com",
            registration_number="TTU/INN/007",
            project="AgriSense",
            first_name="Peter",
            last_name="Mwangi",
        )
        HubBooking.objects.create(
            innovator=other_user,
            visit_date=timezone.localdate() + timedelta(days=1),
            arrival_time=time(14, 0),
            purpose="Calibrate and test the AgriSense soil monitoring device.",
        )

        response = self.client.get(
            reverse("dashboard:bookings"), {"innovator_name": "Amina Juma"}
        )

        self.assertEqual(list(response.context["form"].fields), ["innovator_name"])
        self.assertEqual(list(response.context["page_obj"].object_list), [matching])
        self.assertContains(response, "BlueWatch sensor dashboard")
        self.assertNotContains(response, "AgriSense soil monitoring")


class InnovatorDashboardTests(TestCase):
    def setUp(self):
        self.user = create_innovator()
        self.client.force_login(self.user)

    def test_dashboard_presents_booking_flow(self):
        response = self.client.get(reverse("dashboard:innovator"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, f"Welcome, {self.user.first_name}, to Tsavo Hub Management System"
        )
        self.assertContains(response, "Book a hub visit")
        self.assertContains(response, "My projects")
        self.assertNotContains(response, 'id="add-project-title"')
        self.assertNotContains(response, "Work done during this period")

    def test_projects_have_a_dedicated_page(self):
        response = self.client.get(reverse("innovators:projects"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="add-project-title"')
        self.assertContains(response, "Project portfolio")
        self.assertContains(response, "BlueWatch")

    def test_innovator_can_add_a_project_with_details_and_focus_area(self):
        response = self.client.post(
            reverse("innovators:projects"),
            {
                "name": "Afya Link",
                "details": "A remote health consultation and patient follow-up platform.",
                "area_of_focus": "Digital health",
            },
        )

        self.assertRedirects(response, reverse("innovators:projects"))
        project = InnovatorProject.objects.get(
            profile=self.user.innovator_profile, name="Afya Link"
        )
        self.assertEqual(project.area_of_focus, "Digital health")
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.user,
                action=AuditLog.Action.PROJECT_CREATED,
                target_id=str(project.pk),
            ).exists()
        )

    def test_project_requires_details_and_rejects_duplicate_name(self):
        response = self.client.post(
            reverse("innovators:projects"),
            {
                "name": "bluewatch",
                "details": "Too short",
                "area_of_focus": "IoT",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a project with this name")
        self.assertContains(response, "at least 20 characters")
        self.assertEqual(self.user.innovator_profile.projects.count(), 1)

    def test_innovator_cannot_add_a_project_to_another_profile(self):
        other = create_innovator(
            email="portfolio-owner@example.com",
            registration_number="TTU/INN/404",
        )
        with self.assertRaises(ProjectError):
            create_project(
                other.innovator_profile,
                name="Unauthorized project",
                details="This project must not be attached to another innovator.",
                area_of_focus="Security",
                actor=self.user,
            )
        self.assertFalse(
            InnovatorProject.objects.filter(
                profile=other.innovator_profile, name="Unauthorized project"
            ).exists()
        )

    def test_innovator_can_book_a_future_visit(self):
        visit_date = timezone.localdate() + timedelta(days=2)
        response = self.client.post(
            reverse("dashboard:innovator"),
            {
                "visit_date": visit_date.isoformat(),
                "arrival_time": "10:30",
                "purpose": "Prototype and test the water-quality alert workflow.",
            },
        )

        self.assertRedirects(response, reverse("dashboard:innovator"))
        booking = HubBooking.objects.get(innovator=self.user)
        self.assertEqual(booking.visit_date, visit_date)
        self.assertEqual(booking.arrival_time, time(10, 30))
        self.assertEqual(booking.status, HubBooking.Status.BOOKED)
        self.assertIsNone(booking.admitted_at)

    def test_booking_rejects_past_dates_and_short_purpose(self):
        response = self.client.post(
            reverse("dashboard:innovator"),
            {
                "visit_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
                "arrival_time": "10:30",
                "purpose": "Test",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose today or a future date")
        self.assertContains(response, "Give a useful description")
        self.assertFalse(HubBooking.objects.filter(innovator=self.user).exists())

    def test_only_one_booking_is_allowed_per_innovator_per_day(self):
        visit_date = timezone.localdate() + timedelta(days=1)
        HubBooking.objects.create(
            innovator=self.user,
            visit_date=visit_date,
            arrival_time=time(9, 0),
            purpose="Prepare and test the first prototype in the workshop.",
        )
        response = self.client.post(
            reverse("dashboard:innovator"),
            {
                "visit_date": visit_date.isoformat(),
                "arrival_time": "14:00",
                "purpose": "Return to continue testing the same working prototype.",
            },
        )

        self.assertContains(response, "already have a hub booking for this date")
        self.assertEqual(HubBooking.objects.filter(innovator=self.user).count(), 1)
