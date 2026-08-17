from django import forms

from accounts.forms import BootstrapFormMixin


class AttendanceFilterForm(BootstrapFormMixin, forms.Form):
    innovator_name = forms.CharField(
        required=False,
        max_length=300,
        label="Innovator name",
        widget=forms.SearchInput(
            attrs={
                "placeholder": "Enter the innovator's first or last name",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_innovator_name(self):
        return " ".join(self.cleaned_data["innovator_name"].split())
