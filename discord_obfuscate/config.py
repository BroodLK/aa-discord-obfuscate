"""Runtime config helpers."""

# Django
from django.apps import apps
from django.conf import settings

# Discord Obfuscate App
from discord_obfuscate.app_settings import (
    DISCORD_OBFUSCATE_PERIODIC_SYNC_CRONTAB,
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


def periodic_sync_settings() -> tuple[bool, dict]:
    config = _get_config()
    if config:
        schedule = {
            "minute": config.periodic_sync_minute,
            "hour": config.periodic_sync_hour,
            "day_of_week": config.periodic_sync_day_of_week,
            "day_of_month": config.periodic_sync_day_of_month,
            "month_of_year": config.periodic_sync_month_of_year,
            "timezone": config.periodic_sync_timezone or settings.TIME_ZONE,
        }
        return bool(config.periodic_sync_enabled), schedule

    schedule = DISCORD_OBFUSCATE_PERIODIC_SYNC_CRONTAB or {}
    schedule = {
        "minute": schedule.get("minute", "0"),
        "hour": schedule.get("hour", "*/1"),
        "day_of_week": schedule.get("day_of_week", "*"),
        "day_of_month": schedule.get("day_of_month", "*"),
        "month_of_year": schedule.get("month_of_year", "*"),
        "timezone": schedule.get("timezone", settings.TIME_ZONE),
    }
    return bool(DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED), schedule

