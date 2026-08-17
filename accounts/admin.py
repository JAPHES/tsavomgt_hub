from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccountActivationOTP, User


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
            {"fields": ("role", "account_status", "email_verified", "activation_completed")},
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
                ["role", "account_status", "email_verified", "activation_completed", "is_active"]
            )
        return tuple(dict.fromkeys(fields))


@admin.register(AccountActivationOTP)
class AccountActivationOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "date_sent", "expires_at", "used_at", "attempt_count", "resend_count")
    list_filter = ("date_sent", "used_at", "invalidated_at")
    search_fields = ("user__email",)
    fields = (
        "user",
        "expires_at",
        "used_at",
        "attempt_count",
        "date_sent",
        "resend_count",
        "resent_from",
        "invalidated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
