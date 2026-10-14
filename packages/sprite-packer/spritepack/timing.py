"""Per-frame duration, and the hold the 16-bit intro kit can actually store.

The kit's ``cycle.hold`` is one integer for the whole animation. A frame that
needs to stay up longer is written into the ``frames:`` list more than once.
``kit_cycle`` picks the greatest common divisor so the list stays short.
"""

from __future__ import annotations

import math

from spritepack.errors import SpritePackError


def duration_from_hold(hold: int, fps: int) -> float:
    if hold < 1:
        raise SpritePackError("hold must be >= 1")
    if fps < 1:
        raise SpritePackError("fps must be >= 1")
    return round(hold * 1000.0 / fps, 3)


def hold_from_duration(duration_ms: float, fps: int) -> int:
    """Film frames at ``fps``. Python ``round`` (half to even) is the rule."""
    if duration_ms <= 0:
        raise SpritePackError("duration_ms must be > 0")
    if fps < 1:
        raise SpritePackError("fps must be >= 1")
    return max(1, int(round(float(duration_ms) * fps / 1000.0)))


def kit_cycle(holds: list[int]) -> tuple[int, list[int]]:
    """Return ``(cycle.hold, repeats)``.

    Listing frame ``i`` ``repeats[i]`` times, each shown for ``cycle.hold``
    film frames, lasts as long as ``holds[i]`` film frames.
    """
    if not holds:
        raise SpritePackError("an animation needs at least one frame")
    if any(h < 1 for h in holds):
        raise SpritePackError("hold_frames must be >= 1")
    g = holds[0]
    for hold in holds[1:]:
        g = math.gcd(g, hold)
    g = max(1, g)
    return g, [hold // g for hold in holds]
