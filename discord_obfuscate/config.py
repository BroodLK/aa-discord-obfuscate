"""Runtime config helpers."""

# Django
from django.apps import apps

# Discord Obfuscate App
from discord_obfuscate.app_settings import (
    DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED,
    DISCORD_OBFUSCATE_SYNC_ON_SAVE,
)


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
