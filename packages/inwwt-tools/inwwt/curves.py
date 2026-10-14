"""Easing curves for the era transition.

The curve is applied to normalized time before the stage splits, so every
ramp (CRT in, pixelate, dither, and the reverse) eases together.
"""

from __future__ import annotations

import math

CURVES = ("linear", "smoothstep", "smootherstep", "ease-in", "ease-out", "ease-in-out")


def apply_curve(t: float, name: str) -> float:
    name = name.strip().lower()
    if name not in CURVES:
        known = ", ".join(CURVES)
        raise ValueError(f"unknown curve {name!r}; choose from {known}")
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    if name == "linear":
        return t
    if name == "smoothstep":
        return t * t * (3.0 - 2.0 * t)
    if name == "smootherstep":
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    if name == "ease-in":
        return t * t
    if name == "ease-out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    # ease-in-out, cosine
    return 0.5 - 0.5 * math.cos(math.pi * t)
