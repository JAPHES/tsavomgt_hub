import string
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import User
from accounts.services import generate_temporary_password
from auditlog.models import AuditLog
from core.tests.factories import (
    DEFAULT_PASSWORD,
    create_admin,
    create_innovator,
    make_test_password,
)
from innovators.models import InnovatorProfile


TEMPORARY_PASSWORD = make_test_password()
NEW_PERSONAL_PASSWORD = make_test_password()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationTests(TestCase):
    @override_settings(STATIC_VERSION="test-ui-version")
    def test_login_page_uses_split_layout_without_support_or_activation_link(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="login-welcome-panel"')
        self.assertContains(response, 'class="login-form-panel"')
        self.assertContains(response, "Tsavo Hub Management System")
        self.assertContains(response, f'{static("css/app.css")}?v=test-ui-version')
        self.assertContains(response, f'{static("js/app.js")}?v=test-ui-version')
        self.assertNotContains(response, "Activate account")
        self.assertNotContains(
            response, "Supported by Taita Taveta University &ndash; Home of Ideas"
        )

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

    def test_password_reset_page_matches_login_layout_and_shows_guidelines(self):
        response = self.client.get(reverse("accounts:password-reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="login-layout password-reset-layout"')
        self.assertContains(response, 'class="login-welcome-panel"')
        self.assertContains(response, 'class="login-form-panel"')
        self.assertContains(response, "Recovery guidelines")
        self.assertContains(response, "expires after one hour")
        self.assertContains(response, "spam or junk folder")
        self.assertContains(response, "system-generated temporary password")
        self.assertNotContains(
            response, "Supported by Taita Taveta University &ndash; Home of Ideas"
        )

    def test_password_reset_is_generic_and_sends_only_for_established_user(self):
        user = create_innovator()
        response = self.client.post(reverse("accounts:password-reset"), {"email": user.email})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Hello Amina,", message.body)
        self.assertIn("strong, unique password", message.body)
        self.assertIn("If you did not request this password reset", message.body)
        self.assertIn("Your current password will remain unchanged", message.body)
        self.assertIn("password-reset", message.body)
        self.assertEqual(len(message.alternatives), 1)
        html_body = message.alternatives[0].content
        self.assertIn('data-email-template="tsavo-hub"', html_body)
        self.assertIn("Reset your Tsavo Hub password", html_body)
        self.assertIn("Hello Amina,", html_body)
        self.assertIn("Choose a new password", html_body)
        self.assertIn("Did not request this?", html_body)
        self.assertIn("Your current password will remain unchanged", html_body)

        pending = create_innovator(
            email="pending@example.com",
            registration_number="TTU/INN/088",
            password=TEMPORARY_PASSWORD,
            must_change_password=True,
        )
        response = self.client.post(reverse("accounts:password-reset"), {"email": pending.email})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            reverse("accounts:password-reset"), {"email": "missing@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_confirm_page_is_personalized_and_styled(self):
        user = create_innovator(first_name="Japhes")
        reset_url = reverse(
            "accounts:password-reset-confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )

        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'class="login-layout password-reset-layout password-reset-confirm-layout"',
        )
        self.assertContains(response, "Hello Japhes,")
        self.assertContains(response, "Strong password checklist")
        self.assertContains(response, 'class="password-input-shell')
        self.assertContains(response, "data-password-toggle", count=2)
        self.assertContains(response, 'autocomplete="new-password"', count=2)
        self.assertContains(response, 'placeholder="Enter your new password"')
        self.assertNotContains(
            response, "Supported by Taita Taveta University &ndash; Home of Ideas"
        )

    def test_password_reset_confirm_validates_and_changes_password(self):
        user = create_innovator(first_name="Japhes")
        reset_url = reverse(
            "accounts:password-reset-confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )
        response = self.client.get(reset_url)
        confirm_url = response.url

        response = self.client.post(
            confirm_url,
            {"new_password1": "short", "new_password2": "short"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password requirements")
        self.assertContains(response, "This password is too short")

        response = self.client.post(
            confirm_url,
            {
                "new_password1": NEW_PERSONAL_PASSWORD,
                "new_password2": NEW_PERSONAL_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("accounts:password-reset-complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PERSONAL_PASSWORD))

    def test_invalid_password_reset_link_has_a_clear_recovery_action(self):
        user = create_innovator()
        response = self.client.get(
            reverse(
                "accounts:password-reset-confirm",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": "invalid-token",
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset link unavailable")
        self.assertContains(response, "Request another reset link")
        self.assertContains(response, "Back to sign in")

    def test_password_change_hides_rules_until_validation_fails(self):
        user = create_innovator()
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:password-change"))
        self.assertContains(response, 'class="auth-wrap"')
        self.assertContains(response, 'class="card auth-card password-auth-card"')
        self.assertContains(response, "Current password")
        self.assertContains(response, "New password")
        self.assertContains(response, "Confirm new password")
        self.assertNotContains(response, "Password requirements")

        response = self.client.post(
            reverse("accounts:password-change"),
            {
                "old_password": DEFAULT_PASSWORD,
                "new_password1": "short",
                "new_password2": "short",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password requirements")
        self.assertContains(response, "This password is too short")

    def test_password_change_updates_password(self):
        user = create_innovator()
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:password-change"),
            {
                "old_password": DEFAULT_PASSWORD,
                "new_password1": NEW_PERSONAL_PASSWORD,
                "new_password2": NEW_PERSONAL_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:password-change-done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PERSONAL_PASSWORD))

    def test_logout_requires_post(self):
        self.client.force_login(create_innovator())
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:login"))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TemporaryCredentialTests(TestCase):
    def setUp(self):
        self.user = create_innovator(
            password=TEMPORARY_PASSWORD,
            must_change_password=True,
        )

    def test_generated_password_is_strong_and_uses_secure_categories(self):
        password = generate_temporary_password()
        self.assertEqual(len(password), 18)
        self.assertTrue(any(character.isupper() for character in password))
        self.assertTrue(any(character.islower() for character in password))
        self.assertTrue(any(character.isdigit() for character in password))
        self.assertTrue(any(character in "!@#$%^&*" for character in password))
        self.assertTrue(
            all(
                character in string.ascii_letters + string.digits + "!@#$%^&*"
                for character in password
            )
        )

    def test_temporary_login_redirects_to_mandatory_password_change(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": TEMPORARY_PASSWORD},
        )
        self.assertRedirects(
            response,
            reverse("accounts:first-login-password-change"),
            fetch_redirect_response=False,
        )

    def test_middleware_blocks_all_other_pages_until_password_changes(self):
        self.client.force_login(self.user)
        for route in (
            reverse("dashboard:innovator"),
            reverse("innovators:profile"),
            reverse("attendance:history"),
            reverse("accounts:password-change"),
        ):
            self.assertRedirects(
                self.client.get(route),
                reverse("accounts:first-login-password-change"),
                fetch_redirect_response=False,
            )

    def test_first_login_form_rejects_weak_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:first-login-password-change"),
            {"new_password1": "short", "new_password2": "short"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This password is too short")
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_first_login_change_activates_account_logs_out_and_audits(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:first-login-password-change"),
            {
                "new_password1": NEW_PERSONAL_PASSWORD,
                "new_password2": NEW_PERSONAL_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.email_verified)
        self.assertEqual(self.user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(self.user.check_password(NEW_PERSONAL_PASSWORD))
        self.assertFalse(self.user.check_password(TEMPORARY_PASSWORD))
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.user,
                action=AuditLog.Action.ACCOUNT_ACTIVATED,
            ).exists()
        )

    def test_new_password_can_be_used_on_normal_login(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:first-login-password-change"),
            {
                "new_password1": NEW_PERSONAL_PASSWORD,
                "new_password2": NEW_PERSONAL_PASSWORD,
            },
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": NEW_PERSONAL_PASSWORD},
        )
        self.assertRedirects(response, reverse("dashboard:index"), fetch_redirect_response=False)

    def test_established_user_cannot_open_first_login_form(self):
        established = create_innovator(
            email="established@example.com",
            registration_number="TTU/INN/002",
        )
        self.client.force_login(established)
        self.assertRedirects(
            self.client.get(reverse("accounts:first-login-password-change")),
            reverse("dashboard:index"),
            fetch_redirect_response=False,
        )

    def test_old_activation_pages_are_removed(self):
        self.client.logout()
        self.assertEqual(self.client.get("/accounts/activate/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/resend-otp/").status_code, 404)


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
        }

    def test_add_innovator_form_contains_only_account_fields(self):
        response = self.client.get(reverse("innovators:create"))

        self.assertEqual(
            list(response.context["form"].fields),
            ["first_name", "last_name", "email", "registration_number", "phone_number"],
        )
        self.assertNotContains(response, "Initial project")

    @patch("accounts.services.generate_temporary_password", return_value=TEMPORARY_PASSWORD)
    def test_administrator_creates_account_and_emails_hashed_temporary_password(self, generator):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("innovators:create"), self.data)
        profile = InnovatorProfile.objects.get(registration_number="TTU/INN/099")
        user = profile.user

        self.assertRedirects(
            response, reverse("innovators:create-success", kwargs={"pk": profile.pk})
        )
        generator.assert_called_once_with()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password(TEMPORARY_PASSWORD))
        self.assertNotEqual(user.password, TEMPORARY_PASSWORD)
        self.assertTrue(user.is_active)
        self.assertTrue(user.must_change_password)
        self.assertEqual(user.account_status, User.AccountStatus.PENDING)
        self.assertFalse(profile.projects.exists())
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        html_body = message.alternatives[0].content
        self.assertIn(user.email, message.body)
        self.assertIn(TEMPORARY_PASSWORD, message.body)
        self.assertIn('data-email-template="tsavo-hub"', html_body)
        self.assertIn("Welcome to Tsavo Hub", html_body)
        self.assertIn("Your account is ready", html_body)
        self.assertIn(user.email, html_body)
        self.assertIn(TEMPORARY_PASSWORD, html_body)
        self.assertIn("Sign in to Tsavo Hub", html_body)
        self.assertIn("Keep these credentials private", html_body)
        audit = AuditLog.objects.get(action=AuditLog.Action.ACCOUNT_CREATED)
        self.assertNotIn(TEMPORARY_PASSWORD, str(audit.new_values))

    @override_settings(
        SUPPORT_EMAIL="hub-support@example.com",
        ASSISTANT_SUPPORT_EMAIL="assistant@example.com",
        SUPPORT_PHONE="+254700000000",
    )
    @patch("accounts.services.generate_temporary_password", return_value=TEMPORARY_PASSWORD)
    def test_credentials_email_includes_configured_support_contacts(self, generator):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("innovators:create"), self.data)

        message = mail.outbox[0]
        html_body = message.alternatives[0].content
        self.assertIn("hub-support@example.com", message.body)
        self.assertIn("assistant@example.com", message.body)
        self.assertIn("+254700000000", message.body)
        self.assertIn("hub-support@example.com", html_body)
        self.assertIn("assistant@example.com", html_body)
        self.assertIn("+254700000000", html_body)
        self.assertEqual(message.reply_to, ["hub-support@example.com"])
        generator.assert_called_once_with()

    def test_duplicate_email_is_rejected(self):
        create_innovator(email=self.data["email"], registration_number="OTHER/001")
        response = self.client.post(reverse("innovators:create"), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_duplicate_registration_number_is_rejected(self):
        create_innovator(
            email="other@example.com",
            registration_number=self.data["registration_number"],
        )
        response = self.client.post(reverse("innovators:create"), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")

    @patch("accounts.services.generate_temporary_password", return_value=TEMPORARY_PASSWORD)
    def test_administrator_can_reissue_pending_credentials(self, generator):
        pending = create_innovator(
            email="pending@example.com",
            registration_number="TTU/INN/077",
            password=make_test_password(),
            must_change_password=True,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse(
                    "innovators:admin-reissue-credentials",
                    kwargs={"pk": pending.innovator_profile.pk},
                )
            )

        self.assertRedirects(
            response,
            reverse("innovators:detail", kwargs={"pk": pending.innovator_profile.pk}),
        )
        generator.assert_called_once_with()
        pending.refresh_from_db()
        self.assertTrue(pending.check_password(TEMPORARY_PASSWORD))
        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0].content
        self.assertIn('data-email-template="tsavo-hub"', html_body)
        self.assertIn("Account access updated", html_body)
        self.assertIn("New temporary login credentials", html_body)
        audit = AuditLog.objects.get(
            action=AuditLog.Action.TEMPORARY_CREDENTIALS_REISSUED
        )
        self.assertNotIn(TEMPORARY_PASSWORD, str(audit.new_values))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CredentialDeliveryFailureTests(TransactionTestCase):
    def setUp(self):
        self.admin = create_admin()
        self.client.force_login(self.admin)

    @patch("accounts.services.generate_temporary_password", return_value=TEMPORARY_PASSWORD)
    @patch(
        "accounts.services.EmailMultiAlternatives.send",
        side_effect=RuntimeError("provider unavailable"),
    )
    def test_account_is_preserved_and_admin_sees_warning_when_delivery_fails(
        self, send, generator
    ):
        with self.assertLogs("accounts.services", level="ERROR") as captured:
            response = self.client.post(
                reverse("innovators:create"),
                {
                    "first_name": "Neema",
                    "last_name": "Mwangeka",
                    "email": "neema@students.ttu.ac.ke",
                    "registration_number": "TTU/INN/099",
                    "phone_number": "0711223344",
                },
                follow=True,
            )

        profile = InnovatorProfile.objects.get(registration_number="TTU/INN/099")
        self.assertRedirects(
            response,
            reverse("innovators:detail", kwargs={"pk": profile.pk}),
        )
        self.assertContains(response, "email could not be delivered")
        self.assertTrue(profile.user.must_change_password)
        generator.assert_called_once_with()
        send.assert_called_once_with(fail_silently=False)
        self.assertNotIn(TEMPORARY_PASSWORD, "\n".join(captured.output))

    @patch(
        "accounts.services.EmailMultiAlternatives.send",
        side_effect=RuntimeError("provider unavailable"),
    )
    def test_reissue_redirects_with_warning_instead_of_server_error(self, send):
        pending = create_innovator(
            email="pending@example.com",
            registration_number="TTU/INN/077",
            password=make_test_password(),
            must_change_password=True,
        )

        with self.assertLogs("accounts.services", level="ERROR"):
            response = self.client.post(
                reverse(
                    "innovators:admin-reissue-credentials",
                    kwargs={"pk": pending.innovator_profile.pk},
                ),
                follow=True,
            )

        self.assertRedirects(
            response,
            reverse("innovators:detail", kwargs={"pk": pending.innovator_profile.pk}),
        )
        self.assertContains(response, "email could not be delivered")
        send.assert_called_once_with(fail_silently=False)
