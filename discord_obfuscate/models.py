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
    use_random_key = models.BooleanField(
        default=False,
        help_text=(
            "If enabled, obfuscation uses a random key instead of the group name. "
            "Rotation tasks only apply to entries with this enabled."
        ),
    )
    random_key = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Random 16-character key used for obfuscation when enabled.",
    )
    random_key_rotate_name = models.BooleanField(
        default=True,
        help_text=(
            "Allow the rotation task to rename this role. "
            "Only applies when random key mode is enabled."
        ),
    )
    random_key_rotate_position = models.BooleanField(
        default=True,
        help_text=(
            "Allow the rotation task to reposition this role. "
            "Only applies when random key mode is enabled."
        ),
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
        verbose_name="Obfuscated Name",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord Role Obfuscation"
        verbose_name_plural = "Discord Role Obfuscations"
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
    random_key_rotation_enabled = models.BooleanField(
        default=False,
        help_text="Enable periodic rotation of random obfuscation keys.",
    )
    random_key_rotation_minute = models.CharField(
        max_length=32,
        default="0",
        help_text="Cron minute field for random key rotation.",
    )
    random_key_rotation_hour = models.CharField(
        max_length=32,
        default="0",
        help_text="Cron hour field for random key rotation.",
    )
    random_key_rotation_day_of_week = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_week field for random key rotation.",
    )
    random_key_rotation_day_of_month = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_month field for random key rotation.",
    )
    random_key_rotation_month_of_year = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron month_of_year field for random key rotation.",
    )
    random_key_rotation_timezone = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Timezone for random key rotation (blank uses project timezone).",
    )
    role_color_rule_sync_enabled = models.BooleanField(
        default=False,
        help_text="Enable periodic sync for role color rules.",
    )
    role_color_rule_sync_minute = models.CharField(
        max_length=32,
        default="0",
        help_text="Cron minute field for role color sync.",
    )
    role_color_rule_sync_hour = models.CharField(
        max_length=32,
        default="*/1",
        help_text="Cron hour field for role color sync.",
    )
    role_color_rule_sync_day_of_week = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_week field for role color sync.",
    )
    role_color_rule_sync_day_of_month = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron day_of_month field for role color sync.",
    )
    role_color_rule_sync_month_of_year = models.CharField(
        max_length=32,
        default="*",
        help_text="Cron month_of_year field for role color sync.",
    )
    role_color_rule_sync_timezone = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Timezone for role color sync (blank uses project timezone).",
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
        verbose_name = "Discord Obfuscate Config"

    def __str__(self):
        return "Discord Obfuscate config"


class DiscordRoleColorRule(models.Model):
    """Rule for assigning random colors to matching roles."""

    name = models.CharField(
        max_length=100,
        help_text="Rule name shown in admin.",
    )
    pattern = models.CharField(
        max_length=150,
        help_text="Role name pattern. Use * as a wildcard.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic color assignment for this rule.",
    )
    case_sensitive = models.BooleanField(
        default=False,
        help_text="Match role names with case sensitivity.",
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower numbers run first when multiple rules match.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Discord Role Color Rule"
        verbose_name_plural = "Discord Role Color Rules"

    def __str__(self):
        return f"{self.name}"


class DiscordRoleColorAssignment(models.Model):
    """Assigned color for a Discord role."""

    rule = models.ForeignKey(
        DiscordRoleColorRule,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    role_id = models.BigIntegerField()
    role_name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rule", "role_name"]
        verbose_name = "Discord Role Color Assignment"
        verbose_name_plural = "Discord Role Color Assignments"
        constraints = [
            models.UniqueConstraint(fields=["role_id"], name="unique_role_color_role"),
            models.UniqueConstraint(fields=["color"], name="unique_role_color_value"),
        ]

    def __str__(self):
        return f"{self.role_name} ({self.color})"
