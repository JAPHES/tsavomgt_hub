from django.core import mail
from django.test import TestCase, override_settings

from core.tests.factories import create_innovator
from innovators.services import send_deactivation_email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SUPPORT_EMAIL="hub-support@example.com",
    ASSISTANT_SUPPORT_EMAIL="assistant@example.com",
    SUPPORT_PHONE="+254700000000",
)
class DeactivationEmailTests(TestCase):
    def test_email_includes_configured_help_contacts_and_reply_address(self):
        user = create_innovator()

        send_deactivation_email(user)

        message = mail.outbox[0]
        html_body = message.alternatives[0].content
        self.assertIn("hub-support@example.com", message.body)
        self.assertIn("assistant@example.com", message.body)
        self.assertIn("+254700000000", message.body)
        self.assertIn("hub-support@example.com", html_body)
        self.assertIn("assistant@example.com", html_body)
        self.assertIn("+254700000000", html_body)
        self.assertIn("believe this was an error", message.body)
        self.assertIn("believe this was an error", html_body)
        self.assertEqual(message.reply_to, ["hub-support@example.com"])
