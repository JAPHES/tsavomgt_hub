from django.test import TestCase
from django.urls import reverse

from core.tests.factories import create_admin, create_innovator
from innovators.models import InnovatorProject, ProjectFocusArea


class ProjectDirectoryTests(TestCase):
    def setUp(self):
        self.administrator = create_admin()
        self.climate_innovator = create_innovator(
            project="BlueWatch",
            area_of_focus="Climate technology",
            school="School of Science and Informatics",
            department="Informatics and Computing",
            county="Taita Taveta",
        )
        self.agriculture_innovator = create_innovator(
            email="peter@example.com",
            registration_number="TTU/INN/002",
            first_name="Peter",
            last_name="Mwangi",
            project="AgriSense",
            project_details="A precision agriculture platform for monitoring soil and crop health.",
            area_of_focus="Agricultural technology",
            school="School of Agriculture",
            department="Crop Sciences",
            county="Mombasa",
        )
        self.health_innovator = create_innovator(
            email="neema@example.com",
            registration_number="TTU/INN/003",
            first_name="Neema",
            last_name="Mwangeka",
            project="Afya Link",
            project_details="A community health referral and patient follow-up platform.",
            area_of_focus="Health technology",
            school="School of Health Sciences",
            department="Nursing",
            county="Kilifi",
        )
        self.climate_focus = ProjectFocusArea.objects.get(name="Climate technology")
        self.client.force_login(self.administrator)

    def project_names(self, response):
        return [project.name for project in response.context["page_obj"].object_list]

    def test_directory_lists_projects_with_innovator_background(self):
        response = self.client.get(reverse("innovators:project-directory"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["matched_count"], 3)
        self.assertEqual(response.context["total_projects"], 3)
        self.assertContains(response, 'class="project-directory-intro-card"')
        self.assertContains(response, "Explore hub innovations")
        self.assertContains(response, "Combine only the filters relevant to your search.")
        self.assertNotContains(response, '<p class="eyebrow">Administration</p>', html=True)
        self.assertNotContains(
            response,
            '<h1 id="project-directory-heading">Project directory</h1>',
            html=True,
        )
        self.assertNotContains(response, "View innovators")
        self.assertNotContains(response, "projects from")
        self.assertNotContains(response, "registered projects in total")
        self.assertContains(response, 'class="table mobile-card-table')
        self.assertContains(response, reverse("innovators:project-directory"))
        self.assertContains(response, "BlueWatch")
        self.assertContains(response, "AgriSense")
        self.assertContains(response, "Afya Link")
        self.assertContains(response, "Climate technology")
        self.assertContains(response, "School of Agriculture")
        self.assertContains(response, "Crop Sciences")
        self.assertContains(response, "Mombasa")
        self.assertContains(
            response,
            reverse(
                "innovators:detail",
                kwargs={"pk": self.agriculture_innovator.innovator_profile.pk},
            ),
        )
        self.assertEqual(
            list(response.context["form"].fields),
            [
                "query",
                "technology_focus",
                "county",
                "area_of_study",
                "school",
                "department",
                "result_view",
                "sort_by",
            ],
        )

    def test_filters_by_technology_focus_and_county(self):
        response = self.client.get(
            reverse("innovators:project-directory"),
            {"technology_focus": "Agricultural technology"},
        )
        self.assertEqual(self.project_names(response), ["AgriSense"])
        self.assertTrue(response.context["filter_applied"])

        response = self.client.get(
            reverse("innovators:project-directory"),
            {"county": "Kilifi"},
        )
        self.assertEqual(self.project_names(response), ["Afya Link"])

    def test_area_of_study_searches_school_and_department(self):
        for search_term, expected_project in (
            ("Agriculture", "AgriSense"),
            ("Nursing", "Afya Link"),
            ("Informatics", "BlueWatch"),
        ):
            with self.subTest(search_term=search_term):
                response = self.client.get(
                    reverse("innovators:project-directory"),
                    {"area_of_study": search_term},
                )
                self.assertEqual(self.project_names(response), [expected_project])

    def test_filters_school_and_department_independently(self):
        response = self.client.get(
            reverse("innovators:project-directory"),
            {"school": "Health", "department": "Nursing"},
        )

        self.assertEqual(self.project_names(response), ["Afya Link"])
        self.assertNotContains(response, "AgriSense")

    def test_combines_only_the_selected_geographical_and_department_filters(self):
        response = self.client.get(
            reverse("innovators:project-directory"),
            {"county": "Mombasa", "department": "Crop Sciences"},
        )

        self.assertEqual(self.project_names(response), ["AgriSense"])
        self.assertEqual(response.context["matched_innovator_count"], 1)
        self.assertNotContains(response, "Afya Link")

    def test_technology_choices_only_come_from_registered_projects(self):
        response = self.client.get(reverse("innovators:project-directory"))

        choices = dict(response.context["form"].fields["technology_focus"].choices)
        self.assertIn("Climate technology", choices)
        self.assertIn("Agricultural technology", choices)
        self.assertNotIn("Unregistered technology", choices)

        invalid_response = self.client.get(
            reverse("innovators:project-directory"),
            {"technology_focus": "Unregistered technology"},
        )
        self.assertEqual(invalid_response.context["matched_count"], 0)
        self.assertFormError(
            invalid_response.context["form"],
            "technology_focus",
            "Select a valid choice. Unregistered technology is not one of the available choices.",
        )

    def test_general_search_finds_project_or_innovator(self):
        for search_term, expected_project in (
            ("AgriSense", "AgriSense"),
            ("Neema", "Afya Link"),
            ("TTU/INN/001", "BlueWatch"),
        ):
            with self.subTest(search_term=search_term):
                response = self.client.get(
                    reverse("innovators:project-directory"),
                    {"query": search_term},
                )
                self.assertEqual(self.project_names(response), [expected_project])

    def test_administrator_can_sort_directory_by_each_requested_category(self):
        expected_orders = {
            "project": ["Afya Link", "AgriSense", "BlueWatch"],
            "technology": ["AgriSense", "BlueWatch", "Afya Link"],
            "innovator": ["BlueWatch", "Afya Link", "AgriSense"],
            "county": ["Afya Link", "AgriSense", "BlueWatch"],
            "school": ["AgriSense", "Afya Link", "BlueWatch"],
            "department": ["AgriSense", "BlueWatch", "Afya Link"],
        }

        for sort_by, expected_projects in expected_orders.items():
            with self.subTest(sort_by=sort_by):
                response = self.client.get(
                    reverse("innovators:project-directory"),
                    {"sort_by": sort_by},
                )
                self.assertEqual(self.project_names(response), expected_projects)

    def test_pagination_keeps_active_filters_and_sorting(self):
        for index in range(30):
            project = InnovatorProject.objects.create(
                profile=self.climate_innovator.innovator_profile,
                name=f"Climate Project {index:02d}",
            )
            project.focus_areas.add(self.climate_focus)

        response = self.client.get(
            reverse("innovators:project-directory"),
            {
                "technology_focus": "Climate technology",
                "sort_by": "project",
            },
        )

        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(
            response,
            "?technology_focus=Climate+technology&amp;sort_by=project&amp;page=2",
        )

    def test_unique_innovator_view_removes_duplicate_people(self):
        project = InnovatorProject.objects.create(
            profile=self.climate_innovator.innovator_profile,
            name="Eco Monitor",
        )
        project.focus_areas.add(self.climate_focus)

        response = self.client.get(
            reverse("innovators:project-directory"),
            {
                "county": "Taita Taveta",
                "result_view": "innovators",
            },
        )

        profiles = list(response.context["page_obj"].object_list)
        self.assertEqual(profiles, [self.climate_innovator.innovator_profile])
        self.assertEqual(response.context["matched_count"], 2)
        self.assertEqual(response.context["matched_innovator_count"], 1)
        self.assertEqual(profiles[0].matching_project_count, 2)
        self.assertContains(response, "Unique innovators")

    def test_innovators_cannot_access_project_directory(self):
        self.client.force_login(self.climate_innovator)

        response = self.client.get(reverse("innovators:project-directory"))

        self.assertEqual(response.status_code, 403)
