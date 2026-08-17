from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User
from attendance.models import AttendanceSession


class AttendanceFilterForm(BootstrapFormMixin, forms.Form):
    PERIOD_CHOICES = [
        ("today", "Today"),
        ("week", "This week"),
        ("month", "This month"),
        ("custom", "Custom date range"),
        ("all", "All dates"),
    ]
    period = forms.ChoiceField(choices=PERIOD_CHOICES, required=False, initial="today")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    innovator = forms.ModelChoiceField(
        queryset=User.objects.none(), required=False, empty_label="All innovators"
    )
    registration_number = forms.CharField(required=False, max_length=50)
    project = forms.CharField(required=False, max_length=200)
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses"), *AttendanceSession.Status.choices]
    )
    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.SearchInput(attrs={"placeholder": "Name, email, number or project"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["innovator"].queryset = User.objects.filter(
            role=User.Role.INNOVATOR
        ).order_by("last_name", "first_name")
        self.apply_bootstrap()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("period") == "custom":
            if not cleaned.get("start_date") or not cleaned.get("end_date"):
                raise forms.ValidationError("Choose both dates for a custom date range.")
            if cleaned["end_date"] < cleaned["start_date"]:
                self.add_error("end_date", "End date cannot be before start date.")
        return cleaned
