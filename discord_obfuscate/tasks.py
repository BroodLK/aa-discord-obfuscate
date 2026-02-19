"""App Tasks"""

# Standard Library
import logging
import random
from fnmatch import fnmatchcase

# Third Party
from celery import shared_task

from django.contrib.auth.models import Group

# Alliance Auth
# Discord Obfuscate App
from discord_obfuscate.app_settings import DISCORD_OBFUSCATE_DEFAULT_METHOD
from discord_obfuscate.config import (
    periodic_sync_enabled,
    random_key_rotation_enabled,
    role_color_rule_sync_enabled,
)
from discord_obfuscate.obfuscation import (
    fetch_roleset,
    generate_random_key,
    role_name_for_group,
)
from discord_obfuscate.role_colors import (
    available_colors,
    build_palette,
    select_random_color,
    to_hex,
    to_int,
)
from discord_obfuscate.models import (
    DiscordRoleColorAssignment,
    DiscordRoleColorRule,
    DiscordRoleObfuscation,
)

logger = logging.getLogger(__name__)

# Create your tasks here


def _find_role_by_id(roleset, role_id):
    for role in roleset:
        if role.id == role_id:
            return role
    return None


def _update_role(role_id: int, name: str | None = None, color: int | None = None) -> bool:
    """Update a Discord role via bot client."""
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )

        route = f"guilds/{DISCORD_GUILD_ID}/roles/{role_id}"
        data = {}
        if name is not None:
            data["name"] = name
        if color is not None:
            data["color"] = color
        if not data:
            return True
        default_bot_client._api_request(method="patch", route=route, data=data)
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Updated Discord role %s", role_id)
        return True
    except Exception:
        logger.exception("Failed to update role %s", role_id)
        return False


def _rename_role(role_id: int, new_name: str, color: int | None = None) -> bool:
    """Rename a Discord role via bot client."""
    return _update_role(role_id, name=new_name, color=color)


def _reorder_roles_bottom(role_ids: list[int]) -> bool:
    if not role_ids:
        return True
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )

        shuffled = list(role_ids)
        random.SystemRandom().shuffle(shuffled)
        payload = [
            {"id": role_id, "position": index + 1}
            for index, role_id in enumerate(shuffled)
        ]
        route = f"guilds/{DISCORD_GUILD_ID}/roles"
        default_bot_client._api_request(method="patch", route=route, data=payload)
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Reordered %s roles to the bottom", len(shuffled))
        return True
    except Exception:
        logger.exception("Failed to reorder roles")
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
    if config.use_random_key and not config.random_key:
        config.random_key = generate_random_key(16)
        config.save(update_fields=["random_key", "updated_at"])
    roleset = fetch_roleset(use_cache=False)
    desired_name = role_name_for_group(group, config)
    logger.debug("Sync role for group %s -> %s", group.name, desired_name)
    color_value = None
    if config and config.role_color:
        value = config.role_color.strip()
        if value.startswith("#"):
            value = value[1:]
        if len(value) == 6:
            try:
                color_value = int(value, 16)
            except ValueError:
                color_value = None

    desired_role = roleset.role_by_name(desired_name)
    if desired_role:
        config.role_id = desired_role.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        logger.info("Role already matches desired name for group %s", group.name)
        if color_value is None:
            return True
        return _rename_role(desired_role.id, desired_name, color=color_value)

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
        if color_value is None:
            return True
        return _rename_role(role_to_rename.id, desired_name, color=color_value)

    if _rename_role(role_to_rename.id, desired_name, color=color_value):
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


def _role_name_matches(rule: DiscordRoleColorRule, role_name: str) -> bool:
    pattern = rule.pattern or ""
    if not pattern:
        return False
    if rule.case_sensitive:
        return fnmatchcase(role_name, pattern)
    return fnmatchcase(role_name.lower(), pattern.lower())


@shared_task
def sync_role_color_rules() -> int:
    """Assign colors to roles based on matching rules."""
    rules = list(
        DiscordRoleColorRule.objects.filter(enabled=True).order_by("priority", "id")
    )
    if not rules:
        return 0

    pinned_role_ids = set(
        DiscordRoleObfuscation.objects.exclude(role_color="")
        .exclude(role_id=None)
        .values_list("role_id", flat=True)
    )

    roleset = fetch_roleset(use_cache=False)
    roles_by_id = {role.id: role for role in roleset}

    existing_assignments = list(DiscordRoleColorAssignment.objects.all())
    stale_assignments = [
        assignment
        for assignment in existing_assignments
        if assignment.role_id not in roles_by_id
    ]
    if stale_assignments:
        DiscordRoleColorAssignment.objects.filter(
            id__in=[assignment.id for assignment in stale_assignments]
        ).delete()
        existing_assignments = [
            assignment
            for assignment in existing_assignments
            if assignment.role_id in roles_by_id
        ]

    assigned_role_ids = {assignment.role_id for assignment in existing_assignments}

    used_colors = set()
    for assignment in existing_assignments:
        value = to_int(assignment.color)
        if value is not None:
            used_colors.add(value)

    for role in roleset:
        color_value = getattr(role, "color", 0) or 0
        if color_value:
            used_colors.add(int(color_value))

    palette = build_palette()
    available = available_colors(palette, used_colors)
    created = 0

    for rule in rules:
        for role in roleset:
            if role.id in assigned_role_ids:
                continue
            if role.id in pinned_role_ids:
                continue
            if not _role_name_matches(rule, role.name):
                continue
            existing_color = getattr(role, "color", 0) or 0
            if existing_color:
                continue
            color_value = select_random_color(available)
            if color_value is None:
                logger.warning("No available colors left for rule %s", rule.name)
                return created
            if _update_role(role.id, color=color_value):
                DiscordRoleColorAssignment.objects.create(
                    rule=rule,
                    role_id=role.id,
                    role_name=role.name,
                    color=to_hex(color_value),
                )
                assigned_role_ids.add(role.id)
                used_colors.add(color_value)
                available.remove(color_value)
                created += 1

    for assignment in existing_assignments:
        role = roles_by_id.get(assignment.role_id)
        if role and assignment.role_name != role.name:
            DiscordRoleColorAssignment.objects.filter(id=assignment.id).update(
                role_name=role.name
            )

    return created


@shared_task
def rotate_random_keys_and_reorder_roles() -> int:
    """Rotate random keys, sync role names, and reorder roles at the bottom."""
    configs = list(
        DiscordRoleObfuscation.objects.select_related("group").filter(
            use_random_key=True
        )
    )
    if not configs:
        return 0

    rename_targets = [config for config in configs if config.random_key_rotate_name]
    for config in rename_targets:
        config.random_key = generate_random_key(16)
        config.save(update_fields=["random_key", "updated_at"])

    updated = 0
    for config in rename_targets:
        if sync_group_role(config.group_id):
            updated += 1

    roleset = fetch_roleset(use_cache=False)
    role_ids = []
    for config in configs:
        if not config.random_key_rotate_position:
            continue
        desired_name = role_name_for_group(config.group, config)
        role = roleset.role_by_name(desired_name)
        if not role and config.role_id:
            role = _find_role_by_id(roleset, config.role_id)
        if role:
            role_ids.append(role.id)

    unique_role_ids = list(dict.fromkeys(role_ids))
    _reorder_roles_bottom(unique_role_ids)
    return updated


@shared_task
def periodic_sync_all_roles() -> int:
    if not periodic_sync_enabled():
        return 0
    return sync_all_roles()


@shared_task
def periodic_sync_role_colors() -> int:
    if not role_color_rule_sync_enabled():
        return 0
    return sync_role_color_rules()


@shared_task
def periodic_rotate_random_keys() -> int:
    if not random_key_rotation_enabled():
        return 0
    return rotate_random_keys_and_reorder_roles()
