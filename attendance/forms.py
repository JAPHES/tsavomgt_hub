from datetime import datetime

from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin

class CheckInForm(BootstrapFormMixin, forms.Form):
    project_name = forms.CharField(max_length=200, label="Project")

    def __init__(self, *args, project_name="", **kwargs):
        super().__init__(*args, **kwargs)
        if project_name:
            self.fields["project_name"].initial = project_name
        self.apply_bootstrap()

class CheckOutForm(BootstrapFormMixin, forms.Form):
    work_completed = forms.CharField(
        label="Work completed",
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "Describe the work completed and the result."}
        ),
    )
    challenges_encountered = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_work_completed(self):
        value = self.cleaned_data["work_completed"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Please give a useful description of the work completed.")
        return value


class DailyAttendanceForm(BootstrapFormMixin, forms.Form):
    arrival_time = forms.TimeField(
        label="Time you came in",
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
        help_text="Select your actual arrival time today.",
    )
    departure_time = forms.TimeField(
        label="Time you went out",
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
        help_text="Select your actual departure time today.",
    )
    work_completed = forms.CharField(
        label="Work done during this period",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Describe the work you completed and the result you achieved.",
            }
        ),
    )
    challenges_encountered = forms.CharField(
        label="Challenge faced today (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Describe any challenge you faced, if applicable."}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_work_completed(self):
        value = self.cleaned_data["work_completed"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Give a useful description of the work completed.")
        return value

    def clean(self):
        cleaned = super().clean()
        arrival = cleaned.get("arrival_time")
        departure = cleaned.get("departure_time")
        if not arrival or not departure:
            return cleaned

        local_now = timezone.localtime()
        local_date = local_now.date()
        current_timezone = timezone.get_current_timezone()
        check_in_at = timezone.make_aware(datetime.combine(local_date, arrival), current_timezone)
        check_out_at = timezone.make_aware(
            datetime.combine(local_date, departure), current_timezone
        )
        if check_out_at <= check_in_at:
            self.add_error("departure_time", "Departure time must be later than arrival time.")
        elif check_out_at > local_now:
            self.add_error("departure_time", "Departure time cannot be in the future.")
        if check_in_at > local_now:
            self.add_error("arrival_time", "Arrival time cannot be in the future.")
        cleaned["check_in_at"] = check_in_at
        cleaned["check_out_at"] = check_out_at
        return cleaned
