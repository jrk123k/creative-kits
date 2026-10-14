"""Frame anchors. Origin is the top-left of the source frame, y grows down.

A preset can sit on the far edge. ``bottom-center`` of a 14×12 frame is
``(7, 12)``: ``x = width // 2``, ``y = height``. That point is the bottom
boundary, one past the last pixel row, which is where the feet meet the ground.
"""

from __future__ import annotations

from spritepack.errors import SpritePackError

PRESETS: dict[str, str] = {
    "top-left": "top-left",
    "top-center": "top-center",
    "top-right": "top-right",
    "center-left": "center-left",
    "center": "center",
    "center-right": "center-right",
    "bottom-left": "bottom-left",
    "bottom-center": "bottom-center",
    "bottom-right": "bottom-right",
}

DEFAULT_ANCHOR = "bottom-center"


def resolve_anchor(spec, width: int, height: int) -> tuple[int, int]:
    """Turn a preset or an explicit point into pixel coordinates."""
    if spec is None:
        spec = DEFAULT_ANCHOR
    if isinstance(spec, str):
        name = spec.strip().lower()
        if name not in PRESETS:
            raise SpritePackError(
                f"unknown anchor {spec!r}. Use bottom-center, top-left, center, "
                "or an x,y pair."
            )
        return _preset(name, width, height)
    if isinstance(spec, dict):
        if "x" not in spec or "y" not in spec:
            raise SpritePackError(f"anchor {spec!r} needs x and y")
        return _pair(spec["x"], spec["y"])
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        return _pair(spec[0], spec[1])
    raise SpritePackError(f"anchor must be a preset or x,y, got {spec!r}")


def parse_anchor_token(text: str):
    """CLI token: a preset name or ``x,y``."""
    raw = text.strip()
    if "," not in raw:
        name = raw.lower()
        if name not in PRESETS:
            raise SpritePackError(
                f"unknown anchor {text!r}. Use bottom-center or x,y."
            )
        return name
    x_text, y_text = raw.split(",", 1)
    return _pair(x_text, y_text)


def _preset(name: str, width: int, height: int) -> tuple[int, int]:
    x_mid = width // 2
    y_mid = height // 2
    table = {
        "top-left": (0, 0),
        "top-center": (x_mid, 0),
        "top-right": (width, 0),
        "center-left": (0, y_mid),
        "center": (x_mid, y_mid),
        "center-right": (width, y_mid),
        "bottom-left": (0, height),
        "bottom-center": (x_mid, height),
        "bottom-right": (width, height),
    }
    return table[name]


def _pair(x, y) -> tuple[int, int]:
    try:
        xi, yi = int(x), int(y)
    except (TypeError, ValueError) as exc:
        raise SpritePackError(f"anchor x,y must be integers, got {x!r}, {y!r}") from exc
    return xi, yi
