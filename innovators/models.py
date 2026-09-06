import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinLengthValidator
from django.db import models
from django.utils.text import slugify


KENYAN_COUNTIES = (
    "Baringo",
    "Bomet",
    "Bungoma",
    "Busia",
    "Elgeyo-Marakwet",
    "Embu",
    "Garissa",
    "Homa Bay",
    "Isiolo",
    "Kajiado",
    "Kakamega",
    "Kericho",
    "Kiambu",
    "Kilifi",
    "Kirinyaga",
    "Kisii",
    "Kisumu",
    "Kitui",
    "Kwale",
    "Laikipia",
    "Lamu",
    "Machakos",
    "Makueni",
    "Mandera",
    "Marsabit",
    "Meru",
    "Migori",
    "Mombasa",
    "Murang'a",
    "Nairobi",
    "Nakuru",
    "Nandi",
    "Narok",
    "Nyamira",
    "Nyandarua",
    "Nyeri",
    "Samburu",
    "Siaya",
    "Taita Taveta",
    "Tana River",
    "Tharaka-Nithi",
    "Trans Nzoia",
    "Turkana",
    "Uasin Gishu",
    "Vihiga",
    "Wajir",
    "West Pokot",
)


def validate_kenyan_phone(value):
    compact = re.sub(r"[\s-]", "", value or "")
    if not re.fullmatch(r"(?:\+254|0)(?:7|1)\d{8}", compact):
        raise ValidationError("Enter a valid Kenyan mobile number, for example 0712345678.")


def project_proposal_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    project_name = slugify(instance.name)[:70] or "project"
    return (
        f"project_proposals/{instance.profile_id}/"
        f"{project_name}-{uuid.uuid4().hex}{extension}"
    )


class InnovatorProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="innovator_profile"
    )
    registration_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20, validators=[validate_kenyan_phone])
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default="")
    school = models.CharField(max_length=200, blank=True, default="")
    department = models.CharField(max_length=200, blank=True, default="")
    county = models.CharField(
        max_length=30,
        choices=[(county, county) for county in KENYAN_COUNTIES],
        blank=True,
        default="",
    )
    # Retained for backward database compatibility. New projects live in InnovatorProject.
    innovation_project_name = models.CharField(max_length=200, blank=True, default="")
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
        self.school = " ".join((self.school or "").split())
        self.department = " ".join((self.department or "").split())
        super().save(*args, **kwargs)

    @property
    def has_completed_required_details(self):
        return all(
            (getattr(self, field, "") or "").strip()
            for field in ("gender", "school", "department", "county")
        )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.registration_number})"


class ProjectFocusArea(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = " ".join((self.name or "").split())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InnovatorProject(models.Model):
    profile = models.ForeignKey(
        InnovatorProfile,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=200, validators=[MinLengthValidator(2)])
    focus_areas = models.ManyToManyField(ProjectFocusArea, related_name="projects")
    proposal = models.FileField(
        upload_to=project_proposal_upload_to,
        validators=[FileExtensionValidator(["pdf"])],
        max_length=500,
        blank=True,
    )
    # Retain information entered before proposal uploads and multiple focus
    # areas were introduced. New project forms do not expose these fields.
    legacy_details = models.TextField(blank=True, default="", editable=False)
    legacy_area_of_focus = models.CharField(
        max_length=150,
        blank=True,
        default="",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "name"],
                name="unique_project_name_per_innovator",
                violation_error_message="You already have a project with this name.",
            )
        ]
        indexes = [
            models.Index(fields=["profile", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join((self.name or "").split())
        super().save(*args, **kwargs)

    @property
    def focus_area_names(self):
        return ", ".join(focus.name for focus in self.focus_areas.all())

    def __str__(self):
        return f"{self.name} — {self.profile.user}"
