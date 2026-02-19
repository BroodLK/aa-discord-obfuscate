"""Helpers for role color assignment."""

# Standard Library
import colorsys
import random
from typing import Iterable, List, Set


PALETTE_SIZE = 250
PALETTE_SATURATION = 0.65
PALETTE_LIGHTNESS = 0.5


def _int_to_hex(value: int) -> str:
    return f"#{value:06x}"


def _hex_to_int(value: str) -> int | None:
    value = (value or "").strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def build_palette(count: int = PALETTE_SIZE) -> List[int]:
    colors: List[int] = []
    if count <= 0:
        return colors
    for idx in range(count):
        hue = idx / float(count)
        r, g, b = colorsys.hls_to_rgb(hue, PALETTE_LIGHTNESS, PALETTE_SATURATION)
        value = (int(r * 255) << 16) + (int(g * 255) << 8) + int(b * 255)
        colors.append(value)
    return colors


def select_random_color(available: Iterable[int]) -> int | None:
    pool = list(available)
    if not pool:
        return None
    return random.SystemRandom().choice(pool)


def available_colors(
    palette: Iterable[int],
    used_colors: Set[int],
) -> List[int]:
    return [color for color in palette if color not in used_colors]


def to_hex(value: int) -> str:
    return _int_to_hex(value)


def to_int(value: str) -> int | None:
    return _hex_to_int(value)
