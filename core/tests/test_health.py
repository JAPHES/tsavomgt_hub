from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.db.utils import OperationalError
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.service_status import mark_database_available, mark_database_unavailable
from core.tests.factories import create_admin

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}


class TemporaryOutageStateMixin:
    def setUp(self):
        super().setUp()
        self.temporary_directory = TemporaryDirectory()
        self.state_path = Path(self.temporary_directory.name) / "database-status.json"
        self.settings_override = override_settings(
            DATABASE_OUTAGE_STATE_FILE=str(self.state_path),
            DATABASE_OUTAGE_ALERT_COOLDOWN_SECONDS=3600,
            OUTAGE_ADMIN_EMAILS=[],
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_directory.cleanup()
        super().tearDown()


class HealthCheckTests(TemporaryOutageStateMixin, TestCase):
    def test_liveness_returns_ok_without_database_queries(self):
        administrator = create_admin()
        self.client.force_login(administrator)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(len(queries), 0)

    def test_database_readiness_reports_available_database(self):
        response = self.client.get(reverse("core:database-health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "available"},
        )

    def test_database_readiness_reports_degraded_without_sensitive_details(self):
        sensitive_message = "password=secret host=private-neon-host"
        with patch(
            "core.views.connection.cursor",
            side_effect=OperationalError(sensitive_message),
        ):
            response = self.client.get(reverse("core:database-health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "degraded", "database": "unavailable"},
        )
        self.assertNotContains(response, sensitive_message, status_code=503)
        self.assertNotContains(response, "private-neon-host", status_code=503)

    def test_status_page_does_not_query_database(self):
        administrator = create_admin()
        self.client.force_login(administrator)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("core:status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All systems operational")
        self.assertEqual(len(queries), 0)

    def test_status_page_reflects_last_observed_outage_without_database_access(self):
        mark_database_unavailable()

        with patch(
            "core.views.connection.cursor",
            side_effect=OperationalError("database remains unavailable"),
        ):
            response = self.client.get(reverse("core:status"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "Some services are temporarily unavailable",
            status_code=503,
        )


@override_settings(STORAGES=TEST_STORAGES)
class GracefulDatabaseFailureTests(TemporaryOutageStateMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.administrator = create_admin()
        self.client.force_login(self.administrator)

    def test_model_backed_view_returns_branded_503_for_operational_error(self):
        sensitive_message = "postgresql://user:secret@private-host/database"
        with patch(
            "dashboard.views._base_bookings",
            side_effect=OperationalError(sensitive_message),
        ):
            response = self.client.get(reverse("dashboard:admin"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "Some services are temporarily unavailable",
            status_code=503,
        )
        self.assertNotContains(response, sensitive_message, status_code=503)
        self.assertNotContains(response, "private-host", status_code=503)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_model_backed_view_still_works_when_database_is_healthy(self):
        response = self.client.get(reverse("dashboard:admin"))

        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_non_database_programming_errors_are_not_converted_to_503(self):
        client = Client(raise_request_exception=False)
        client.force_login(self.administrator)
        with patch("dashboard.views._base_bookings", side_effect=ValueError("bug")):
            response = client.get(reverse("dashboard:admin"))

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Something went wrong", status_code=500)


class OutageNotificationTests(TemporaryOutageStateMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.recipients_override = override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            OUTAGE_ADMIN_EMAILS=["operations@example.com"],
        )
        self.recipients_override.enable()
        mail.outbox.clear()

    def tearDown(self):
        self.recipients_override.disable()
        super().tearDown()

    def test_repeated_outage_reports_send_one_alert(self):
        mark_database_unavailable()
        mark_database_unavailable()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Tsavo Hub Service Interruption")
        self.assertEqual(mail.outbox[0].to, ["operations@example.com"])

    def test_recovery_notification_is_sent_once(self):
        mark_database_unavailable()
        mark_database_available()
        mark_database_available()

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "Tsavo Hub Services Restored")
