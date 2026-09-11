from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin

from .models import HubBooking


class HubBookingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = HubBooking
        fields = ["visit_date", "arrival_time", "purpose"]
        labels = {
            "visit_date": "Date you want to visit",
            "arrival_time": "Time you expect to arrive",
            "purpose": "What do you intend to do in the hub?",
        }
        widgets = {
            "visit_date": forms.DateInput(attrs={"type": "date"}),
            "arrival_time": forms.TimeInput(attrs={"type": "time", "step": "60"}),
            "purpose": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Describe the work, meeting, equipment, or support you plan to use.",
                }
            ),
        }

    def __init__(self, *args, innovator=None, **kwargs):
        self.innovator = innovator
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.instance.pk:
            self.fields["visit_date"].initial = today
        self.fields["visit_date"].widget.attrs["min"] = today.isoformat()
        self.apply_bootstrap()

    def clean_visit_date(self):
        visit_date = self.cleaned_data["visit_date"]
        if visit_date < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date.")
        return visit_date

    def clean_purpose(self):
        purpose = self.cleaned_data["purpose"].strip()
        if len(purpose) < 10:
            raise forms.ValidationError("Give a useful description of what you intend to do.")
        return purpose

    def clean(self):
        cleaned = super().clean()
        visit_date = cleaned.get("visit_date")
        if self.innovator and visit_date:
            duplicate = HubBooking.objects.filter(
                innovator=self.innovator,
                visit_date=visit_date,
            ).exclude(status=HubBooking.Status.CANCELLED)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("visit_date", "You already have a hub booking for this date.")
        return cleaned


class BookingCancellationForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        min_length=10,
        max_length=1000,
        label="Reason for cancellation",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Explain clearly why this hub visit is being cancelled.",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_reason(self):
        return " ".join(self.cleaned_data["reason"].split())
