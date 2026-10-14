"""Shelf packer. Frames are copied into the atlas. Nothing is resampled.

Padding is empty space between frames and around the border. Rects do not
include that space. A frame wider than ``max_width`` still gets its own row.
"""

from __future__ import annotations

import numpy as np

from spritepack.errors import SpritePackError


def shelf_pack(
    items: list[tuple[str, int, int]], padding: int, max_width: int
) -> tuple[list[tuple[str, int, int, int, int]], int, int]:
    """Place ``(id, w, h)`` and return ``(id, x, y, w, h)`` plus atlas size.

    Sort is the caller's job. Placement is in the order given.
    """
    if padding < 0:
        raise SpritePackError("padding must be >= 0")
    if max_width < 1:
        raise SpritePackError("max_width must be >= 1")
    x = padding
    y = padding
    row_h = 0
    placed: list[tuple[str, int, int, int, int]] = []
    for ident, w, h in items:
        if w < 1 or h < 1:
            raise SpritePackError(f"{ident} has no pixels")
        fits = x == padding or (x + w + padding) <= max_width
        if not fits:
            y += row_h + padding
            x = padding
            row_h = 0
        placed.append((ident, x, y, w, h))
        x += w + padding
        row_h = max(row_h, h)
    if not placed:
        raise SpritePackError("nothing to pack")
    atlas_w = 0
    atlas_h = 0
    for _ident, px, py, w, h in placed:
        atlas_w = max(atlas_w, px + w + padding)
        atlas_h = max(atlas_h, py + h + padding)
    _check_layout(placed, padding, atlas_w, atlas_h)
    return placed, atlas_w, atlas_h


def blit(atlas: np.ndarray, sprite: np.ndarray, x: int, y: int) -> None:
    """Copy pixels. Alpha is not composited, so a partial pixel keeps its RGB."""
    h, w = sprite.shape[:2]
    atlas[y : y + h, x : x + w] = sprite


def crop(atlas: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    if y < 0 or x < 0 or y + h > atlas.shape[0] or x + w > atlas.shape[1]:
        raise SpritePackError(f"rect {x},{y} {w}×{h} is outside the atlas")
    return atlas[y : y + h, x : x + w].copy()


def _check_layout(placed, padding: int, atlas_w: int, atlas_h: int) -> None:
    rects = []
    for ident, x, y, w, h in placed:
        if x < padding or y < padding or x + w + padding > atlas_w or y + h + padding > atlas_h:
            raise SpritePackError(f"{ident} is closer to the atlas edge than padding {padding}")
        rects.append((ident, x, y, w, h))
    for i, a in enumerate(rects):
        for b in rects[i + 1 :]:
            if not _separated(a[1:], b[1:], padding):
                raise SpritePackError(f"{a[0]} and {b[0]} are closer than padding {padding}")


def _separated(a, b, padding: int) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax1, ay1 = ax + aw, ay + ah
    bx1, by1 = bx + bw, by + bh
    # A negative gap means the spans overlap. Zero means they touch, which is
    # legal when padding is 0.
    if ax1 <= bx:
        dx = bx - ax1
    elif bx1 <= ax:
        dx = ax - bx1
    else:
        dx = -1
    if ay1 <= by:
        dy = by - ay1
    elif by1 <= ay:
        dy = ay - by1
    else:
        dy = -1
    if dx < 0 and dy < 0:
        return False
    if dy < 0:
        return dx >= padding
    if dx < 0:
        return dy >= padding
    return True
