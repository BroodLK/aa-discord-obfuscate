"""Signal handlers for Discord Obfuscate."""

# Django
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

# Discord Obfuscate App
from discord_obfuscate.config import default_obfuscation_values, role_color_rule_sync_enabled
from discord_obfuscate.constants import DEFAULT_OBFUSCATE_METHOD
from discord_obfuscate.models import DiscordRoleObfuscation
from discord_obfuscate.tasks import sync_role_color_rules


@receiver(post_save, sender=Group)
def schedule_role_color_sync(sender, instance: Group, created: bool, **kwargs):
    """Queue role color sync when new groups are created."""
    if not created:
        return
    defaults = default_obfuscation_values()
    defaults.setdefault("obfuscation_type", DEFAULT_OBFUSCATE_METHOD)
    defaults["opt_out"] = True
    DiscordRoleObfuscation.objects.get_or_create(group=instance, defaults=defaults)
    if not role_color_rule_sync_enabled():
        return
    sync_role_color_rules.apply_async(countdown=15)
