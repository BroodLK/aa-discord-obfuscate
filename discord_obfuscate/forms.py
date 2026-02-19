"""Forms for Discord role obfuscation."""

# Standard Library
import re

# Django
from django import forms

# Discord Obfuscate App
from discord_obfuscate.constants import ALLOWED_DIVIDERS, OBFUSCATION_METHODS
from discord_obfuscate.models import DiscordObfuscateConfig, DiscordRoleObfuscation
from discord_obfuscate.obfuscation import (
    generate_random_key,
    role_name_for_group,
    role_name_for_name,
)

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
    random_key = forms.CharField(
        required=False,
        label="Random key",
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
        help_text="Generated automatically when random key mode is enabled.",
    )
    role_color = forms.CharField(
        required=False,
        label="Role color",
        widget=forms.TextInput(attrs={"type": "color"}),
    )

    class Meta:
        model = DiscordRoleObfuscation
        fields = [
            "group",
            "state_name",
            "opt_out",
            "obfuscation_type",
            "obfuscation_format",
            "divider_characters",
            "min_chars_before_divider",
            "custom_name",
            "use_random_key",
            "random_key",
            "random_key_rotate_name",
            "random_key_rotate_position",
            "role_color",
            "preview",
        ]
        widgets = {
            "custom_name": forms.TextInput(attrs={"class": "form-control"}),
            "obfuscation_format": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "group" in self.fields:
            self.fields["group"].required = False
        if self.instance and self.instance.pk:
            self.fields["divider_characters"].initial = self.instance.get_dividers()
            subject_name = self.instance.subject_name
            if subject_name:
                self.fields["preview"].initial = role_name_for_group(
                    self.instance.group, self.instance
                ) if self.instance.group else role_name_for_name(
                    subject_name, self.instance
                )
        if "random_key" in self.fields:
            self.fields["random_key"].widget.attrs["readonly"] = "readonly"

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

    def clean_role_color(self):
        value = (self.cleaned_data.get("role_color") or "").strip()
        if not value:
            return ""
        if not value.startswith("#"):
            raise forms.ValidationError("Color must start with #.")
        if len(value) != 7:
            raise forms.ValidationError("Color must be in #RRGGBB format.")
        for char in value[1:]:
            if char.lower() not in "0123456789abcdef":
                raise forms.ValidationError("Color must be valid hex.")
        return value.lower()

    def clean_random_key(self):
        value = (self.cleaned_data.get("random_key") or "").strip()
        if not value:
            return ""
        if len(value) != 16:
            raise forms.ValidationError("Random key must be 16 characters.")
        if not value.isalnum():
            raise forms.ValidationError("Random key must be alphanumeric.")
        return value

    def clean(self):
        cleaned = super().clean()
        group = cleaned.get("group")
        state_name = (cleaned.get("state_name") or "").strip()
        cleaned["state_name"] = state_name
        if group and state_name:
            self.add_error("state_name", "Choose either a group or a state, not both.")
            self.add_error("group", "Choose either a group or a state, not both.")
        if not group and not state_name:
            self.add_error("state_name", "A state or a group is required.")
        opt_out = cleaned.get("opt_out")
        if opt_out:
            cleaned["custom_name"] = ""
        use_random_key = cleaned.get("use_random_key")
        if use_random_key:
            cleaned["random_key"] = cleaned.get("random_key") or generate_random_key(16)
        else:
            cleaned["random_key"] = ""
            cleaned["random_key_rotate_name"] = False
            cleaned["random_key_rotate_position"] = False
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


class DiscordObfuscateConfigForm(forms.ModelForm):
    """Form for global Discord obfuscation settings."""

    class Meta:
        model = DiscordObfuscateConfig
        fields = "__all__"
