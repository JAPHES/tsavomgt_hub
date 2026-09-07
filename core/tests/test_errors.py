from django.test import TestCase, override_settings
from django.urls import reverse

from .factories import create_admin


@override_settings(DEBUG=True)
class CustomNotFoundPageTests(TestCase):
    def assert_custom_not_found(self, response, requested_path):
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["X-Tsavo-Error-Page"], "404")
        self.assertTemplateUsed(response, "errors/404.html")
        self.assertContains(response, "This page is not available", status_code=404)
        self.assertContains(response, requested_path, status_code=404)
        if response.wsgi_request.user.is_authenticated:
            self.assertContains(response, "Go back to dashboard", status_code=404)
            self.assertContains(
                response,
                f'href="{reverse("dashboard:index")}"',
                status_code=404,
            )
            self.assertNotContains(response, "Return to sign in", status_code=404)
        else:
            self.assertContains(response, "Return to sign in", status_code=404)
            self.assertContains(
                response,
                f'href="{reverse("accounts:login")}"',
                status_code=404,
            )
            self.assertNotContains(response, "Go back to dashboard", status_code=404)
        self.assertNotContains(response, "Using the URLconf", status_code=404)

    def test_missing_public_url_uses_custom_page_in_debug_mode(self):
        requested_path = "/page-that-does-not-exist/"

        response = self.client.get(requested_path)

        self.assert_custom_not_found(response, requested_path)

    def test_missing_admin_url_uses_custom_page_in_debug_mode(self):
        administrator = create_admin()
        administrator.is_superuser = True
        administrator.save(update_fields=["is_superuser"])
        self.client.force_login(administrator)

        requested_path = "/admin/not-a-real-section/"
        response = self.client.get(requested_path)

        self.assert_custom_not_found(response, requested_path)

    def test_django_admin_login_is_hidden_behind_custom_not_found_page(self):
        requested_path = "/admin/login/"

        response = self.client.get(f"{requested_path}?next=/admin/")

        self.assert_custom_not_found(response, requested_path)
        self.assertNotContains(response, "Django administration", status_code=404)

    def test_anonymous_admin_root_redirects_to_hidden_login_page(self):
        response = self.client.get("/admin/", follow=True)

        self.assertEqual(
            response.redirect_chain,
            [("/admin/login/?next=/admin/", 302)],
        )
        self.assert_custom_not_found(response, "/admin/login/")

    def test_authenticated_staff_can_still_open_database_admin(self):
        administrator = create_admin()
        self.client.force_login(administrator)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site administration")

    def test_missing_application_object_uses_custom_page_in_debug_mode(self):
        administrator = create_admin()
        self.client.force_login(administrator)
        requested_path = reverse(
            "attendance:admin-detail",
            kwargs={"pk": 999999999},
        )

        response = self.client.get(requested_path)

        self.assert_custom_not_found(response, requested_path)
