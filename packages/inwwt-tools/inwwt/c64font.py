"""C64 Pro Mono glyphs, rasterized to the 8×8 character cell.

Style's C64 Pro Mono (v1.2.1) stores the uppercase/graphics charset at
U+EE00 and the lowercase/uppercase charset at U+EF00, one codepoint per
screen code. Outlines sit on a 256-unit grid inside a 2048-unit em, so
each cell is exactly eight pixels. See LICENSES.md before redistributing
the font file.
"""

from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

FONT_FILENAME = "C64_Pro_Mono-STYLE.ttf"
OFFICIAL_PAGE = "http://style64.org/c64-truetype"
OFFICIAL_ZIP = "https://style64.org/file/C64_TrueType_v1.2.1-STYLE.zip"
ZIP_MEMBER = f"C64_TrueType_v1.2.1-STYLE/fonts/{FONT_FILENAME}"

CELL = 8
UPPER_BASE = 0xEE00
LOWER_BASE = 0xEF00

# Uppercase/graphics screen codes. Confirmed against the font's 8×8 bitmaps.
# Anything else is available as {sc:N} (0–255, 128–255 are reverse video).
PETSCII_NAMES: dict[str, int] = {
    "space": 32,
    "hbar": 64,
    "hline": 64,
    "spade": 65,
    "vbar": 66,
    "vline": 66,
    "heart": 83,
    "club": 88,
    "diamond": 90,
    "circle": 81,
    "disc": 81,
    "ring": 87,
    "shade": 102,
    "checker": 102,
    "lhalf": 97,
    "left": 97,
    "bblock": 98,
    "tline": 99,
    "block": 160,
    "tl": 79,
    "tr": 80,
    "bl": 76,
    "br": 122,
    "pi": 94,
}


def bundled_font_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / FONT_FILENAME


def resolve_font_path() -> Path:
    """Find the font, or download the official Style zip into the user cache.

    The file shipped with this package keeps Style's filename. Downloading
    is the fallback the license points at (link to style64.org) when the
    bundled file is missing.
    """
    override = os.environ.get("INWWT_C64_FONT")
    if override:
        path = Path(override)
        if not path.is_file():
            raise FileNotFoundError(f"INWWT_C64_FONT does not exist: {path}")
        return path
    bundled = bundled_font_path()
    if bundled.is_file():
        return bundled
    cache = Path.home() / ".cache" / "inwwt" / FONT_FILENAME
    if cache.is_file():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(OFFICIAL_ZIP, timeout=60) as response:
            payload = response.read()
    except OSError as exc:
        raise FileNotFoundError(
            f"C64 Pro Mono is not bundled and the download from {OFFICIAL_ZIP} failed. "
            f"Install it from {OFFICIAL_PAGE} and set INWWT_C64_FONT."
        ) from exc
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        cache.write_bytes(archive.read(ZIP_MEMBER))
    return cache


def _raster_glyph(font: TTFont, glyph_set, name: str) -> np.ndarray:
    image = np.zeros((CELL, CELL), dtype=np.uint8)
    for py in range(CELL):
        for px in range(CELL):
            # em square is 2048 units; one C64 pixel is 256 units. Y grows up.
            cx = (px + 0.5) * 256
            cy = (7 - py + 0.5) * 256
            pen = PointInsidePen(glyph_set, (cx, cy))
            glyph_set[name].draw(pen)
            if pen.getResult():
                image[py, px] = 1
    return image


def _raster_charset(font: TTFont, base: int) -> np.ndarray:
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    out = np.zeros((256, CELL, CELL), dtype=np.uint8)
    for code in range(256):
        name = cmap.get(base + code)
        if name is None:
            continue
        out[code] = _raster_glyph(font, glyph_set, name)
    return out


@lru_cache(maxsize=1)
def load_charsets() -> tuple[np.ndarray, np.ndarray]:
    """Return ``(upper, lower)`` arrays of shape (256, 8, 8)."""
    font = TTFont(str(resolve_font_path()))
    try:
        return _raster_charset(font, UPPER_BASE), _raster_charset(font, LOWER_BASE)
    finally:
        font.close()


def glyph(screen_code: int, charset: str = "upper") -> np.ndarray:
    """8×8 bitmap for a screen code. Codes 128–255 are reverse video."""
    upper, lower = load_charsets()
    table = upper if charset == "upper" else lower
    bits = table[screen_code & 0x7F]
    if screen_code & 0x80:
        return 1 - bits
    return bits


def ascii_to_screen(char: str, charset: str = "upper") -> int:
    """Map one printable character to a screen code in the selected charset."""
    if len(char) != 1:
        raise ValueError(f"expected one character, got {char!r}")
    if charset == "upper":
        if "a" <= char <= "z":
            char = char.upper()
        code = ord(char)
        if char == "@":
            return 0
        if "A" <= char <= "Z":
            return code - 64
        if char == "£":
            return 28
        if char == "π":
            return 94
        if 32 <= code <= 63:
            return code
        raise ValueError(f"no uppercase/graphics screen code for {char!r}; use a {{sc:N}} token")
    code = ord(char)
    if "a" <= char <= "z":
        return code - 96
    if "A" <= char <= "Z":
        return code
    if char == "@":
        return 0
    if char == "π":
        return 94
    if 32 <= code <= 63:
        return code
    raise ValueError(f"no lowercase-charset screen code for {char!r}")
