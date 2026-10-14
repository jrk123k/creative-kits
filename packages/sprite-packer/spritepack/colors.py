"""Background colors. ``#rgb``, ``#rrggbb``, or ``r,g,b``."""

from __future__ import annotations

from spritepack.errors import SpritePackError


def parse_color(text: str) -> tuple[int, int, int]:
    raw = text.strip()
    if raw.startswith("#"):
        hexes = raw[1:]
        if len(hexes) == 3:
            hexes = "".join(ch * 2 for ch in hexes)
        if len(hexes) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in hexes):
            raise SpritePackError(f"color {text!r} is not #rgb or #rrggbb")
        return tuple(int(hexes[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 3:
        raise SpritePackError(f"color must be #rrggbb or r,g,b, got {text!r}")
    try:
        rgb = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise SpritePackError(f"color must be #rrggbb or r,g,b, got {text!r}") from exc
    if any(channel < 0 or channel > 255 for channel in rgb):
        raise SpritePackError(f"color channels must be 0..255, got {text!r}")
    return rgb  # type: ignore[return-value]


def is_color(text: str) -> bool:
    raw = text.strip()
    if raw.startswith("#"):
        return True
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 3:
        return False
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return False
    return all(0 <= value <= 255 for value in values)


def color_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)
