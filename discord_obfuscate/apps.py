"""App Configuration"""

# Django
from django.apps import AppConfig

# AA Discord Obfuscate App
from discord_obfuscate import __version__


class DiscordObfuscateConfig(AppConfig):
    """App Config"""

    name = "discord_obfuscate"
    label = "discord_obfuscate"
    verbose_name = f"Discord Obfuscate v{__version__}"

    def ready(self):
        from discord_obfuscate.patches import patch_discord_user_group_names

        patch_discord_user_group_names()
