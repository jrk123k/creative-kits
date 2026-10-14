"""Keyframe sampling and sprite frame cycles.

Positions are resolved in absolute frame indices. Python's round() is used
so a value landing on x.5 matches the reference cut saucer math (banker's round).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Keyframe:
    frame: int
    x: float | None
    y: float | None
    ease: str


def ease(u: float, name: str) -> float:
    if name in (None, "", "linear"):
        return u
    if name == "smoothstep":
        return u * u * (3.0 - 2.0 * u)
    raise ValueError(f"unknown ease {name}")


def sample_xy(frame: int, keys: list[Keyframe], x: float, y: float) -> tuple[float, float]:
    """Interpolate x, y. Missing key components stay at the sprite constant."""
    if not keys:
        return float(x), float(y)

    def xy_of(k: Keyframe) -> tuple[float, float]:
        return (float(x if k.x is None else k.x), float(y if k.y is None else k.y))

    if frame <= keys[0].frame:
        return xy_of(keys[0])
    if frame >= keys[-1].frame:
        return xy_of(keys[-1])
    for a, b in zip(keys, keys[1:]):
        if frame <= b.frame:
            span = b.frame - a.frame
            u = 0.0 if span == 0 else (frame - a.frame) / span
            u = ease(u, b.ease)
            ax, ay = xy_of(a)
            bx, by = xy_of(b)
            return ax + (bx - ax) * u, ay + (by - ay) * u
    return xy_of(keys[-1])


def round_pos(x: float, y: float) -> tuple[int, int]:
    return int(round(x)), int(round(y))


def cycle_index(local: int, count: int, mode: str, span: int, hold: int) -> int:
    """Frame index inside a cycle. `once` spreads `count` poses across `span` frames."""
    if count <= 1:
        return 0
    if mode == "once":
        if span <= 0:
            raise ValueError("cycle span must be positive")
        if local < 0:
            local = 0
        return min(count - 1, local * count // span)
    if mode == "loop":
        step = hold if hold > 0 else 1
        if local < 0:
            local = 0
        return (local // step) % count
    raise ValueError(f"unknown cycle mode {mode}")
