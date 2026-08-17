from django import forms

from accounts.forms import BootstrapFormMixin

from .models import AttendanceSession


class CheckInForm(BootstrapFormMixin, forms.Form):
    project_name = forms.CharField(max_length=200, label="Project")
    planned_activity = forms.CharField(
        label="Planned activity",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Describe the specific work you plan to complete during this visit.",
            }
        ),
    )

    def __init__(self, *args, project_name="", **kwargs):
        super().__init__(*args, **kwargs)
        if project_name:
            self.fields["project_name"].initial = project_name
        self.apply_bootstrap()

    def clean_planned_activity(self):
        value = self.cleaned_data["planned_activity"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Please give a useful description of the planned activity.")
        return value


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
    next_step = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_work_completed(self):
        value = self.cleaned_data["work_completed"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Please give a useful description of the work completed.")
        return value


class AttendanceCorrectionForm(BootstrapFormMixin, forms.ModelForm):
    correction_reason = forms.CharField(
        label="Correction reason",
        min_length=5,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required for the permanent correction history.",
    )

    class Meta:
        model = AttendanceSession
        fields = ["check_in_at", "check_out_at", "status", "work_completed"]
        widgets = {
            "check_in_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "check_out_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "work_completed": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["check_in_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["check_out_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.apply_bootstrap()

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get("check_in_at")
        check_out = cleaned.get("check_out_at")
        status = cleaned.get("status")
        if check_in and check_out and check_out < check_in:
            self.add_error("check_out_at", "Check-out time cannot be earlier than check-in time.")
        if status == AttendanceSession.Status.COMPLETED and not check_out:
            self.add_error("check_out_at", "A completed session requires a check-out time.")
        if status == AttendanceSession.Status.ACTIVE and check_out:
            self.add_error("status", "An active session cannot have a check-out time.")
        return cleaned
