"""Signal handlers for Discord Obfuscate."""

# Standard Library
import logging

# Django
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

# Discord Obfuscate App
from discord_obfuscate.config import default_obfuscation_values, role_color_rule_sync_enabled
from discord_obfuscate.constants import DEFAULT_OBFUSCATE_METHOD
from discord_obfuscate.models import DiscordRoleObfuscation
from discord_obfuscate.tasks import sync_role_color_rules

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Group)
def schedule_role_color_sync(sender, instance: Group, created: bool, **kwargs):
    """Queue role color sync when new groups are created."""
    if not created:
        return

    group_id = instance.pk

    def _after_commit():
        group = Group.objects.filter(pk=group_id).first()
        if not group:
            logger.warning("Group %s no longer exists; skipping obfuscation setup.", group_id)
            return
        defaults = default_obfuscation_values()
        defaults.setdefault("obfuscation_type", DEFAULT_OBFUSCATE_METHOD)
        defaults["opt_out"] = True
        obfuscation, created_cfg = DiscordRoleObfuscation.objects.get_or_create(
            group=group, defaults=defaults
        )
        if created_cfg:
            logger.info("Created obfuscation config for group %s.", group.name)
        else:
            logger.debug("Obfuscation config already exists for group %s.", group.name)

        if role_color_rule_sync_enabled():
            logger.info(
                "Scheduling role color sync after 30s for group %s.", group.name
            )
            sync_role_color_rules.apply_async(countdown=30)

    transaction.on_commit(_after_commit)
