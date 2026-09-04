from unittest.mock import Mock, patch

from cloudinary.exceptions import NotFound
from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from core.storage import CloudinaryMediaStorage


class CloudinaryMediaStorageTests(SimpleTestCase):
    def setUp(self):
        self.storage = CloudinaryMediaStorage()

    @patch("core.storage.get_random_string", return_value="abc123def456")
    @patch("core.storage.uploader.upload")
    def test_save_uses_a_unique_public_id_and_returns_cloudinary_name(
        self, upload, random_string
    ):
        upload.return_value = {
            "public_id": "profile_photos/2026/09/avatar_abc123def456",
            "format": "jpg",
        }
        content = ContentFile(b"image bytes", name="avatar.jpg")

        saved_name = self.storage.save(
            "profile_photos/2026/09/avatar.jpg",
            content,
        )

        self.assertEqual(
            saved_name,
            "profile_photos/2026/09/avatar_abc123def456.jpg",
        )
        upload.assert_called_once_with(
            content,
            public_id="profile_photos/2026/09/avatar_abc123def456",
            overwrite=False,
            resource_type="image",
        )
        random_string.assert_called_once_with(12)

    @patch("core.storage.cloudinary_url")
    def test_url_is_always_secure(self, build_url):
        build_url.return_value = (
            "https://res.cloudinary.com/example/image/upload/profile/avatar.jpg",
            {},
        )

        url = self.storage.url("profile/avatar.jpg")

        self.assertTrue(url.startswith("https://"))
        build_url.assert_called_once_with(
            "profile/avatar.jpg",
            resource_type="image",
            secure=True,
        )

    @patch("core.storage.uploader.destroy")
    def test_delete_invalidates_the_remote_asset(self, destroy):
        self.storage.delete("profile/avatar.jpg")

        destroy.assert_called_once_with(
            "profile/avatar",
            invalidate=True,
            resource_type="image",
        )

    @patch("core.storage.api.resource")
    def test_exists_handles_missing_remote_asset(self, resource):
        resource.side_effect = NotFound("missing")

        self.assertFalse(self.storage.exists("profile/avatar.jpg"))

    @patch("core.storage.requests.get")
    @patch.object(CloudinaryMediaStorage, "url", return_value="https://example.test/avatar.jpg")
    def test_open_downloads_remote_content(self, build_url, get):
        response = Mock(content=b"remote image")
        response.raise_for_status.return_value = None
        get.return_value = response

        opened = self.storage.open("profile/avatar.jpg")

        self.assertEqual(opened.read(), b"remote image")
        get.assert_called_once_with("https://example.test/avatar.jpg", timeout=30)
        build_url.assert_called_once_with("profile/avatar.jpg")
