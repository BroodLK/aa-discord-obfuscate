"""App Settings."""

# Django
from django.conf import settings

DISCORD_OBFUSCATE_SECRET = getattr(
    settings,
    "DISCORD_OBFUSCATE_SECRET",
    getattr(settings, "SECRET_KEY", ""),
)
