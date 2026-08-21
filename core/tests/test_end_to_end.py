from datetime import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from attendance.models import HubBooking
from core.tests.factories import DEFAULT_PASSWORD, create_admin, make_test_password


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CompleteHubFlowTests(TestCase):
    def test_first_login_booking_and_admin_admission_flow(self):
        administrator = create_admin()
        self.client.force_login(administrator)
        create_data = {
            "first_name": "Neema",
            "last_name": "Mwangeka",
            "email": "neema@students.ttu.ac.ke",
            "registration_number": "TTU/INN/099",
            "phone_number": "0711223344",
            "innovation_project_name": "Eco Sort",
            "project_details": "A smart sorting system that classifies recyclable waste.",
            "area_of_focus": "Climate technology",
        }
        temporary_password = make_test_password()
        with patch(
            "accounts.services.generate_temporary_password", return_value=temporary_password
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("innovators:create"), create_data)
        self.assertEqual(response.status_code, 302)
        innovator = User.objects.get(email=create_data["email"])

        self.client.logout()
        self.assertRedirects(
            self.client.post(
                reverse("accounts:login"),
                {"username": innovator.email, "password": temporary_password},
            ),
            reverse("accounts:first-login-password-change"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.post(
                reverse("accounts:first-login-password-change"),
                {"new_password1": DEFAULT_PASSWORD, "new_password2": DEFAULT_PASSWORD},
            ),
            reverse("accounts:login"),
        )
        innovator.refresh_from_db()
        self.assertRedirects(
            self.client.post(
                reverse("accounts:login"),
                {"username": innovator.email, "password": DEFAULT_PASSWORD},
            ),
            reverse("dashboard:index"),
            fetch_redirect_response=False,
        )

        self.assertRedirects(
            self.client.post(
                reverse("dashboard:innovator"),
                {
                    "visit_date": timezone.localdate().isoformat(),
                    "arrival_time": "10:00",
                    "purpose": "Build and test the Eco Sort classification prototype.",
                },
            ),
            reverse("dashboard:innovator"),
        )
        booking = HubBooking.objects.get(innovator=innovator)
        self.assertEqual(booking.arrival_time, time(10, 0))

        self.client.force_login(administrator)
        admin_queue = self.client.get(reverse("dashboard:admin"))
        self.assertContains(admin_queue, "Neema Mwangeka")
        self.assertContains(admin_queue, "Eco Sort classification prototype")
        self.assertEqual(admin_queue.context["summary"]["awaiting_admission"], 1)

        self.assertRedirects(
            self.client.post(
                reverse("dashboard:admit-booking", kwargs={"pk": booking.pk})
            ),
            reverse("dashboard:admin"),
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, HubBooking.Status.ADMITTED)
        self.assertEqual(booking.admitted_by, administrator)
        self.assertIsNotNone(booking.admitted_at)

        admitted_queue = self.client.get(reverse("dashboard:admin"))
        self.assertEqual(admitted_queue.context["summary"]["awaiting_admission"], 0)
        self.assertEqual(admitted_queue.context["summary"]["admitted_today"], 1)
