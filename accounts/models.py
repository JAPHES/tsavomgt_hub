from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        INNOVATOR = "INNOVATOR", "Innovator"
        CHAIRPERSON = "CHAIRPERSON", "Chairperson (read-only)"

    class AccountStatus(models.TextChoices):
        PENDING = "PENDING", "Pending activation"
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
    activation_completed = models.BooleanField(default=False)
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


class AccountActivationOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activation_otps"
    )
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    date_sent = models.DateTimeField(auto_now_add=True)
    resend_count = models.PositiveSmallIntegerField(default=0)
    resent_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="resends"
    )
    invalidated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_sent"]
        indexes = [models.Index(fields=["user", "used_at", "expires_at"])]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return self.used_at is None and self.invalidated_at is None and not self.is_expired

    def __str__(self):
        return f"Activation code for {self.user.email} sent {self.date_sent:%Y-%m-%d %H:%M}"
