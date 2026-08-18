from django.contrib import admin

from .models import AttendanceCorrection, AttendanceSession


class AttendanceCorrectionInline(admin.TabularInline):
    model = AttendanceCorrection
    extra = 0
    can_delete = False
    readonly_fields = (
        "administrator",
        "previous_values",
        "new_values",
        "reason",
        "created_at",
    )


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "innovator",
        "project_name",
        "check_in_at",
        "check_out_at",
        "status",
    )
    list_filter = ("status", "check_in_at", "check_out_at")
    search_fields = (
        "innovator__email",
        "innovator__first_name",
        "innovator__last_name",
        "innovator__innovator_profile__registration_number",
        "project_name",
    )
    readonly_fields = (
        "innovator",
        "project_name",
        "work_completed",
        "challenges_encountered",
        "check_in_at",
        "check_out_at",
        "status",
        "corrected_by",
        "correction_reason",
        "corrected_at",
        "created_at",
        "updated_at",
    )
    inlines = [AttendanceCorrectionInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(admin.ModelAdmin):
    list_display = ("attendance", "administrator", "reason", "created_at")
    list_filter = ("created_at",)
    search_fields = ("attendance__innovator__email", "administrator__email", "reason")
    readonly_fields = (
        "attendance",
        "administrator",
        "previous_values",
        "new_values",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
