from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from auditlog.models import AuditLog
from core.tests.factories import DEFAULT_PASSWORD, create_admin, create_innovator, make_test_password
from innovators.models import InnovatorProfile


class InnovatorProfileCompletionTests(TestCase):
    def setUp(self):
        self.innovator = create_innovator(profile_complete=False)

    def test_login_redirects_incomplete_innovator_to_profile_setup(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.innovator.email, "password": DEFAULT_PASSWORD},
        )

        self.assertRedirects(
            response,
            reverse("innovators:profile-complete"),
            fetch_redirect_response=False,
        )

    def test_temporary_password_change_takes_priority_over_profile_setup(self):
        temporary_password = make_test_password()
        pending = create_innovator(
            email="pending-profile@example.com",
            registration_number="TTU/INN/077",
            password=temporary_password,
            must_change_password=True,
            profile_complete=False,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": pending.email, "password": temporary_password},
        )

        self.assertRedirects(
            response,
            reverse("accounts:first-login-password-change"),
            fetch_redirect_response=False,
        )

    def test_incomplete_profile_cannot_bypass_required_setup(self):
        self.client.force_login(self.innovator)

        for route in (
            reverse("dashboard:innovator"),
            reverse("innovators:profile"),
            reverse("innovators:projects"),
            reverse("attendance:booking-history"),
            reverse("accounts:password-change"),
        ):
            with self.subTest(route=route):
                self.assertRedirects(
                    self.client.get(route),
                    reverse("innovators:profile-complete"),
                    fetch_redirect_response=False,
                )

        self.assertEqual(self.client.get(reverse("innovators:profile-complete")).status_code, 200)

    def test_profile_setup_page_contains_all_required_fields(self):
        self.client.force_login(self.innovator)

        response = self.client.get(reverse("innovators:profile-complete"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete your innovator profile")
        self.assertContains(response, "Gender")
        self.assertContains(response, "School")
        self.assertContains(response, "Department")
        self.assertContains(response, "County of origin")
        self.assertContains(response, '<option value="MALE">Male</option>')
        self.assertContains(response, '<option value="FEMALE">Female</option>')
        self.assertContains(response, "School of Science and Informatics")
        self.assertContains(response, "Informatics and Computing")
        self.assertContains(response, '<option value="Taita Taveta">Taita Taveta</option>')
        self.assertContains(response, "All fields on this page are required")

    def test_profile_setup_rejects_missing_required_details(self):
        self.client.force_login(self.innovator)

        response = self.client.post(
            reverse("innovators:profile-complete"),
            {"gender": "", "school": "", "department": "", "county": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required", count=4)
        self.innovator.innovator_profile.refresh_from_db()
        self.assertFalse(
            self.innovator.innovator_profile.has_completed_required_details
        )

    def test_completing_profile_saves_details_and_unlocks_dashboard(self):
        self.client.force_login(self.innovator)

        response = self.client.post(
            reverse("innovators:profile-complete"),
            {
                "gender": InnovatorProfile.Gender.FEMALE,
                "school": "  School of Science and Informatics  ",
                "department": "Informatics   and Computing",
                "county": "Taita Taveta",
            },
        )

        self.assertRedirects(response, reverse("dashboard:innovator"))
        profile = InnovatorProfile.objects.get(user=self.innovator)
        self.assertEqual(profile.gender, InnovatorProfile.Gender.FEMALE)
        self.assertEqual(profile.school, "School of Science and Informatics")
        self.assertEqual(profile.department, "Informatics and Computing")
        self.assertEqual(profile.county, "Taita Taveta")
        self.assertTrue(profile.has_completed_required_details)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.innovator,
                action=AuditLog.Action.ACCOUNT_UPDATED,
                reason="Innovator completed required profile details",
            ).exists()
        )

        profile_response = self.client.get(reverse("innovators:profile"))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, "Female")
        self.assertContains(profile_response, "School of Science and Informatics")
        self.assertContains(profile_response, "Informatics and Computing")
        self.assertContains(profile_response, "Taita Taveta")

    def test_administrator_sees_completed_details_and_incomplete_fallbacks(self):
        completed = create_innovator(
            email="completed-profile@example.com",
            registration_number="TTU/INN/088",
            gender=InnovatorProfile.Gender.MALE,
            school="School of Mines and Engineering",
            department="Mining and Mineral Processing Engineering",
            county="Mombasa",
        )
        administrator = create_admin()
        self.client.force_login(administrator)

        completed_response = self.client.get(
            reverse(
                "innovators:detail",
                kwargs={"pk": completed.innovator_profile.pk},
            )
        )
        self.assertContains(completed_response, "Male")
        self.assertContains(completed_response, "School of Mines and Engineering")
        self.assertContains(
            completed_response, "Mining and Mineral Processing Engineering"
        )
        self.assertContains(completed_response, "Mombasa")

        incomplete_response = self.client.get(
            reverse(
                "innovators:detail",
                kwargs={"pk": self.innovator.innovator_profile.pk},
            )
        )
        self.assertContains(incomplete_response, "Not provided", count=4)

    def test_completed_innovator_can_update_profile_details_later(self):
        innovator = create_innovator(
            email="editable-profile@example.com",
            registration_number="TTU/INN/099",
        )
        self.client.force_login(innovator)

        response = self.client.post(
            reverse("innovators:profile-edit"),
            {
                "phone_number": "0711223344",
                "gender": InnovatorProfile.Gender.MALE,
                "school": "School of Business",
                "department": "Business Administration",
                "county": "Nairobi",
            },
        )

        self.assertRedirects(response, reverse("innovators:profile"))
        innovator.innovator_profile.refresh_from_db()
        self.assertEqual(innovator.innovator_profile.gender, InnovatorProfile.Gender.MALE)
        self.assertEqual(innovator.innovator_profile.school, "School of Business")
        self.assertEqual(
            innovator.innovator_profile.department, "Business Administration"
        )
        self.assertEqual(innovator.innovator_profile.county, "Nairobi")

    def test_administrators_are_not_subject_to_profile_completion(self):
        administrator = create_admin()
        self.client.force_login(administrator)

        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 200)
        self.assertEqual(administrator.role, User.Role.ADMIN)
