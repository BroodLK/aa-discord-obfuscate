"""Runtime config helpers."""

# Django
from django.apps import apps

# Discord Obfuscate App
from discord_obfuscate.app_settings import (
    DISCORD_OBFUSCATE_DEFAULT_METHOD,
    DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED,
    DISCORD_OBFUSCATE_SYNC_ON_SAVE,
)
from discord_obfuscate.constants import ALLOWED_DIVIDERS, OBFUSCATION_METHODS


def _get_config():
    try:
        if not apps.ready:
            return None
        model = apps.get_model("discord_obfuscate", "DiscordObfuscateConfig")
        if model is None:
            return None
        return model.get_solo()
    except Exception:
        return None


def sync_on_save_enabled() -> bool:
    config = _get_config()
    if config:
        return bool(config.sync_on_save)
    return bool(DISCORD_OBFUSCATE_SYNC_ON_SAVE)


def periodic_sync_enabled() -> bool:
    config = _get_config()
    if config:
        return bool(config.periodic_sync_enabled)
    return bool(DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED)


def role_color_rule_sync_enabled() -> bool:
    config = _get_config()
    if config:
        return bool(config.role_color_rule_sync_enabled)
    return False


def random_key_rotation_enabled() -> bool:
    config = _get_config()
    if config:
        return bool(config.random_key_rotation_enabled)
    return False


def default_obfuscation_values() -> dict:
    config = _get_config()
    if config:
        obfuscation_type = config.default_obfuscation_type
        if obfuscation_type not in OBFUSCATION_METHODS:
            obfuscation_type = DISCORD_OBFUSCATE_DEFAULT_METHOD
        dividers = [d for d in config.default_divider_characters.split(",") if d]
        dividers = [d for d in dividers if d in ALLOWED_DIVIDERS]
        return {
            "opt_out": bool(config.default_opt_out),
            "use_random_key": bool(config.default_use_random_key),
            "random_key_rotate_name": bool(config.default_random_key_rotate_name),
            "random_key_rotate_position": bool(
                config.default_random_key_rotate_position
            ),
            "obfuscation_type": obfuscation_type,
            "divider_characters": ",".join(dividers),
            "min_chars_before_divider": int(
                config.default_min_chars_before_divider or 0
            ),
        }

    return {
        "opt_out": False,
        "use_random_key": False,
        "random_key_rotate_name": True,
        "random_key_rotate_position": True,
        "obfuscation_type": DISCORD_OBFUSCATE_DEFAULT_METHOD,
        "divider_characters": "",
        "min_chars_before_divider": 0,
    }
