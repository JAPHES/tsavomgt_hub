from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        ACCOUNT_CREATED = "ACCOUNT_CREATED", "Innovator account added"
        ACCOUNT_UPDATED = "ACCOUNT_UPDATED", "Account updated"
        ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", "Account activated"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", "Account deactivated"
        TEMPORARY_CREDENTIALS_REISSUED = (
            "TEMPORARY_CREDENTIALS_REISSUED",
            "Temporary login credentials reissued",
        )
        ATTENDANCE_CORRECTED = "ATTENDANCE_CORRECTED", "Attendance corrected"
        INCOMPLETE_SESSION_CLOSED = "INCOMPLETE_SESSION_CLOSED", "Incomplete session closed"
        ROLE_CHANGED = "ROLE_CHANGED", "User role changed"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions",
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} at {self.timestamp:%Y-%m-%d %H:%M}"
