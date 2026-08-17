from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "actor", "target_model", "target_repr", "ip_address")
    list_filter = ("action", "target_model", "timestamp")
    search_fields = ("actor__email", "target_repr", "target_id", "reason")
    readonly_fields = (
        "actor",
        "action",
        "target_model",
        "target_id",
        "target_repr",
        "previous_values",
        "new_values",
        "reason",
        "ip_address",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
