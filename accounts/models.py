from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        INNOVATOR = "INNOVATOR", "Innovator"
        CHAIRPERSON = "CHAIRPERSON", "Chairperson (read-only)"

    class AccountStatus(models.TextChoices):
        PENDING = "PENDING", "Password change required"
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    username = None
    date_joined = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INNOVATOR)
    account_status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.PENDING
    )
    email_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name", "email"]

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        super().save(*args, **kwargs)

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN

    @property
    def is_innovator(self):
        return self.role == self.Role.INNOVATOR

    def __str__(self):
        return self.get_full_name() or self.email
