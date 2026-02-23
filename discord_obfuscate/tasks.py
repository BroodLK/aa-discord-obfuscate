"""App Tasks"""

# Standard Library
import logging
import random
import time
from collections.abc import Mapping
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
    role_ordering_enabled,
    role_order_bot_role_id,
    role_order_mode,
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
    DiscordRoleOrder,
)

logger = logging.getLogger(__name__)

# Create your tasks here


def _role_position(role, default=0):
    if role is None:
        return default
    if isinstance(role, Mapping):
        value = role.get("position", default)
    else:
        value = getattr(role, "position", default)
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _role_sort_key(role):
    position = _role_position(role, default=0)
    role_id = getattr(role, "id", 0) or 0
    try:
        role_id = int(role_id)
    except (TypeError, ValueError):
        role_id = 0
    return (-position, role_id)


def _role_is_everyone(role) -> bool:
    if role is None:
        return False
    if isinstance(role, Mapping):
        return role.get("name") == "@everyone"
    return getattr(role, "name", "") == "@everyone"


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


def _reorder_roles_payload(payload: list[dict]) -> bool:
    if not payload:
        return True
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )
        from allianceauth.services.modules.discord.discord_client.exceptions import (
            DiscordRateLimitExhausted,
        )

        route = f"guilds/{DISCORD_GUILD_ID}/roles"
        _api_request_with_retry(
            default_bot_client,
            DiscordRateLimitExhausted,
            method="patch",
            route=route,
            data=payload,
        )
        default_bot_client._invalidate_guild_roles_cache(DISCORD_GUILD_ID)
        logger.info("Reordered %s roles via manual ordering", len(payload))
        return True
    except Exception:
        logger.exception("Failed to reorder roles via manual ordering")
        return False


def _build_manual_order_payload(
    roleset,
    bot_role_id: int | None,
    mode: str = "desired",
) -> list[dict]:
    roles = list(roleset)
    if not roles:
        return []

    roles_by_id = {role.id: role for role in roles}
    bot_role = roles_by_id.get(bot_role_id) if bot_role_id else None
    if bot_role_id and not bot_role:
        logger.warning("Manual role ordering enabled but bot role id %s not found.", bot_role_id)
        return []

    if bot_role_id is None:
        logger.warning("Manual role ordering enabled but bot role is not configured.")
        return []

    bot_position = _role_position(bot_role, default=None)
    if bot_position is None:
        logger.warning("Bot role position unavailable; skipping manual role ordering.")
        return []

    order_entries = list(DiscordRoleOrder.objects.all().order_by("sort_order", "role_name"))
    if not order_entries:
        logger.info("Manual role ordering enabled but no saved order exists.")
        return []

    system_locked_ids: set[int] = set()
    user_locked_ids: set[int] = {
        entry.role_id for entry in order_entries if entry.locked
    }
    opt_out_ids = _opt_out_role_ids(roleset)
    for role in roles:
        if _role_is_everyone(role):
            system_locked_ids.add(role.id)
            continue
        if _role_position(role) >= bot_position:
            system_locked_ids.add(role.id)
            continue
        if role.id in opt_out_ids:
            system_locked_ids.add(role.id)

    locked_ids = system_locked_ids | user_locked_ids
    movable_roles = [
        role
        for role in roles
        if _role_position(role) > 0 and _role_position(role) < bot_position
    ]
    movable_ids = {role.id for role in movable_roles}

    desired_ids = [
        entry.role_id
        for entry in order_entries
        if entry.role_id in movable_ids
    ]
    desired_set = set(desired_ids)
    remaining_ids = [
        role.id
        for role in sorted(movable_roles, key=_role_sort_key)
        if role.id not in desired_set
    ]
    ordered_ids = desired_ids + remaining_ids

    available_positions = sorted(
        {
            _role_position(role)
            for role in movable_roles
            if role.id not in locked_ids
        },
        reverse=True,
    )

    unlocked_ids = [role_id for role_id in ordered_ids if role_id not in locked_ids]
    if mode == "shuffle":
        shuffled = list(unlocked_ids)
        random.SystemRandom().shuffle(shuffled)
        unlocked_ids = shuffled

    payload = []
    for index, role_id in enumerate(unlocked_ids):
        if index >= len(available_positions):
            break
        payload.append({"id": role_id, "position": available_positions[index]})

    for role in movable_roles:
        if role.id in locked_ids:
            payload.append({"id": role.id, "position": _role_position(role)})

    return payload


def _opt_out_role_ids(roleset) -> set[int]:
    configs = list(
        DiscordRoleObfuscation.objects.select_related("group").filter(opt_out=True)
    )
    if not configs:
        return set()
    roles_by_id = {role.id: role for role in roleset}
    roles_by_name = {role.name: role for role in roleset}
    role_ids: set[int] = set()

    for config in configs:
        role_id = None
        if config.role_id and config.role_id in roles_by_id:
            role_id = config.role_id
        else:
            desired = role_name_for_group(config.group, config)
            for name in (desired, config.last_obfuscated_name, config.group.name):
                if name and name in roles_by_name:
                    role_id = roles_by_name[name].id
                    break
        if role_id:
            role_ids.add(role_id)

    return role_ids


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

    configs_with_roles = list(
        DiscordRoleObfuscation.objects.exclude(role_id=None).only("id", "role_id", "role_color")
    )
    pinned_role_ids = {
        cfg.role_id for cfg in configs_with_roles if cfg.role_color
    }
    obfuscation_by_role_id = {
        cfg.role_id: cfg for cfg in configs_with_roles if cfg.role_id
    }

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
                    obfuscation=obfuscation_by_role_id.get(role.id),
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
    """Rotate random keys, sync role names, and reorder roles via role ordering config."""
    configs = list(
        DiscordRoleObfuscation.objects.select_related("group").filter(
            use_random_key=True
        )
    )
    if not configs and not role_ordering_enabled():
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

    if role_ordering_enabled():
        bot_role_id = role_order_bot_role_id()
        payload = _build_manual_order_payload(roleset, bot_role_id, role_order_mode())
        if payload:
            _reorder_roles_payload(payload)
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
