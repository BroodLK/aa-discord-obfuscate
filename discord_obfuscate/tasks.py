"""App Tasks"""

# Standard Library
import logging
import random
import time
from fnmatch import fnmatchcase

# Third Party
from celery import shared_task

from django.contrib.auth.models import Group

# Alliance Auth
# Discord Obfuscate App
from discord_obfuscate.constants import DEFAULT_OBFUSCATE_METHOD
from discord_obfuscate.config import (
    default_obfuscation_values,
    periodic_sync_enabled,
    random_key_rotation_enabled,
    random_key_reposition_enabled,
    random_key_reposition_min_position,
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
        from allianceauth.services.modules.discord.discord_client.exceptions import (
            DiscordRateLimitExhausted,
        )

        route = f"guilds/{DISCORD_GUILD_ID}/roles/{role_id}"
        data = {}
        if name is not None:
            data["name"] = name
        if color is not None:
            data["color"] = color
        if not data:
            return True
        _api_request_with_retry(
            default_bot_client,
            DiscordRateLimitExhausted,
            method="patch",
            route=route,
            data=data,
        )
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Updated Discord role %s", role_id)
        return True
    except Exception:
        logger.exception("Failed to update role %s", role_id)
        return False


def _rename_role(role_id: int, new_name: str, color: int | None = None) -> bool:
    """Rename a Discord role via bot client."""
    return _update_role(role_id, name=new_name, color=color)


def _reorder_roles_bottom(role_ids: list[int], start_position: int = 1) -> bool:
    if not role_ids:
        return True
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )
        from allianceauth.services.modules.discord.discord_client.exceptions import (
            DiscordRateLimitExhausted,
        )

        start = max(1, int(start_position or 1))
        shuffled = list(role_ids)
        random.SystemRandom().shuffle(shuffled)
        payload = [
            {"id": role_id, "position": start + index}
            for index, role_id in enumerate(shuffled)
        ]
        route = f"guilds/{DISCORD_GUILD_ID}/roles"
        _api_request_with_retry(
            default_bot_client,
            DiscordRateLimitExhausted,
            method="patch",
            route=route,
            data=payload,
        )
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Reordered %s roles to the bottom", len(shuffled))
        return True
    except Exception:
        logger.exception("Failed to reorder roles")
        return False


def _api_request_with_retry(
    client,
    rate_limit_exc,
    method: str,
    route: str,
    data: dict | list,
    max_attempts: int = 3,
) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            client._api_request(method=method, route=route, data=data)
            return
        except rate_limit_exc as exc:
            if attempt >= max_attempts:
                raise
            delay = _rate_limit_delay(exc)
            logger.warning(
                "Rate limit hit; retrying in %.2fs (attempt %s/%s)",
                delay,
                attempt,
                max_attempts,
            )
            time.sleep(delay)


def _rate_limit_delay(exc) -> float:
    resets_in = getattr(exc, "resets_in", None)
    if resets_in is None and exc.args:
        try:
            resets_in = float(exc.args[0])
        except (TypeError, ValueError):
            resets_in = None
    if resets_in is None:
        return 5.0
    try:
        delay = float(resets_in)
    except (TypeError, ValueError):
        return 5.0
    if delay > 60:
        delay = delay / 1000.0
    return max(delay + 0.25, 0.5)


@shared_task
def sync_group_role(group_id: int) -> bool:
    """Sync role name for a single group."""
    try:
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        logger.warning("Group with id %s no longer exists", group_id)
        return False

    defaults = default_obfuscation_values()
    defaults.setdefault("obfuscation_type", DEFAULT_OBFUSCATE_METHOD)
    config, _ = DiscordRoleObfuscation.objects.get_or_create(group=group, defaults=defaults)
    return _sync_config(config)


def _sync_config(config: DiscordRoleObfuscation, roleset=None) -> bool:
    if config.use_random_key and not config.random_key:
        config.random_key = generate_random_key(16)
        config.save(update_fields=["random_key", "updated_at"])
    desired_name = role_name_for_group(config.group, config)
    logger.debug("Sync role for group %s -> %s", config.group.name, desired_name)
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

    if roleset is None:
        roleset = fetch_roleset(use_cache=True)

    if not roleset or not len(roleset):
        if config.role_id and _rename_role(config.role_id, desired_name, color=color_value):
            config.last_obfuscated_name = desired_name
            config.save(update_fields=["last_obfuscated_name", "updated_at"])
            return True
        logger.info(
            "Skipping sync for group %s because roles could not be loaded",
            config.group.name,
        )
        return False

    desired_role = roleset.role_by_name(desired_name)
    if desired_role:
        config.role_id = desired_role.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        logger.info("Role already matches desired name for group %s", config.group.name)
        if color_value is None:
            return True
        return _rename_role(desired_role.id, desired_name, color=color_value)

    role_to_rename = None
    if config.role_id:
        role_to_rename = _find_role_by_id(roleset, config.role_id)

    if not role_to_rename and config.last_obfuscated_name:
        role_to_rename = roleset.role_by_name(config.last_obfuscated_name)

    if not role_to_rename:
        role_to_rename = roleset.role_by_name(config.group.name)

    if not role_to_rename:
        logger.info("No matching role found for group %s", config.group.name)
        return False

    if role_to_rename.name == desired_name:
        config.role_id = role_to_rename.id
        config.last_obfuscated_name = desired_name
        config.save(update_fields=["role_id", "last_obfuscated_name", "updated_at"])
        logger.info("Role name already set for group %s", config.group.name)
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
    count = 0
    configs = list(DiscordRoleObfuscation.objects.select_related("group"))
    if configs:
        roleset = fetch_roleset(use_cache=False)
        for config in configs:
            if _sync_config(config, roleset=roleset):
                count += 1
        return count

    group_ids = list(Group.objects.values_list("id", flat=True))
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
    roleset = fetch_roleset(use_cache=False)
    for config in rename_targets:
        if _sync_config(config, roleset=roleset):
            updated += 1

    if random_key_reposition_enabled():
        role_ids = []
        for config in configs:
            if not config.random_key_rotate_position:
                continue
            if config.role_id:
                role_ids.append(config.role_id)

        unique_role_ids = list(dict.fromkeys(role_ids))
        if unique_role_ids:
            start_position = random_key_reposition_min_position()
            max_position = 249
            reserve_slots = 1  # Reserve one slot so obfuscated roles + bot role fit below max.
            required = len(unique_role_ids) + reserve_slots
            if start_position + required - 1 > max_position:
                adjusted = max_position - required + 1
                if adjusted < 1:
                    logger.warning(
                        "Not enough room to reposition %s roles below position 250; "
                        "skipping reordering.",
                        len(unique_role_ids),
                    )
                else:
                    logger.warning(
                        "Adjusted random key reposition start from %s to %s to fit %s roles.",
                        start_position,
                        adjusted,
                        len(unique_role_ids),
                    )
                    start_position = adjusted
            if start_position >= 1:
                _reorder_roles_bottom(unique_role_ids, start_position)
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
