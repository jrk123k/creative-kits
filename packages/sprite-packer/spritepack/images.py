"""Load and save PNG frames without resampling or alpha compositing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from spritepack.errors import SpritePackError


def load_png(path: Path) -> tuple[np.ndarray, str]:
    """Return an RGBA copy and the source mode.

    RGB becomes RGBA with alpha 255. The color channels are not scaled.
    Alpha 0 keeps its RGB, which is what Pixel Studio's eraser writes.
    """
    try:
        with Image.open(path) as im:
            mode = im.mode
            rgba = np.array(im.convert("RGBA"), dtype=np.uint8, copy=True)
    except OSError as exc:
        raise SpritePackError(f"could not read {path.name}: {exc}") from exc
    if rgba.ndim != 3 or rgba.shape[-1] != 4:
        raise SpritePackError(f"{path.name} did not load as an image")
    if rgba.shape[0] < 1 or rgba.shape[1] < 1:
        raise SpritePackError(f"{path.name} is empty")
    return rgba, mode


def save_png(path: Path, rgba: np.ndarray, mode: str) -> None:
    """Write ``rgba`` in ``mode`` when that mode can hold the pixels."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "RGB":
        if np.any(rgba[..., 3] != 255):
            image = Image.fromarray(rgba, "RGBA")
        else:
            image = Image.fromarray(rgba[..., :3], "RGB")
    else:
        image = Image.fromarray(rgba, "RGBA")
    image.save(path, format="PNG")


def scale_nearest(rgb: np.ndarray, scale: int) -> np.ndarray:
    """Integer nearest-neighbor scale. ``scale`` is a whole number >= 1."""
    if scale < 1:
        raise SpritePackError("scale must be an integer >= 1")
    if scale == 1:
        return rgb.copy()
    return np.repeat(np.repeat(rgb, scale, axis=0), scale, axis=1)


def blit_rgb(dst_rgb: np.ndarray, src_rgb: np.ndarray, x: int, y: int) -> None:
    """Copy an RGB image onto an RGB canvas. No resampling."""
    sh, sw = src_rgb.shape[:2]
    dh, dw = dst_rgb.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(dw, x + sw)
    y1 = min(dh, y + sh)
    if x0 >= x1 or y0 >= y1:
        return
    dst_rgb[y0:y1, x0:x1] = src_rgb[y0 - y : y1 - y, x0 - x : x1 - x, :3]


def composite_over(
    dst_rgb: np.ndarray, src_rgba: np.ndarray, x: int, y: int
) -> None:
    """Draw ``src`` over ``dst`` in place. Opaque and empty pixels stay exact."""
    sh, sw = src_rgba.shape[:2]
    dh, dw = dst_rgb.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(dw, x + sw)
    y1 = min(dh, y + sh)
    if x0 >= x1 or y0 >= y1:
        return
    src = src_rgba[y0 - y : y1 - y, x0 - x : x1 - x]
    alpha = src[..., 3:4].astype(np.float32) * (1.0 / 255.0)
    if np.all(alpha == 0):
        return
    region = dst_rgb[y0:y1, x0:x1]
    if np.all(alpha == 1):
        region[...] = src[..., :3]
        return
    blended = region.astype(np.float32) * (1.0 - alpha) + src[..., :3].astype(np.float32) * alpha
    region[...] = np.rint(blended).astype(np.uint8)
