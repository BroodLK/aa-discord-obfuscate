"""App Tasks"""

# Standard Library
import logging

# Third Party
from celery import shared_task

from django.contrib.auth.models import Group

# Alliance Auth
# Discord Obfuscate App
from discord_obfuscate.app_settings import DISCORD_OBFUSCATE_DEFAULT_METHOD
from discord_obfuscate.obfuscation import (
    fetch_roleset,
    role_name_for_group,
)
from discord_obfuscate.models import DiscordRoleObfuscation

logger = logging.getLogger(__name__)

# Create your tasks here


def _find_role_by_id(roleset, role_id):
    for role in roleset:
        if role.id == role_id:
            return role
    return None


def _rename_role(role_id: int, new_name: str) -> bool:
    """Rename a Discord role via bot client."""
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )

        route = f"guilds/{DISCORD_GUILD_ID}/roles/{role_id}"
        default_bot_client._api_request(method="patch", route=route, data={"name": new_name})
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Renamed Discord role %s to %s", role_id, new_name)
        return True
    except Exception:
        logger.exception("Failed to rename role %s to %s", role_id, new_name)
        return False


@shared_task
def sync_group_role(group_id: int) -> bool:
    """Sync role name for a single group."""
    try:
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        logger.warning("Group with id %s no longer exists", group_id)
        return False

    config, _ = DiscordRoleObfuscation.objects.get_or_create(
        group=group, defaults={"obfuscation_type": DISCORD_OBFUSCATE_DEFAULT_METHOD}
    )
    roleset = fetch_roleset(use_cache=False)
    desired_name = role_name_for_group(group, config)
    logger.debug("Sync role for group %s -> %s", group.name, desired_name)

    desired_role = roleset.role_by_name(desired_name)
    if desired_role:
        config.role_id = desired_role.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        logger.info("Role already matches desired name for group %s", group.name)
        return True

    role_to_rename = None
    if config.role_id:
        role_to_rename = _find_role_by_id(roleset, config.role_id)

    if not role_to_rename and config.last_obfuscated_name:
        role_to_rename = roleset.role_by_name(config.last_obfuscated_name)

    if not role_to_rename:
        role_to_rename = roleset.role_by_name(group.name)

    if not role_to_rename:
        logger.info("No matching role found for group %s", group.name)
        return False

    if role_to_rename.name == desired_name:
        config.role_id = role_to_rename.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        logger.info("Role name already set for group %s", group.name)
        return True

    if _rename_role(role_to_rename.id, desired_name):
        config.role_id = role_to_rename.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        return True

    return False


@shared_task
def sync_all_roles() -> int:
    """Sync role names for all groups with configs."""
    group_ids = list(
        DiscordRoleObfuscation.objects.values_list("group_id", flat=True)
    )
    if not group_ids:
        group_ids = list(Group.objects.values_list("id", flat=True))

    count = 0
    for group_id in group_ids:
        if sync_group_role(group_id):
            count += 1
    return count
