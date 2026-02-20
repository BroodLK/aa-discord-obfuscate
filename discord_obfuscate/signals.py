"""Signal handlers for Discord Obfuscate."""

# Django
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

# Discord Obfuscate App
from discord_obfuscate.config import role_color_rule_sync_enabled
from discord_obfuscate.tasks import sync_role_color_rules


@receiver(post_save, sender=Group)
def schedule_role_color_sync(sender, instance: Group, created: bool, **kwargs):
    """Queue role color sync when new groups are created."""
    if not created:
        return
    if not role_color_rule_sync_enabled():
        return
    sync_role_color_rules.apply_async(countdown=30)
