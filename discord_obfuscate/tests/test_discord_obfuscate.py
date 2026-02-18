"""
Discord Obfuscate test
"""

# Django
from django.test import TestCase

# Discord Obfuscate App
from discord_obfuscate.obfuscation import obfuscate_name

class TestDiscordObfuscate(TestCase):
    """
    TestDiscordObfuscate
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Test setup
        :return:
        :rtype:
        """

        super().setUpClass()

    def test_discord_obfuscate(self):
        """
        Dummy test function
        :return:
        :rtype:
        """

        result = obfuscate_name(
            "Test Group",
            "sha256_hex",
            "secret",
            prefix="grp",
            format_str="{prefix}{hash8}",
        )
        self.assertTrue(result.startswith("grp"))
        self.assertEqual(len(result), len("grp") + 8)
