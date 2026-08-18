from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "account_status", "is_active")
    list_filter = ("role", "account_status", "email_verified", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("last_login", "date_created", "date_updated")
    fieldsets = (
        (None, {"fields": ("email",)}),
        ("Personal information", {"fields": ("first_name", "last_name")}),
        (
            "Hub access",
            {"fields": ("role", "account_status", "email_verified", "must_change_password")},
        ),
        ("Django permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_created", "date_updated")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2", "role"),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.extend(
                ["role", "account_status", "email_verified", "must_change_password", "is_active"]
            )
        return tuple(dict.fromkeys(fields))
