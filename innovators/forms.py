from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import (
    InnovatorProfile,
    InnovatorProject,
    ProjectFocusArea,
    validate_kenyan_phone,
)


MAX_PROJECT_PROPOSAL_SIZE = 10 * 1024 * 1024


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


class InnovatorProfileCompletionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InnovatorProfile
        fields = ["gender", "school", "department", "county"]
        labels = {
            "county": "County of origin",
        }
        help_texts = {
            "school": "Enter the full name of your school.",
            "department": "Enter the department where you study or work.",
            "county": "Select the Kenyan county you come from.",
        }
        widgets = {
            "school": forms.TextInput(
                attrs={"placeholder": "e.g. School of Science and Informatics"}
            ),
            "department": forms.TextInput(
                attrs={"placeholder": "e.g. Informatics and Computing"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("gender", "school", "department", "county"):
            self.fields[field_name].required = True
        self.fields["gender"].choices = [
            ("", "Select gender"),
            *InnovatorProfile.Gender.choices,
        ]
        self.fields["county"].choices = [
            ("", "Select county"),
            *(
                (value, label)
                for value, label in self.fields["county"].choices
                if value
            ),
        ]
        self.fields["gender"].widget.attrs["autofocus"] = True
        self.apply_bootstrap()


class InnovatorSelfUpdateForm(InnovatorProfileCompletionForm):
    class Meta(InnovatorProfileCompletionForm.Meta):
        fields = [
            "phone_number",
            "gender",
            "school",
            "department",
            "county",
            "profile_photo",
        ]


class ProjectDirectoryFilterForm(BootstrapFormMixin, forms.Form):
    RESULT_VIEW_CHOICES = (
        ("projects", "Projects"),
        ("innovators", "Unique innovators"),
    )
    SORT_CHOICES = (
        ("newest", "Newest projects"),
        ("project", "Project name"),
        ("technology", "Technology focus"),
        ("innovator", "Innovator name"),
        ("county", "County"),
        ("school", "School"),
        ("department", "Department"),
    )

    query = forms.CharField(
        required=False,
        max_length=300,
        label="Search projects or innovators",
        widget=forms.SearchInput(
            attrs={"placeholder": "Project name, focus area, innovator, email or registration"}
        ),
    )
    technology_focus = forms.ChoiceField(
        required=False,
        choices=(),
        label="Technology / project focus",
    )
    county = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All counties"),
            *InnovatorProfile._meta.get_field("county").choices,
        ],
        label="Geographical area",
    )
    area_of_study = forms.CharField(
        required=False,
        max_length=200,
        label="Area of study",
        help_text="Searches across both school and department.",
        widget=forms.SearchInput(attrs={"placeholder": "e.g. computing, engineering"}),
    )
    school = forms.CharField(
        required=False,
        max_length=200,
        label="School of study",
        widget=forms.SearchInput(attrs={"placeholder": "e.g. Science and Informatics"}),
    )
    department = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.SearchInput(attrs={"placeholder": "e.g. Informatics and Computing"}),
    )
    result_view = forms.ChoiceField(
        required=False,
        choices=RESULT_VIEW_CHOICES,
        initial="projects",
        label="Show results as",
    )
    sort_by = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        initial="newest",
        label="Sort results by",
    )

    def __init__(self, *args, technology_focuses=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["technology_focus"].choices = [
            ("", "All technology areas"),
            *((focus, focus) for focus in technology_focuses),
        ]
        self.apply_bootstrap()

    def clean(self):
        cleaned = super().clean()
        for field_name in ("query", "area_of_study", "school", "department"):
            cleaned[field_name] = " ".join(cleaned.get(field_name, "").split())
        return cleaned


class InnovatorProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InnovatorProject
        fields = ["name", "focus_areas", "proposal"]
        labels = {
            "name": "Project name",
            "focus_areas": "Areas of focus",
            "proposal": "Upload project proposal",
        }
        help_texts = {
            "focus_areas": "Select every area that applies. You may choose more than two.",
            "proposal": "Upload one PDF document, up to 10 MB.",
        }
        widgets = {
            "focus_areas": forms.CheckboxSelectMultiple(),
            "proposal": forms.FileInput(
                attrs={"accept": "application/pdf,.pdf"}
            ),
        }

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields["focus_areas"].queryset = ProjectFocusArea.objects.exclude(
            name__iexact="Not specified"
        ).order_by("name")
        has_existing_proposal = bool(self.instance.pk and self.instance.proposal)
        self.fields["proposal"].required = not has_existing_proposal
        if has_existing_proposal:
            self.fields["proposal"].help_text = (
                "Upload a new PDF only if you want to replace the current proposal. "
                "Maximum size: 10 MB."
            )
        self.apply_bootstrap()
        self.fields["focus_areas"].widget.attrs["class"] = "project-focus-options"

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter a meaningful project name.")
        if (
            self.profile
            and InnovatorProject.objects.filter(profile=self.profile, name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("You already have a project with this name.")
        return name

    def clean_proposal(self):
        proposal = self.cleaned_data.get("proposal")
        uploaded_proposal = self.files.get(self.add_prefix("proposal"))
        if uploaded_proposal is None:
            if proposal:
                return proposal
            raise forms.ValidationError("Upload the project proposal as a PDF document.")
        if uploaded_proposal.size > MAX_PROJECT_PROPOSAL_SIZE:
            raise forms.ValidationError("The project proposal must not exceed 10 MB.")
        if uploaded_proposal.content_type not in {
            "application/pdf",
            "application/octet-stream",
        }:
            raise forms.ValidationError("Upload a valid PDF project proposal.")
        position = uploaded_proposal.tell()
        signature = uploaded_proposal.read(5)
        uploaded_proposal.seek(position)
        if signature != b"%PDF-":
            raise forms.ValidationError("Upload a valid PDF project proposal.")
        return uploaded_proposal
