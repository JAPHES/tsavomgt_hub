from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from attendance.models import AttendanceSession
from core.tests.factories import DEFAULT_PASSWORD, create_admin, make_test_password


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CompleteHubFlowTests(TestCase):
    def test_first_login_attendance_and_admin_monitoring_flow(self):
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
        temporary_password = make_test_password()
        with patch(
            "accounts.services.generate_temporary_password",
            return_value=temporary_password,
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
                reverse("attendance:check-in"),
                {
                    "project_name": "Eco Sort",
                },
            ),
            reverse("dashboard:innovator"),
        )

        self.client.force_login(administrator)
        admin_live = self.client.get(reverse("dashboard:admin"))
        self.assertContains(admin_live, "Neema Mwangeka")
        self.assertEqual(admin_live.context["summary"]["attended_today"], 1)

        self.client.force_login(innovator)
        checkout = self.client.post(
            reverse("attendance:check-out"),
            {
                "work_completed": "Completed the classification form and validated its database records.",
                "challenges_encountered": "A small sample dataset limited testing.",
            },
        )
        self.assertEqual(checkout.status_code, 302)
        session = AttendanceSession.objects.get(innovator=innovator)
        self.assertEqual(session.status, AttendanceSession.Status.COMPLETED)
        self.assertIsNotNone(session.duration)

        self.client.force_login(administrator)
        completed = self.client.get(reverse("dashboard:admin"))
        self.assertContains(completed, "Completed the classification form")
        self.assertEqual(completed.context["summary"]["attended_today"], 1)
