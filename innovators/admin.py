from django.contrib import admin

from .models import InnovatorProfile


@admin.register(InnovatorProfile)
class InnovatorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "user",
        "innovation_project_name",
    )
    search_fields = (
        "registration_number",
        "user__email",
        "user__first_name",
        "user__last_name",
        "innovation_project_name",
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
