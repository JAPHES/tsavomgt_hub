from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm


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


class ActivationVerificationForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="Email address")
    otp = forms.CharField(
        label="Six-digit activation code",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )

    def clean_otp(self):
        otp = self.cleaned_data["otp"].strip()
        if not otp.isdigit():
            raise forms.ValidationError("Enter the six-digit code sent to your email.")
        return otp

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class ResendOTPForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="Email address")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class ActivationPasswordForm(BootstrapFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


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
