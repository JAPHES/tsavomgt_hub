from django.contrib import admin

from .models import InnovatorProfile, InnovatorProject, ProjectFocusArea


@admin.register(ProjectFocusArea)
class ProjectFocusAreaAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InnovatorProject)
class InnovatorProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "focus_area_list", "created_at")
    list_filter = ("focus_areas", "created_at")
    search_fields = (
        "name",
        "focus_areas__name",
        "profile__user__email",
        "profile__user__first_name",
        "profile__user__last_name",
    )
    readonly_fields = (
        "profile",
        "name",
        "focus_areas",
        "proposal",
        "legacy_details",
        "legacy_area_of_focus",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Areas of focus")
    def focus_area_list(self, obj):
        return obj.focus_area_names

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
        "projects__focus_areas__name",
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
