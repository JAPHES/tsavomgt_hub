from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import User


class ProjectProposalMigrationTests(TransactionTestCase):
    migrate_from = [("innovators", "0006_add_required_profile_details")]
    migrate_to = [("innovators", "0007_project_proposals_and_focus_areas")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        InnovatorProfile = old_apps.get_model("innovators", "InnovatorProfile")
        InnovatorProject = old_apps.get_model("innovators", "InnovatorProject")
        user = User.objects.create(
            email="migration-project@example.com",
            password="!",
            first_name="Legacy",
            last_name="Innovator",
            role="INNOVATOR",
            account_status="ACTIVE",
            is_active=True,
        )
        profile = InnovatorProfile.objects.create(
            user_id=user.pk,
            registration_number="TTU/MIG/001",
            phone_number="0712345678",
        )
        self.project_id = InnovatorProject.objects.create(
            profile=profile,
            name="Legacy Climate Project",
            details="A valuable description entered before proposal uploads were available.",
            area_of_focus="Climate technology",
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def test_existing_project_information_and_focus_are_preserved(self):
        InnovatorProject = self.apps.get_model("innovators", "InnovatorProject")
        ProjectFocusArea = self.apps.get_model("innovators", "ProjectFocusArea")

        project = InnovatorProject.objects.get(pk=self.project_id)
        self.assertEqual(project.legacy_area_of_focus, "Climate technology")
        self.assertIn("valuable description", project.legacy_details)
        self.assertEqual(
            list(project.focus_areas.values_list("name", flat=True)),
            ["Climate technology"],
        )
        self.assertFalse(project.proposal)
        self.assertTrue(
            ProjectFocusArea.objects.filter(
                name="Artificial Intelligence and Machine Learning"
            ).exists()
        )
