"""Shared constants."""

ROLE_NAME_MAX_LEN = 100

DEFAULT_OBFUSCATE_ENABLED = True
DEFAULT_OBFUSCATE_METHOD = "sha256_base32"
DEFAULT_OBFUSCATE_FORMAT = "{hash12}"
DEFAULT_OBFUSCATE_PREFIX = ""
DEFAULT_REQUIRE_EXISTING_ROLE = False
DEFAULT_SYNC_ON_SAVE = True
DEFAULT_PERIODIC_SYNC_ENABLED = False

ALLOWED_DIVIDERS = [
    "┃",
    "┇",
    "┆",
    "︲",
    "｜",
    "︱",
    "➖",
]

OBFUSCATION_METHODS = {
    "sha256_hex": ("SHA256 + hex", "sha256", "hex"),
    "sha256_base32": ("SHA256 + base32", "sha256", "base32"),
    "blake2s_hex": ("BLAKE2s + hex", "blake2s", "hex"),
    "blake2s_base32": ("BLAKE2s + base32", "blake2s", "base32"),
}
