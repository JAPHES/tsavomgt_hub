import os
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import User


class BootstrapAdminCommandTests(TestCase):
    def run_command(self, environment):
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True):
            call_command("bootstrap_admin", stdout=output)
        return output.getvalue()

    def test_skips_when_credentials_are_not_configured(self):
        output = self.run_command({})

        self.assertIn("not configured", output)
        self.assertFalse(User.objects.exists())

    def test_requires_email_and_password_together(self):
        with self.assertRaisesMessage(CommandError, "must be set together"):
            self.run_command({"INITIAL_ADMIN_EMAIL": "admin@example.com"})

    def test_rejects_an_invalid_email(self):
        with self.assertRaisesMessage(CommandError, "not a valid email"):
            self.run_command(
                {
                    "INITIAL_ADMIN_EMAIL": "invalid",
                    "INITIAL_ADMIN_PASSWORD": "StrongDeploymentPassword-4892",
                }
            )

    def test_rejects_a_weak_password(self):
        with self.assertRaises(CommandError):
            self.run_command(
                {
                    "INITIAL_ADMIN_EMAIL": "admin@example.com",
                    "INITIAL_ADMIN_PASSWORD": "password",
                }
            )

    def test_creates_the_first_administrator(self):
        output = self.run_command(
            {
                "INITIAL_ADMIN_EMAIL": "ADMIN@EXAMPLE.COM",
                "INITIAL_ADMIN_PASSWORD": "StrongDeploymentPassword-4892",
                "INITIAL_ADMIN_FIRST_NAME": "Tsavo",
                "INITIAL_ADMIN_LAST_NAME": "Manager",
            }
        )

        user = User.objects.get(email="admin@example.com")
        self.assertIn("created", output)
        self.assertEqual(user.first_name, "Tsavo")
        self.assertEqual(user.last_name, "Manager")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
        self.assertFalse(user.must_change_password)
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.check_password("StrongDeploymentPassword-4892"))

    def test_existing_administrator_is_never_changed(self):
        original_password = "OriginalDeploymentPassword-4892"
        user = User.objects.create_superuser(
            email="admin@example.com",
            password=original_password,
        )

        output = self.run_command(
            {
                "INITIAL_ADMIN_EMAIL": "another@example.com",
                "INITIAL_ADMIN_PASSWORD": "DifferentDeploymentPassword-5721",
            }
        )

        user.refresh_from_db()
        self.assertIn("already exists", output)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(user.check_password(original_password))
        self.assertFalse(user.check_password("DifferentDeploymentPassword-5721"))

    def test_refuses_to_promote_an_existing_non_administrator(self):
        User.objects.create_user(
            email="member@example.com",
            password="MemberDeploymentPassword-4892",
        )

        with self.assertRaisesMessage(CommandError, "non-administrator account"):
            self.run_command(
                {
                    "INITIAL_ADMIN_EMAIL": "member@example.com",
                    "INITIAL_ADMIN_PASSWORD": "StrongDeploymentPassword-4892",
                }
            )
