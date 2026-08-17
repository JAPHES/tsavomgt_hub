from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import InnovatorProfile, validate_kenyan_phone


class InnovatorCreateForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    registration_number = forms.CharField(max_length=50, label="Registration or staff number")
    phone_number = forms.CharField(max_length=20)
    innovation_project_name = forms.CharField(max_length=200, label="Innovation / project name")
    account_status = forms.ChoiceField(
        choices=[(User.AccountStatus.PENDING, "Pending activation")],
        initial=User.AccountStatus.PENDING,
        help_text="New accounts remain pending until the innovator verifies the emailed code.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean_registration_number(self):
        number = self.cleaned_data["registration_number"].strip().upper()
        if InnovatorProfile.objects.filter(registration_number__iexact=number).exists():
            raise forms.ValidationError("This registration or staff number is already in use.")
        return number

    def clean_phone_number(self):
        value = self.cleaned_data["phone_number"]
        validate_kenyan_phone(value)
        return value

class InnovatorAdminUpdateForm(BootstrapFormMixin, forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = InnovatorProfile
        fields = [
            "first_name",
            "last_name",
            "email",
            "registration_number",
            "phone_number",
            "innovation_project_name",
            "profile_photo",
            "biography",
            "project_description",
        ]
        widgets = {
            "biography": forms.Textarea(attrs={"rows": 3}),
            "project_description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.instance.user.first_name
        self.fields["last_name"].initial = self.instance.user.last_name
        self.fields["email"].initial = self.instance.user.email
        self.apply_bootstrap()

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean_registration_number(self):
        number = self.cleaned_data["registration_number"].strip().upper()
        if InnovatorProfile.objects.filter(registration_number__iexact=number).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This registration or staff number is already in use.")
        return number

class InnovatorSelfUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InnovatorProfile
        fields = ["phone_number", "profile_photo", "biography", "project_description"]
        widgets = {
            "biography": forms.Textarea(attrs={"rows": 3}),
            "project_description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
