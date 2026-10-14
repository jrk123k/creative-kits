"""Mouth A/B patches, the same rectangle Pixel Studio exports.

The patch is the bounding box of pixels that differ, taken from the open
frame. Pasting that rectangle onto the closed plate reproduces the open still.
That is the check the 16-bit intro kit runs.
"""

from __future__ import annotations

import numpy as np

from spritepack.errors import SpritePackError


def diff_box(closed: np.ndarray, opened: np.ndarray) -> tuple[int, int, int, int] | None:
    """Minimal ``x, y, w, h`` of pixels that differ. ``None`` if they match."""
    if closed.shape != opened.shape:
        raise SpritePackError(
            f"closed and open frames differ in size: {closed.shape[1]}×{closed.shape[0]} "
            f"and {opened.shape[1]}×{opened.shape[0]}"
        )
    if closed.shape[-1] != opened.shape[-1]:
        raise SpritePackError("closed and open frames have different channel counts")
    changed = np.any(closed != opened, axis=-1)
    if not np.any(changed):
        return None
    ys, xs = np.nonzero(changed)
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return x0, y0, x1 - x0, y1 - y0


def crop(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    return image[y : y + h, x : x + w].copy()


def paste_rgb(closed: np.ndarray, patch: np.ndarray, x: int, y: int) -> np.ndarray:
    """Paste ``patch`` onto a copy of ``closed``. Compares the RGB channels."""
    out = closed.copy()
    h, w = patch.shape[:2]
    if y < 0 or x < 0 or y + h > out.shape[0] or x + w > out.shape[1]:
        raise SpritePackError(f"patch {w}×{h} at {x},{y} does not fit the plate")
    out[y : y + h, x : x + w, :3] = patch[..., :3]
    if out.shape[-1] == 4 and patch.shape[-1] == 4:
        out[y : y + h, x : x + w, 3] = patch[..., 3]
    return out


def rgb_equal(a: np.ndarray, b: np.ndarray) -> bool:
    if a.shape[:2] != b.shape[:2]:
        return False
    return bool(np.array_equal(a[..., :3], b[..., :3]))


def locate_patch(
    closed: np.ndarray, opened: np.ndarray, patch: np.ndarray
) -> tuple[int, int]:
    """Find where ``patch`` sits on the open frame and reproduces it.

    Pixel Studio's patch is the open-frame crop of the diff box, so that
    position is tried first. A larger exported rectangle is accepted when
    pasting it onto the closed plate matches the open still.
    """
    ph, pw = patch.shape[:2]
    height, width = opened.shape[:2]
    if ph > height or pw > width:
        raise SpritePackError(f"patch {pw}×{ph} is larger than the open frame")

    def accept(x: int, y: int) -> bool:
        return rgb_equal(paste_rgb(closed, patch, x, y), opened)

    box = diff_box(closed, opened)
    if box is not None and (box[2], box[3]) == (pw, ph) and accept(box[0], box[1]):
        return box[0], box[1]

    # A larger exported rectangle: find the window of the open frame it matches.
    for y in range(height - ph + 1):
        row = opened[y : y + ph]
        for x in range(width - pw + 1):
            if np.array_equal(row[:, x : x + pw], patch) and accept(x, y):
                return x, y
    raise SpritePackError(
        "the mouth patch does not paste onto the closed plate to make the open still"
    )
