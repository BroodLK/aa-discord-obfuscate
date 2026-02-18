"""Monkey patches for Alliance Auth Discord service."""

# Standard Library
import logging

# Discord Obfuscate App
from discord_obfuscate.obfuscation import obfuscated_user_group_names

logger = logging.getLogger(__name__)

_PATCHED = False


def patch_discord_user_group_names() -> None:
    """Patch Discord service to use obfuscated group names."""
    global _PATCHED
    if _PATCHED:
        return

    try:
        from allianceauth.services.modules.discord import core as discord_core
    except Exception:
        logger.info("Discord service not available; skipping patch")
        return

    original = discord_core._user_group_names
    logger.info("Patching Alliance Auth Discord _user_group_names")

    def _patched_user_group_names(user, state_name=None):
        try:
            return obfuscated_user_group_names(user=user, state_name=state_name)
        except Exception:
            logger.exception("Failed to obfuscate group names, falling back")
            return original(user, state_name=state_name)

    discord_core._user_group_names = _patched_user_group_names
    logger.info("Patched Alliance Auth Discord _user_group_names")
    _PATCHED = True
