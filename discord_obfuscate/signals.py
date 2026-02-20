"""Signal handlers for Discord Obfuscate."""

# Django
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import Group

# Discord Obfuscate App
from discord_obfuscate.models import (
    DiscordRoleColorAssignment,
    DiscordRoleObfuscation,
)
from discord_obfuscate.obfuscation import role_name_for_group


@receiver(pre_delete, sender=DiscordRoleObfuscation)
def cleanup_role_color_assignments(sender, instance: DiscordRoleObfuscation, **kwargs):
    """Remove role color assignments when a group obfuscation is deleted."""
    if instance.role_id:
        DiscordRoleColorAssignment.objects.filter(role_id=instance.role_id).delete()

    names = set()
    if instance.last_obfuscated_name:
        names.add(instance.last_obfuscated_name)
    try:
        if instance.group_id and instance.group:
            names.add(instance.group.name)
            names.add(role_name_for_group(instance.group, instance))
    except Exception:
        # Best-effort cleanup; ignore missing relations during delete cascades.
        pass

    if names:
        DiscordRoleColorAssignment.objects.filter(role_name__in=names).delete()


@receiver(pre_delete, sender=Group)
def cleanup_group_obfuscations(sender, instance: Group, **kwargs):
    """Ensure obfuscation configs are removed when a group is deleted."""
    DiscordRoleObfuscation.objects.filter(group=instance).delete()
