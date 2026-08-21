from django.contrib import admin

from .models import InnovatorProfile, InnovatorProject


@admin.register(InnovatorProject)
class InnovatorProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "area_of_focus", "created_at")
    list_filter = ("area_of_focus", "created_at")
    search_fields = (
        "name",
        "details",
        "area_of_focus",
        "profile__user__email",
        "profile__user__first_name",
        "profile__user__last_name",
    )
    readonly_fields = (
        "profile",
        "name",
        "details",
        "area_of_focus",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InnovatorProfile)
class InnovatorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "user",
        "project_count",
    )
    search_fields = (
        "registration_number",
        "user__email",
        "user__first_name",
        "user__last_name",
        "projects__name",
        "projects__area_of_focus",
    )
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("projects")

    @admin.display(description="Projects")
    def project_count(self, obj):
        return len(obj.projects.all())

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
