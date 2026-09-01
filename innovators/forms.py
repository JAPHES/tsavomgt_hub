from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import InnovatorProfile, InnovatorProject, validate_kenyan_phone


class InnovatorCreateForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    registration_number = forms.CharField(max_length=50, label="Registration number")
    phone_number = forms.CharField(max_length=20)

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
            raise forms.ValidationError("This registration number is already in use.")
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
            "profile_photo",
        ]

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
            raise forms.ValidationError("This registration number is already in use.")
        return number


class InnovatorSelfUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InnovatorProfile
        fields = ["phone_number", "profile_photo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class InnovatorProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InnovatorProject
        fields = ["name", "details", "area_of_focus"]
        labels = {
            "name": "Project name",
            "details": "Project details",
            "area_of_focus": "Area of focus",
        }
        help_texts = {
            "area_of_focus": (
                "For example: Climate technology, agriculture, health, education, or fintech."
            ),
        }
        widgets = {
            "details": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Describe the problem, your solution, and the progress made so far.",
                }
            ),
            "area_of_focus": forms.TextInput(
                attrs={"placeholder": "e.g. Climate technology"}
            ),
        }

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter a meaningful project name.")
        if (
            self.profile
            and InnovatorProject.objects.filter(profile=self.profile, name__iexact=name).exists()
        ):
            raise forms.ValidationError("You already have a project with this name.")
        return name

    def clean_details(self):
        details = self.cleaned_data["details"].strip()
        if len(details) < 20:
            raise forms.ValidationError(
                "Describe the project in at least 20 characters."
            )
        return details

    def clean_area_of_focus(self):
        area = " ".join(self.cleaned_data["area_of_focus"].split())
        if len(area) < 3:
            raise forms.ValidationError("Enter a meaningful area of focus.")
        return area
