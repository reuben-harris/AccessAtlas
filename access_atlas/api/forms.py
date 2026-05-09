from django import forms
from django.utils import timezone

from access_atlas.core.widgets import DateTimePicker


class ApiTokenCreateForm(forms.Form):
    name = forms.CharField(max_length=120)
    can_write = forms.BooleanField(
        label="Allow writes",
        required=False,
        help_text=(
            "Read-only tokens can list and view API objects but cannot change them."
        ),
    )
    expires_at = forms.DateTimeField(
        label="Expires at",
        required=False,
        input_formats=["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=DateTimePicker(),
        help_text="Leave blank for a token that does not expire automatically.",
    )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a token name.")
        return name

    def clean_expires_at(self):
        expires_at = self.cleaned_data["expires_at"]
        if expires_at is not None and expires_at <= timezone.now():
            raise forms.ValidationError("Expiry must be in the future.")
        return expires_at
