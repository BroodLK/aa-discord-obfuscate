"""App Models."""

# Django
from django.db import models
from django.contrib.auth.models import Group

# Third Party
from solo.models import SingletonModel

# Discord Obfuscate App
from discord_obfuscate.constants import ALLOWED_DIVIDERS, OBFUSCATION_METHODS


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        """Meta definitions"""

        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)


class DiscordRoleObfuscation(models.Model):
    """Configuration for obfuscating Discord roles tied to groups."""

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="discord_obfuscation",
    )
    opt_out = models.BooleanField(
        default=True,
        help_text="When enabled, the original group name is used.",
    )
    obfuscation_type = models.CharField(
        max_length=32,
        choices=[(key, label) for key, (label, _, _) in OBFUSCATION_METHODS.items()],
        default="sha256_base32",
    )
    obfuscation_format = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Format string using {hash8}, {hash12}, {hash16}.",
    )
    divider_characters = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Comma-separated list of divider characters.",
    )
    min_chars_before_divider = models.PositiveIntegerField(
        default=0,
        help_text="Minimum number of characters before a divider is used.",
    )
    custom_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="If set, overrides the obfuscation method.",
    )
    role_color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="Optional role color in hex (#RRGGBB).",
    )
    role_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Cached Discord role ID for rename operations.",
    )
    last_obfuscated_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord role obfuscation"
        verbose_name_plural = "Discord role obfuscations"
        ordering = ["group__name"]

    def __str__(self):
        return f"{self.group.name}"

    def get_dividers(self):
        return [d for d in self.divider_characters.split(",") if d]

    def set_dividers(self, values):
        unique = []
        for divider in values or []:
            if divider in ALLOWED_DIVIDERS and divider not in unique:
                unique.append(divider)
        self.divider_characters = ",".join(unique)


class DiscordObfuscateConfig(SingletonModel):
    """Global settings for Discord Obfuscate."""

    sync_on_save = models.BooleanField(
        default=True,
        help_text="Queue a role rename task when a config is saved in admin.",
    )
    periodic_sync_enabled = models.BooleanField(
        default=False,
        help_text="Enable periodic full sync of roles via Celery beat.",
    )
    periodic_sync_minute = models.CharField(
        max_length=32,
        default="0",
        help_text="Cron minute field for periodic sync.",
    )
    periodic_sync_hour = models.CharField(
        max_length=32,
        default="*/1",
        help_text="Cron hour field for periodic sync.",
    )
    periodic_sync_day_of_week = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_week field for periodic sync.",
    )
    periodic_sync_day_of_month = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_month field for periodic sync.",
    )
    periodic_sync_month_of_year = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron month_of_year field for periodic sync.",
    )
    periodic_sync_timezone = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Timezone for periodic sync (blank uses project timezone).",
    )

    class Meta:
        verbose_name = "Discord Obfuscate config"

    def __str__(self):
        return "Discord Obfuscate config"
