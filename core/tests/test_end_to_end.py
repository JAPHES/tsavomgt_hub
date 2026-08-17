from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from attendance.models import AttendanceSession
from core.tests.factories import DEFAULT_PASSWORD, create_admin


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CompleteHubFlowTests(TestCase):
    def test_account_activation_attendance_and_admin_monitoring_flow(self):
        administrator = create_admin()
        self.client.force_login(administrator)
        create_data = {
            "first_name": "Neema",
            "last_name": "Mwangeka",
            "email": "neema@students.ttu.ac.ke",
            "registration_number": "TTU/INN/099",
            "phone_number": "0711223344",
            "innovation_project_name": "Eco Sort",
        }
        with patch("accounts.services.generate_otp", return_value="246810"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("innovators:create"), create_data)
        self.assertEqual(response.status_code, 302)
        innovator = User.objects.get(email=create_data["email"])

        self.client.logout()
        self.assertRedirects(
            self.client.post(
                reverse("accounts:activate"), {"email": innovator.email, "otp": "246810"}
            ),
            reverse("accounts:activation-password"),
        )
        self.assertRedirects(
            self.client.post(
                reverse("accounts:activation-password"),
                {"new_password1": DEFAULT_PASSWORD, "new_password2": DEFAULT_PASSWORD},
            ),
            reverse("accounts:login"),
        )
        innovator.refresh_from_db()
        self.assertTrue(
            self.client.login(username=innovator.email, password=DEFAULT_PASSWORD)
        )
        self.assertRedirects(
            self.client.post(
                reverse("attendance:check-in"),
                {
                    "project_name": "Eco Sort",
                    "planned_activity": "Build and test the recyclable material classification form.",
                },
            ),
            reverse("dashboard:innovator"),
        )

        self.client.force_login(administrator)
        admin_live = self.client.get(reverse("dashboard:admin"))
        self.assertContains(admin_live, "Neema Mwangeka")
        self.assertEqual(admin_live.context["summary"]["currently_in_hub"], 1)

        self.client.force_login(innovator)
        checkout = self.client.post(
            reverse("attendance:check-out"),
            {
                "work_completed": "Completed the classification form and validated its database records.",
                "challenges_encountered": "A small sample dataset limited testing.",
                "next_step": "Collect a larger labelled dataset.",
            },
        )
        self.assertEqual(checkout.status_code, 302)
        session = AttendanceSession.objects.get(innovator=innovator)
        self.assertEqual(session.status, AttendanceSession.Status.COMPLETED)
        self.assertIsNotNone(session.duration)

        self.client.force_login(administrator)
        completed = self.client.get(reverse("dashboard:admin"))
        self.assertContains(completed, "Completed the classification form")
        self.assertEqual(completed.context["summary"]["currently_in_hub"], 0)
        self.assertEqual(completed.context["summary"]["checked_out_today"], 1)
