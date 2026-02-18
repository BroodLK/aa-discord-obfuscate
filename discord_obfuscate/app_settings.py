"""App Settings."""

# Django
from django.conf import settings

# Discord Obfuscate App
from discord_obfuscate.constants import OBFUSCATION_METHODS

# Defaults
DISCORD_OBFUSCATE_ENABLED = getattr(
    settings,
    "DISCORD_OBFUSCATE_ENABLED",
    True,
)
DISCORD_OBFUSCATE_DEFAULT_METHOD = getattr(
    settings,
    "DISCORD_OBFUSCATE_DEFAULT_METHOD",
    "sha256_base32",
)
if DISCORD_OBFUSCATE_DEFAULT_METHOD not in OBFUSCATION_METHODS:
    DISCORD_OBFUSCATE_DEFAULT_METHOD = "sha256_base32"
DISCORD_OBFUSCATE_SECRET = getattr(
    settings,
    "DISCORD_OBFUSCATE_SECRET",
    getattr(settings, "SECRET_KEY", ""),
)
DISCORD_OBFUSCATE_PREFIX = getattr(
    settings,
    "DISCORD_OBFUSCATE_PREFIX",
    "",
)
DISCORD_OBFUSCATE_FORMAT = getattr(
    settings,
    "DISCORD_OBFUSCATE_FORMAT",
    "{hash12}",
)
DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE = getattr(
    settings,
    "DISCORD_OBFUSCATE_REQUIRE_EXISTING_ROLE",
    True,
)
DISCORD_OBFUSCATE_INCLUDE_STATES = getattr(
    settings,
    "DISCORD_OBFUSCATE_INCLUDE_STATES",
    True,
)
DISCORD_OBFUSCATE_SYNC_ON_SAVE = getattr(
    settings,
    "DISCORD_OBFUSCATE_SYNC_ON_SAVE",
    True,
)
DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED = getattr(
    settings,
    "DISCORD_OBFUSCATE_PERIODIC_SYNC_ENABLED",
    False,
)
DISCORD_OBFUSCATE_PERIODIC_SYNC_CRONTAB = getattr(
    settings,
    "DISCORD_OBFUSCATE_PERIODIC_SYNC_CRONTAB",
    {
        "minute": "0",
        "hour": "*/1",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
    },
)
