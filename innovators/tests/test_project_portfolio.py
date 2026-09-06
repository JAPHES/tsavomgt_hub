from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from auditlog.models import AuditLog
from core.tests.factories import create_admin, create_innovator
from innovators.models import InnovatorProject, ProjectFocusArea


def pdf_upload(name="proposal.pdf", content=b"%PDF-1.4\nTest project proposal"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class ProjectPortfolioTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_directory = TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_directory.name)
        cls.media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls.media_override.disable()
            cls.media_directory.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.owner = create_innovator()
        cls.other_innovator = create_innovator(
            email="other-project-owner@example.com",
            registration_number="TTU/INN/909",
        )
        cls.administrator = create_admin()
        cls.focus_areas = [
            ProjectFocusArea.objects.get_or_create(name=name)[0]
            for name in (
                "Artificial Intelligence and Machine Learning",
                "Internet of Things",
                "Health and Medical Technology",
            )
        ]

    def create_uploaded_project(self, name="Smart Lab"):
        project = InnovatorProject.objects.create(
            profile=self.owner.innovator_profile,
            name=name,
            proposal=pdf_upload(),
        )
        project.focus_areas.add(self.focus_areas[0])
        return project

    def test_create_form_replaces_details_with_proposal_and_multiple_focuses(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("innovators:projects"))

        self.assertEqual(list(page.context["form"].fields), ["name", "focus_areas", "proposal"])
        self.assertContains(page, 'enctype="multipart/form-data"')
        self.assertNotContains(page, "Project details")
        self.assertGreaterEqual(
            page.context["form"].fields["focus_areas"].queryset.count(),
            18,
        )
        existing_project = self.owner.innovator_profile.projects.get(name="BlueWatch")
        self.assertContains(
            page,
            reverse("innovators:project-update", kwargs={"pk": existing_project.pk}),
        )

        response = self.client.post(
            reverse("innovators:projects"),
            {
                "name": "Connected Clinic",
                "focus_areas": [focus.pk for focus in self.focus_areas],
                "proposal": pdf_upload("connected-clinic.pdf"),
            },
        )

        self.assertRedirects(response, reverse("innovators:projects"))
        project = InnovatorProject.objects.get(name="Connected Clinic")
        self.assertEqual(project.focus_areas.count(), 3)
        self.assertTrue(project.proposal.name.endswith(".pdf"))
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.owner,
                action=AuditLog.Action.PROJECT_CREATED,
                target_id=str(project.pk),
            ).exists()
        )

    def test_create_rejects_a_file_that_is_not_a_real_pdf(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("innovators:projects"),
            {
                "name": "Invalid Proposal",
                "focus_areas": [self.focus_areas[0].pk],
                "proposal": pdf_upload(content=b"This is not a PDF file"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a valid PDF project proposal")
        self.assertFalse(InnovatorProject.objects.filter(name="Invalid Proposal").exists())

    def test_legacy_project_requires_a_proposal_when_it_is_updated(self):
        project = self.owner.innovator_profile.projects.get(name="BlueWatch")
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("innovators:project-update", kwargs={"pk": project.pk}),
            {
                "name": project.name,
                "focus_areas": [self.focus_areas[0].pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        project.refresh_from_db()
        self.assertFalse(project.proposal)

    def test_owner_can_update_name_focus_areas_and_proposal(self):
        project = self.create_uploaded_project()
        old_proposal_name = project.proposal.name
        old_storage = project.proposal.storage
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("innovators:project-update", kwargs={"pk": project.pk}),
                {
                    "name": "Smart Laboratory",
                    "focus_areas": [focus.pk for focus in self.focus_areas],
                    "proposal": pdf_upload("smart-laboratory.pdf", b"%PDF-1.5\nUpdated"),
                },
            )

        self.assertRedirects(response, reverse("innovators:projects"))
        project.refresh_from_db()
        self.assertEqual(project.name, "Smart Laboratory")
        self.assertEqual(project.focus_areas.count(), 3)
        self.assertNotEqual(project.proposal.name, old_proposal_name)
        self.assertFalse(old_storage.exists(old_proposal_name))
        update_audit = AuditLog.objects.get(
            actor=self.owner,
            action=AuditLog.Action.PROJECT_UPDATED,
            target_id=str(project.pk),
        )
        self.assertEqual(update_audit.previous_values["name"], "Smart Lab")
        self.assertEqual(update_audit.new_values["name"], "Smart Laboratory")

    def test_owner_can_update_project_without_replacing_existing_proposal(self):
        project = self.create_uploaded_project()
        original_proposal_name = project.proposal.name
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("innovators:project-update", kwargs={"pk": project.pk}),
            {
                "name": "Renamed Smart Lab",
                "focus_areas": [self.focus_areas[1].pk],
            },
        )

        self.assertRedirects(response, reverse("innovators:projects"))
        project.refresh_from_db()
        self.assertEqual(project.proposal.name, original_proposal_name)
        self.assertEqual(
            list(project.focus_areas.values_list("name", flat=True)),
            ["Internet of Things"],
        )

    def test_another_innovator_cannot_update_or_download_project(self):
        project = self.create_uploaded_project()
        self.client.force_login(self.other_innovator)

        edit_response = self.client.get(
            reverse("innovators:project-update", kwargs={"pk": project.pk})
        )
        download_response = self.client.get(
            reverse("innovators:project-proposal", kwargs={"pk": project.pk})
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(download_response.status_code, 403)

    def test_owner_and_administrator_can_download_proposal(self):
        project = self.create_uploaded_project()
        proposal_url = reverse("innovators:project-proposal", kwargs={"pk": project.pk})

        for user in (self.owner, self.administrator):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(proposal_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertIn("attachment;", response["Content-Disposition"])
                self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF-"))
