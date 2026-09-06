from django.test import TestCase
from django.urls import reverse

from core.tests.factories import create_admin, create_innovator
from innovators.models import InnovatorProject


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
        self.client.force_login(self.administrator)

    def project_names(self, response):
        return [project.name for project in response.context["page_obj"].object_list]

    def test_directory_lists_projects_with_innovator_background(self):
        response = self.client.get(reverse("innovators:project-directory"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["matched_count"], 3)
        self.assertEqual(response.context["total_projects"], 3)
        self.assertContains(response, "Project directory")
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

    def test_general_search_finds_project_or_innovator(self):
        for search_term, expected_project in (
            ("precision agriculture", "AgriSense"),
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
            InnovatorProject.objects.create(
                profile=self.climate_innovator.innovator_profile,
                name=f"Climate Project {index:02d}",
                details="A sufficiently detailed climate technology project description.",
                area_of_focus="Climate technology",
            )

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

    def test_innovators_cannot_access_project_directory(self):
        self.client.force_login(self.climate_innovator)

        response = self.client.get(reverse("innovators:project-directory"))

        self.assertEqual(response.status_code, 403)
