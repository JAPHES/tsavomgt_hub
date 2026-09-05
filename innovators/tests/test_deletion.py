from datetime import time
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceCorrection, AttendanceSession, HubBooking
from auditlog.models import AuditLog
from auditlog.services import record_audit
from core.tests.factories import create_admin, create_innovator
from innovators.models import InnovatorProfile, InnovatorProject
from innovators.services import InnovatorDeletionError, permanently_delete_innovator


class PermanentInnovatorDeletionTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.innovator = create_innovator()
        self.profile = self.innovator.innovator_profile
        self.project = self.profile.projects.get()
        self.booking = HubBooking.objects.create(
            innovator=self.innovator,
            visit_date=timezone.localdate(),
            arrival_time=time(10, 0),
            purpose="Test permanent deletion of the innovator booking record.",
        )
        self.attendance = AttendanceSession.objects.create(
            innovator=self.innovator,
            project_name=self.project.name,
            check_in_at=timezone.now(),
        )
        self.correction = AttendanceCorrection.objects.create(
            attendance=self.attendance,
            administrator=self.admin,
            previous_values={"status": "INCOMPLETE"},
            new_values={"status": "ADMIN_CLOSED"},
            reason="Close the retained test attendance record.",
        )
        self.project_audit = record_audit(
            actor=self.innovator,
            action=AuditLog.Action.PROJECT_CREATED,
            target=self.project,
        )
        self.booking_audit = record_audit(
            actor=self.admin,
            action=AuditLog.Action.BOOKING_ADMITTED,
            target=self.booking,
        )
        self.unrelated_audit = record_audit(
            actor=self.admin,
            action=AuditLog.Action.ACCOUNT_UPDATED,
            target=self.admin,
        )
        self.client.force_login(self.admin)

    def test_confirmation_page_explains_permanent_impact_before_deletion(self):
        detail_response = self.client.get(
            reverse("innovators:detail", kwargs={"pk": self.profile.pk})
        )
        response = self.client.get(
            reverse("innovators:delete", kwargs={"pk": self.profile.pk})
        )

        self.assertContains(detail_response, "Delete innovator permanently")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete this innovator?")
        self.assertContains(response, "Are you sure you want to continue?")
        self.assertContains(response, "This action cannot be undone")
        self.assertContains(response, "Yes, permanently delete innovator")
        self.assertContains(response, "Cancel and keep account")
        self.assertTrue(User.objects.filter(pk=self.innovator.pk).exists())

    def test_post_without_explicit_confirmation_does_not_delete(self):
        response = self.client.post(
            reverse("innovators:delete", kwargs={"pk": self.profile.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm the permanent deletion")
        self.assertTrue(User.objects.filter(pk=self.innovator.pk).exists())

    def test_confirmed_deletion_removes_account_and_all_associated_records(self):
        user_id = self.innovator.pk
        profile_id = self.profile.pk
        project_id = self.project.pk
        booking_id = self.booking.pk
        attendance_id = self.attendance.pk
        correction_id = self.correction.pk
        full_name = self.innovator.get_full_name()
        email = self.innovator.email
        registration_number = self.profile.registration_number
        photo_name = "profile_photos/2026/09/innovator-photo.jpg"
        self.profile.profile_photo.name = photo_name
        self.profile.save(update_fields=["profile_photo"])
        innovator_client = Client()
        innovator_client.force_login(self.innovator)
        innovator_session_key = innovator_client.session.session_key

        with patch("innovators.services._delete_profile_photo") as delete_photo:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("innovators:delete", kwargs={"pk": profile_id}),
                    {"confirmation": "permanently-delete"},
                )
        delete_photo.assert_called_once()
        self.assertEqual(delete_photo.call_args.args[1], photo_name)

        self.assertRedirects(
            response,
            reverse("innovators:manage"),
            fetch_redirect_response=False,
        )
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(InnovatorProfile.objects.filter(pk=profile_id).exists())
        self.assertFalse(InnovatorProject.objects.filter(pk=project_id).exists())
        self.assertFalse(HubBooking.objects.filter(pk=booking_id).exists())
        self.assertFalse(AttendanceSession.objects.filter(pk=attendance_id).exists())
        self.assertFalse(AttendanceCorrection.objects.filter(pk=correction_id).exists())
        self.assertFalse(Session.objects.filter(session_key=innovator_session_key).exists())
        self.assertFalse(AuditLog.objects.filter(pk=self.project_audit.pk).exists())
        self.assertFalse(AuditLog.objects.filter(pk=self.booking_audit.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=self.unrelated_audit.pk).exists())

        deletion_audit = AuditLog.objects.get(action=AuditLog.Action.ACCOUNT_DELETED)
        self.assertEqual(deletion_audit.actor, self.admin)
        self.assertEqual(deletion_audit.target_repr, "Deleted innovator account")
        self.assertEqual(deletion_audit.target_id, "")
        audit_content = (
            f"{deletion_audit.target_repr} {deletion_audit.target_id} "
            f"{deletion_audit.new_values} {deletion_audit.reason}"
        ).lower()
        for personal_value in (full_name, email, registration_number):
            self.assertNotIn(personal_value.lower(), audit_content)

        first_refresh = self.client.get(reverse("innovators:manage"))
        self.assertContains(first_refresh, "all associated records were permanently deleted")
        self.assertNotContains(first_refresh, full_name)
        self.assertNotContains(first_refresh, email)
        self.assertNotContains(first_refresh, registration_number)
        self.assertRedirects(
            innovator_client.get(reverse("dashboard:innovator")),
            f"{reverse('accounts:login')}?next={reverse('dashboard:innovator')}",
        )
        self.assertEqual(
            self.client.get(
                reverse("innovators:detail", kwargs={"pk": profile_id})
            ).status_code,
            404,
        )

    def test_innovator_cannot_open_or_submit_permanent_deletion(self):
        route = reverse("innovators:delete", kwargs={"pk": self.profile.pk})
        self.client.force_login(self.innovator)

        self.assertEqual(self.client.get(route).status_code, 403)
        self.assertEqual(
            self.client.post(
                route,
                {"confirmation": "permanently-delete"},
            ).status_code,
            403,
        )
        self.assertTrue(User.objects.filter(pk=self.innovator.pk).exists())

    def test_service_rejects_a_non_administrator(self):
        other_innovator = create_innovator(
            email="other@example.com",
            registration_number="TTU/INN/002",
        )

        with self.assertRaisesMessage(
            InnovatorDeletionError,
            "Only an administrator can permanently delete an innovator.",
        ):
            permanently_delete_innovator(self.profile, actor=other_innovator)

        self.assertTrue(User.objects.filter(pk=self.innovator.pk).exists())
