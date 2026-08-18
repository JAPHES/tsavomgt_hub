import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_kenyan_phone(value):
    compact = re.sub(r"[\s-]", "", value or "")
    if not re.fullmatch(r"(?:\+254|0)(?:7|1)\d{8}", compact):
        raise ValidationError("Enter a valid Kenyan mobile number, for example 0712345678.")


class InnovatorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="innovator_profile"
    )
    registration_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20, validators=[validate_kenyan_phone])
    innovation_project_name = models.CharField(max_length=200)
    profile_photo = models.ImageField(upload_to="profile_photos/%Y/%m/", null=True, blank=True)
    project_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    def clean(self):
        if self.user_id and self.user.role != self.user.Role.INNOVATOR:
            raise ValidationError({"user": "Only innovator users can have an innovator profile."})

    def save(self, *args, **kwargs):
        self.registration_number = self.registration_number.strip().upper()
        self.phone_number = re.sub(r"[\s-]", "", self.phone_number or "")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.registration_number})"
