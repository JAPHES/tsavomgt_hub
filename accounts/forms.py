from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)


class BootstrapFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.EmailField(label="Email address", widget=forms.EmailInput(attrs={"autofocus": True}))
    error_messages = {
        "invalid_login": "Unable to log in with the supplied email and password.",
        "inactive": "This account is inactive. Please contact the hub administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class TsavoSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Enter your new password",
                "spellcheck": "false",
                "autofocus": True,
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Enter the new password again",
                "spellcheck": "false",
            }
        )
        self.apply_bootstrap()


class FirstLoginPasswordChangeForm(TsavoSetPasswordForm):
    pass


class TsavoPasswordResetConfirmForm(TsavoSetPasswordForm):
    pass


class TsavoPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def get_users(self, email):
        return (user for user in super().get_users(email) if not user.must_change_password)


class TsavoPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_settings = {
            "old_password": ("Current password", "Enter your current password", "current-password"),
            "new_password1": ("New password", "Enter your new password", "new-password"),
            "new_password2": ("Confirm new password", "Enter the new password again", "new-password"),
        }
        for name, (label, placeholder, autocomplete) in field_settings.items():
            field = self.fields[name]
            field.label = label
            field.widget.attrs.update(
                {
                    "autocomplete": autocomplete,
                    "placeholder": placeholder,
                    "spellcheck": "false",
                }
            )
        self.fields["old_password"].widget.attrs["autofocus"] = True
        self.apply_bootstrap()
