from pathlib import PurePosixPath

import requests
from cloudinary import api, uploader
from cloudinary.exceptions import NotFound
from cloudinary.utils import cloudinary_url
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.crypto import get_random_string
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryMediaStorage(Storage):
    """Store user-uploaded images in Cloudinary through authenticated HTTPS calls."""

    resource_type = "image"

    @staticmethod
    def _normalise_name(name):
        return str(PurePosixPath(str(name).replace("\\", "/")))

    @classmethod
    def _public_id(cls, name):
        return str(PurePosixPath(cls._normalise_name(name)).with_suffix(""))

    def get_available_name(self, name, max_length=None):
        path = PurePosixPath(self._normalise_name(name))
        directory = "" if str(path.parent) == "." else f"{path.parent}/"
        suffix = path.suffix.lower()
        random_suffix = f"_{get_random_string(12)}{suffix}"
        stem = path.stem

        if max_length is not None:
            available_stem_length = max_length - len(directory) - len(random_suffix)
            if available_stem_length < 1:
                raise SuspiciousFileOperation(
                    f'Cloudinary cannot create an available filename for "{name}".'
                )
            stem = stem[:available_stem_length]

        return f"{directory}{stem}{random_suffix}"

    def _save(self, name, content):
        response = uploader.upload(
            content,
            public_id=self._public_id(name),
            overwrite=False,
            resource_type=self.resource_type,
        )
        try:
            public_id = response["public_id"]
            image_format = response["format"]
        except KeyError as exc:
            raise OSError("Cloudinary returned an incomplete upload response.") from exc
        return f"{public_id}.{image_format}"

    def _open(self, name, mode="rb"):
        if mode not in {"r", "rb"}:
            raise ValueError("Cloudinary media can only be opened for reading.")
        response = requests.get(self.url(name), timeout=30)
        response.raise_for_status()
        return ContentFile(response.content, name=PurePosixPath(name).name)

    def delete(self, name):
        if name:
            uploader.destroy(
                self._public_id(name),
                invalidate=True,
                resource_type=self.resource_type,
            )

    def exists(self, name):
        try:
            api.resource(self._public_id(name), resource_type=self.resource_type)
        except NotFound:
            return False
        return True

    def size(self, name):
        resource = api.resource(self._public_id(name), resource_type=self.resource_type)
        return resource["bytes"]

    def url(self, name):
        url, _ = cloudinary_url(
            self._normalise_name(name),
            resource_type=self.resource_type,
            secure=True,
        )
        return url
