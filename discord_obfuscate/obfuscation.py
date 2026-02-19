"""Obfuscation helpers."""

# Standard Library
import base64
import hashlib
import hmac
import itertools
import logging
import secrets
import string
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# Django
from django.contrib.auth.models import Group, User

# Alliance Auth
from allianceauth.services.modules.discord.discord_client.helpers import RolesSet

# Discord Obfuscate App
from discord_obfuscate.app_settings import (
    DISCORD_OBFUSCATE_DEFAULT_METHOD,
    DISCORD_OBFUSCATE_ENABLED,
    DISCORD_OBFUSCATE_INCLUDE_STATES,
    DISCORD_OBFUSCATE_FORMAT,
    DISCORD_OBFUSCATE_PREFIX,
    DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE,
    DISCORD_OBFUSCATE_SECRET,
)
from discord_obfuscate.constants import (
    ALLOWED_DIVIDERS,
    OBFUSCATION_METHODS,
    ROLE_NAME_MAX_LEN,
)
from discord_obfuscate.models import DiscordRoleObfuscation

logger = logging.getLogger(__name__)

RANDOM_KEY_CHARS = string.ascii_letters + string.digits


def generate_random_key(length: int = 16) -> str:
    return "".join(secrets.choice(RANDOM_KEY_CHARS) for _ in range(length))



@dataclass(frozen=True)
class RoleNameResolution:
    """Resolved role name for a group."""

    group: Optional[Group]
    desired_name: str
    used_name: Optional[str]
    matched_role_id: Optional[int]
    used_original: bool


def _method_info(method: str) -> tuple:
    method = method or DISCORD_OBFUSCATE_DEFAULT_METHOD
    if method not in OBFUSCATION_METHODS:
        method = DISCORD_OBFUSCATE_DEFAULT_METHOD
    _, algo, encoding = OBFUSCATION_METHODS[method]
    return algo, encoding


def _hash_bytes(name: str, secret: str, algo: str) -> bytes:
    secret_bytes = str(secret or "").encode("utf-8")
    name_bytes = str(name).encode("utf-8")
    digestmod = hashlib.sha256
    if algo == "blake2s":
        digestmod = hashlib.blake2s
    return hmac.new(secret_bytes, name_bytes, digestmod).digest()


def _encode_hash(hash_bytes: bytes, encoding: str) -> str:
    if encoding == "base32":
        return base64.b32encode(hash_bytes).decode("ascii").rstrip("=")
    return hash_bytes.hex()


def _apply_format(format_str: str, tokens: dict) -> str:
    result = format_str or DISCORD_OBFUSCATE_FORMAT
    for key, value in tokens.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def _sanitize_output(value: str, allowed_dividers: list) -> str:
    cleaned = []
    divider_set = set(allowed_dividers or [])
    for char in value:
        if char.isalnum() or char in divider_set:
            cleaned.append(char)
    return "".join(cleaned)


def _insert_dividers(value: str, dividers: list, min_chars: int) -> str:
    if not dividers or min_chars <= 0:
        return value
    chunks = [value[i : i + min_chars] for i in range(0, len(value), min_chars)]
    if len(chunks) <= 1:
        return value
    out = chunks[0]
    for divider, chunk in zip(itertools.cycle(dividers), chunks[1:]):
        out += divider + chunk
    return out


def obfuscate_name(
    name: str,
    method: str,
    secret: str,
    prefix: str = "",
    format_str: str = "",
    dividers: Optional[list] = None,
    min_chars_before_divider: int = 0,
) -> str:
    """Create a deterministic obfuscated name."""
    algo, encoding = _method_info(method)
    hash_str = _encode_hash(_hash_bytes(name, secret, algo), encoding)

    format_str = format_str or DISCORD_OBFUSCATE_FORMAT
    prefix = prefix or ""
    if prefix and "{prefix}" not in format_str:
        format_str = "{prefix}" + format_str

    tokens = {
        "prefix": _sanitize_output(prefix, ALLOWED_DIVIDERS),
        "hash8": hash_str[:8],
        "hash12": hash_str[:12],
        "hash16": hash_str[:16],
    }
    value = _apply_format(format_str, tokens)
    value = _sanitize_output(value, dividers or [])
    value = _insert_dividers(value, dividers or [], min_chars_before_divider)
    value = _sanitize_output(value, dividers or [])
    return value[:ROLE_NAME_MAX_LEN]


def role_name_for_name(
    name: str,
    config: Optional[DiscordRoleObfuscation],
) -> str:
    """Determine the desired role name for a subject name based on config."""
    if config and config.opt_out:
        return name
    if config and config.custom_name:
        dividers = config.get_dividers()
        return _sanitize_output(str(config.custom_name), dividers)[:ROLE_NAME_MAX_LEN]
    method = config.obfuscation_type if config else DISCORD_OBFUSCATE_DEFAULT_METHOD
    format_str = config.obfuscation_format if config else DISCORD_OBFUSCATE_FORMAT
    dividers = config.get_dividers() if config else []
    min_chars = config.min_chars_before_divider if config else 0
    input_name = name
    if config and config.use_random_key and config.random_key:
        input_name = config.random_key
    return obfuscate_name(
        input_name,
        method,
        DISCORD_OBFUSCATE_SECRET,
        DISCORD_OBFUSCATE_PREFIX,
        format_str,
        dividers,
        min_chars,
    )


def role_name_for_group(
    group: Group,
    config: Optional[DiscordRoleObfuscation],
) -> str:
    """Determine the desired role name for a group based on config."""
    return role_name_for_name(group.name, config)


def fetch_roleset(use_cache: bool = True) -> RolesSet:
    """Fetch roles for the configured guild as RolesSet."""
    try:
        from allianceauth.services.modules.discord.core import (
            default_bot_client,
            DISCORD_GUILD_ID,
        )

        roles = default_bot_client.guild_roles(
            guild_id=DISCORD_GUILD_ID, use_cache=use_cache
        )
    except Exception:
        logger.exception("Failed to fetch roles from Discord")
        return RolesSet([])
    return RolesSet(roles)


def resolve_group_role_name(
    group: Group,
    roleset: RolesSet,
    config: Optional[DiscordRoleObfuscation] = None,
) -> RoleNameResolution:
    """Resolve role name to be used for a group."""
    desired = role_name_for_group(group, config)
    desired_role = roleset.role_by_name(desired)
    if desired_role:
        if desired != group.name:
            logger.debug("Resolved group %s to existing obfuscated role %s", group.name, desired)
        return RoleNameResolution(
            group=group,
            desired_name=desired,
            used_name=desired,
            matched_role_id=desired_role.id,
            used_original=(desired == group.name),
        )

    original_role = roleset.role_by_name(group.name)
    if original_role and DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE:
        if desired != group.name:
            logger.debug(
                "Desired role %s missing; using original for group %s",
                desired,
                group.name,
            )
        return RoleNameResolution(
            group=group,
            desired_name=desired,
            used_name=group.name,
            matched_role_id=original_role.id,
            used_original=True,
        )

    if not DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE:
        return RoleNameResolution(
            group=group,
            desired_name=desired,
            used_name=desired,
            matched_role_id=None,
            used_original=(desired == group.name),
        )

    return RoleNameResolution(
        group=group,
        desired_name=desired,
        used_name=None,
        matched_role_id=None,
        used_original=False,
    )


def obfuscated_user_group_names(
    user: User,
    state_name: Optional[str] = None,
) -> List[str]:
    """Return obfuscated role names for a user's groups."""
    if not DISCORD_OBFUSCATE_ENABLED:
        names = [group.name for group in user.groups.all()]
        if state_name:
            names.append(state_name)
        return names

    roleset = fetch_roleset(use_cache=True)
    role_names: List[str] = []

    for group in user.groups.all():
        config = DiscordRoleObfuscation.objects.filter(group=group).first()
        resolution = resolve_group_role_name(group, roleset, config=config)
        if resolution.used_name:
            if resolution.used_name != group.name:
                logger.debug(
                    "Obfuscate group %s -> %s",
                    group.name,
                    resolution.used_name,
                )
            else:
                logger.debug("Using original name for group %s", group.name)
            role_names.append(resolution.used_name)
        else:
            logger.debug(
                "Skipping group %s because no matching role exists in Discord",
                group.name,
            )

    if state_name and DISCORD_OBFUSCATE_INCLUDE_STATES:
        state_config = (
            DiscordRoleObfuscation.objects.filter(state_name=state_name).first()
        )
        desired_state_name = role_name_for_name(state_name, state_config)
        if not DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE:
            logger.debug("Including state %s without role check", state_name)
            role_names.append(desired_state_name)
        else:
            if roleset.role_by_name(desired_state_name):
                logger.debug("Including state %s", state_name)
                role_names.append(desired_state_name)
            else:
                logger.debug(
                    "Skipping state %s because no matching role exists in Discord",
                    state_name,
                )

    return role_names


def get_group_configs(groups: Iterable[Group]) -> Dict[int, DiscordRoleObfuscation]:
    """Fetch configs keyed by group id."""
    configs = DiscordRoleObfuscation.objects.filter(group__in=groups)
    return {cfg.group_id: cfg for cfg in configs}
