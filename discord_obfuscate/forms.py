"""Forms for Discord role obfuscation."""

# Standard Library
import re

# Django
from django import forms

# Discord Obfuscate App
from discord_obfuscate.constants import ALLOWED_DIVIDERS, OBFUSCATION_METHODS
from discord_obfuscate.models import DiscordRoleObfuscation
from discord_obfuscate.obfuscation import role_name_for_group

DIVIDER_CHOICES = [(char, char) for char in ALLOWED_DIVIDERS]
PLACEHOLDER_PATTERN = re.compile(r"\{hash8\}|\{hash12\}|\{hash16\}|\{prefix\}")


class DiscordRoleObfuscationForm(forms.ModelForm):
    """Form for editing obfuscation settings."""

    divider_characters = forms.MultipleChoiceField(
        required=False,
        choices=DIVIDER_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Dividers",
    )
    preview = forms.CharField(
        required=False,
        disabled=True,
        label="Preview",
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )

    class Meta:
        model = DiscordRoleObfuscation
        fields = [
            "group",
            "opt_out",
            "obfuscation_type",
            "obfuscation_format",
            "divider_characters",
            "min_chars_before_divider",
            "custom_name",
            "preview",
        ]
        widgets = {
            "custom_name": forms.TextInput(attrs={"class": "form-control"}),
            "obfuscation_format": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["divider_characters"].initial = self.instance.get_dividers()
            self.fields["preview"].initial = role_name_for_group(
                self.instance.group, self.instance
            )

    def clean_divider_characters(self):
        values = self.cleaned_data.get("divider_characters") or []
        return [val for val in values if val in ALLOWED_DIVIDERS]

    def clean_obfuscation_type(self):
        obfuscation_type = self.cleaned_data.get("obfuscation_type")
        if obfuscation_type not in OBFUSCATION_METHODS:
            return "sha256_base32"
        return obfuscation_type

    def clean_custom_name(self):
        custom_name = (self.cleaned_data.get("custom_name") or "").strip()
        dividers = set(self.cleaned_data.get("divider_characters") or [])
        if custom_name:
            for char in custom_name:
                if not (char.isalnum() or char in dividers):
                    raise forms.ValidationError(
                        "Custom name can only contain letters, numbers, and selected dividers."
                    )
        return custom_name

    def clean_obfuscation_format(self):
        value = (self.cleaned_data.get("obfuscation_format") or "").strip()
        dividers = set(self.cleaned_data.get("divider_characters") or [])
        stripped = PLACEHOLDER_PATTERN.sub("", value)
        for char in stripped:
            if not (char.isalnum() or char in dividers):
                raise forms.ValidationError(
                    "Format can only contain letters, numbers, placeholders, and selected dividers."
                )
        if value and not PLACEHOLDER_PATTERN.search(value):
            raise forms.ValidationError(
                "Format must include at least one of {hash8}, {hash12}, or {hash16}."
            )
        return value

    def clean(self):
        cleaned = super().clean()
        opt_out = cleaned.get("opt_out")
        if opt_out:
            cleaned["custom_name"] = ""
        dividers = cleaned.get("divider_characters") or []
        min_chars = cleaned.get("min_chars_before_divider") or 0
        if dividers and min_chars < 1:
            self.add_error(
                "min_chars_before_divider",
                "Minimum characters must be at least 1 when dividers are selected.",
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.set_dividers(self.cleaned_data.get("divider_characters") or [])
        if commit:
            instance.save()
        return instance
