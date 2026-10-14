"""Documented 16-color VIC-II palettes.

The VIC-II never emitted RGB. Every "C64 palette" is a measurement or a
model of that video signal. This module ships two published ones:

* **Pepto** — Philip "Pepto" Timmermann's 2001 PAL calculation, the set
  emulators shipped for years. Hex values below match the table in
  "All you ever wanted to know about the colors of the Commodore 64"
  (https://www.pepto.de/projects/colorvic/2001/) and VICE's
  ``pepto-pal.vpl``.
* **Colodore** — Timmermann's later remeasurement, published at
  https://www.colodore.com/. The site's sliders move the result, so the
  fixed sRGB triples here are the ones VICE records as "Colodore (PAL)"
  in ``data/C64/colodore.vpl``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

Color = tuple[int, int, int]

# Index order is the VIC-II color register order, 0 through 15.
NAMES: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "cyan",
    "purple",
    "green",
    "blue",
    "yellow",
    "orange",
    "brown",
    "light red",
    "dark grey",
    "grey",
    "light green",
    "light blue",
    "light grey",
)

# Pepto 2001 / VICE pepto-pal. The 2001 article prints these as
# 00 00 00, FF FF FF, 68 37 2B, 70 A4 B2, 6F 3D 86, 58 8D 43,
# 35 28 79, B8 C7 6F, 6F 4F 25, 43 39 00, 9A 67 59, 44 44 44,
# 6C 6C 6C, 9A D2 84, 6C 5E B5, 95 95 95.
PEPTO: tuple[Color, ...] = (
    (0x00, 0x00, 0x00),
    (0xFF, 0xFF, 0xFF),
    (0x68, 0x37, 0x2B),
    (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86),
    (0x58, 0x8D, 0x43),
    (0x35, 0x28, 0x79),
    (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25),
    (0x43, 0x39, 0x00),
    (0x9A, 0x67, 0x59),
    (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C),
    (0x9A, 0xD2, 0x84),
    (0x6C, 0x5E, 0xB5),
    (0x95, 0x95, 0x95),
)

# VICE Colodore (PAL), from data/C64/colodore.vpl, based on colodore.com.
COLODORE: tuple[Color, ...] = (
    (0x00, 0x00, 0x00),
    (0xFF, 0xFF, 0xFF),
    (0x96, 0x28, 0x2E),
    (0x5B, 0xD6, 0xCE),
    (0x9F, 0x2D, 0xAD),
    (0x41, 0xB9, 0x36),
    (0x27, 0x24, 0xC4),
    (0xEF, 0xF3, 0x47),
    (0x9F, 0x48, 0x15),
    (0x5E, 0x35, 0x00),
    (0xDA, 0x5F, 0x66),
    (0x47, 0x47, 0x47),
    (0x78, 0x78, 0x78),
    (0x91, 0xFF, 0x84),
    (0x68, 0x64, 0xFF),
    (0xAE, 0xAE, 0xAE),
)

PALETTES: dict[str, tuple[Color, ...]] = {
    "pepto": PEPTO,
    "colodore": COLODORE,
}

# Power-on colors from the KERNAL screen init: border $0E, background $06,
# text color $0E (light blue on blue, light-blue border).
BORDER_INDEX = 14
BACKGROUND_INDEX = 6
TEXT_INDEX = 14


def get_palette(name: str) -> np.ndarray:
    key = name.strip().lower()
    if key not in PALETTES:
        known = ", ".join(sorted(PALETTES))
        raise ValueError(f"unknown palette {name!r}; choose from {known}")
    return np.array(PALETTES[key], dtype=np.uint8)


def hex_colors(name: str) -> list[str]:
    return [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in PALETTES[name.strip().lower()]]


def write_ffmpeg_palette(path: str | Path, name: str) -> Path:
    """Write a 16×16 palettized PNG that ffmpeg's paletteuse filter accepts.

    Slots 0–15 are the VIC-II colors. The remaining slots repeat those
    colors so every palette entry is a real C64 color.
    """
    colors = PALETTES[name.strip().lower()]
    img = Image.new("P", (16, 16))
    flat: list[int] = []
    for i in range(256):
        r, g, b = colors[i % 16]
        flat.extend((r, g, b))
    img.putpalette(flat)
    img.putdata([i % 16 for i in range(256)])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path
