from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditlog.models import AuditLog
from core.tests.factories import DEFAULT_PASSWORD, create_admin, create_innovator
from innovators.models import InnovatorProfile

from accounts.models import AccountActivationOTP, User
from accounts.services import (
    OTPVerificationError,
    complete_activation,
    generate_otp,
    issue_activation_otp,
    verify_activation_otp,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationTests(TestCase):
    def test_email_login_and_invalid_login(self):
        user = create_innovator()
        response = self.client.post(
            reverse("accounts:login"), {"username": user.email, "password": DEFAULT_PASSWORD}
        )
        self.assertRedirects(response, reverse("dashboard:index"), fetch_redirect_response=False)
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"), {"username": user.email, "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unable to log in")

    def test_inactive_user_cannot_log_in(self):
        user = create_innovator(active=False)
        user.set_password(DEFAULT_PASSWORD)
        user.save(update_fields=["password"])
        response = self.client.post(
            reverse("accounts:login"), {"username": user.email, "password": DEFAULT_PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_is_generic_and_sends_for_active_user(self):
        user = create_innovator()
        response = self.client.post(reverse("accounts:password-reset"), {"email": user.email})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password-reset", mail.outbox[0].body)
        response = self.client.post(
            reverse("accounts:password-reset"), {"email": "missing@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_logout_requires_post(self):
        self.client.force_login(create_innovator())
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:login"))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_RESEND_COOLDOWN_SECONDS=0,
)
class OTPTests(TestCase):
    def setUp(self):
        self.user = create_innovator(active=False)

    def issue_known_otp(self, value="123456"):
        with patch("accounts.services.generate_otp", return_value=value):
            with self.captureOnCommitCallbacks(execute=True):
                otp = issue_activation_otp(self.user)
        return otp

    def test_secure_six_digit_generation(self):
        otp = generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_otp_is_hashed_and_correct_code_verifies(self):
        otp = self.issue_known_otp()
        self.assertNotEqual(otp.otp_hash, "123456")
        verified_user, verified_otp = verify_activation_otp(self.user.email, "123456")
        self.assertEqual(verified_user, self.user)
        self.assertEqual(verified_otp, otp)

    def test_incorrect_otp_increments_attempt_count(self):
        otp = self.issue_known_otp()
        with self.assertRaises(OTPVerificationError):
            verify_activation_otp(self.user.email, "000000")
        otp.refresh_from_db()
        self.assertEqual(otp.attempt_count, 1)

    def test_expired_and_used_otps_are_rejected(self):
        otp = self.issue_known_otp()
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=["expires_at"])
        with self.assertRaises(OTPVerificationError):
            verify_activation_otp(self.user.email, "123456")
        otp.expires_at = timezone.now() + timedelta(minutes=5)
        otp.used_at = timezone.now()
        otp.save(update_fields=["expires_at", "used_at"])
        with self.assertRaises(OTPVerificationError):
            verify_activation_otp(self.user.email, "123456")

    @override_settings(OTP_MAX_ATTEMPTS=2)
    def test_attempt_limit_blocks_even_correct_code(self):
        otp = self.issue_known_otp()
        for value in ("000000", "111111"):
            with self.assertRaises(OTPVerificationError):
                verify_activation_otp(self.user.email, value)
        otp.refresh_from_db()
        self.assertEqual(otp.attempt_count, 2)
        with self.assertRaises(OTPVerificationError):
            verify_activation_otp(self.user.email, "123456")

    def test_resend_invalidates_previous_otp(self):
        first = self.issue_known_otp("123456")
        with patch("accounts.services.generate_otp", return_value="654321"):
            with self.captureOnCommitCallbacks(execute=True):
                second = issue_activation_otp(self.user, resent=True)
        first.refresh_from_db()
        self.assertIsNotNone(first.invalidated_at)
        with self.assertRaises(OTPVerificationError):
            verify_activation_otp(self.user.email, "123456")
        self.assertEqual(verify_activation_otp(self.user.email, "654321")[1], second)

    def test_password_creation_completes_activation_and_uses_otp(self):
        otp = self.issue_known_otp()
        complete_activation(self.user.pk, otp.pk, DEFAULT_PASSWORD)
        self.user.refresh_from_db()
        otp.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.email_verified)
        self.assertTrue(self.user.activation_completed)
        self.assertTrue(self.user.check_password(DEFAULT_PASSWORD))
        self.assertIsNotNone(otp.used_at)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.ACCOUNT_ACTIVATED).exists()
        )

    def test_activation_view_verifies_then_creates_password(self):
        otp = self.issue_known_otp()
        response = self.client.post(
            reverse("accounts:activate"), {"email": self.user.email, "otp": "123456"}
        )
        self.assertRedirects(response, reverse("accounts:activation-password"))
        response = self.client.post(
            reverse("accounts:activation-password"),
            {"new_password1": DEFAULT_PASSWORD, "new_password2": DEFAULT_PASSWORD},
        )
        self.assertRedirects(response, reverse("accounts:login"))
        otp.refresh_from_db()
        self.assertIsNotNone(otp.used_at)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdministratorAccountCreationTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.client.force_login(self.admin)
        self.data = {
            "first_name": "Neema",
            "last_name": "Mwangeka",
            "email": "neema@students.ttu.ac.ke",
            "registration_number": "TTU/INN/099",
            "phone_number": "0711223344",
            "innovation_project_name": "Eco Sort",
            "account_status": User.AccountStatus.PENDING,
        }

    def test_administrator_creates_account_and_otp(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("innovators:create"), self.data)
        profile = InnovatorProfile.objects.get(registration_number="TTU/INN/099")
        self.assertRedirects(
            response, reverse("innovators:create-success", kwargs={"pk": profile.pk})
        )
        self.assertFalse(profile.user.has_usable_password())
        self.assertFalse(profile.user.is_active)
        self.assertEqual(profile.user.activation_otps.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.ACCOUNT_CREATED).exists())

    def test_duplicate_email_is_rejected(self):
        create_innovator(email=self.data["email"], registration_number="OTHER/001")
        response = self.client.post(reverse("innovators:create"), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_duplicate_registration_number_is_rejected(self):
        create_innovator(email="other@example.com", registration_number=self.data["registration_number"])
        response = self.client.post(reverse("innovators:create"), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")
