"""CRT curvature, scanlines, bloom, vignette, and a little chroma shift.

The distortion is a barrel remap: normalized coordinates are scaled by
``1 + k * r^2`` and samples that fall outside the source become black,
which is the dark corner of a curved tube. Strength 0 returns the frame
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


@dataclass
class CRTParams:
    curvature: float = 0.22
    scanline: float = 0.50
    bloom: float = 0.40
    bloom_radius: float = 8.0
    vignette: float = 0.45
    chroma: float = 1.5  # pixels of red/blue shift at full strength


@dataclass
class CRTCache:
    """Maps that do not change between frames of one size."""

    width: int
    height: int
    map_x: np.ndarray
    map_y: np.ndarray
    ident_x: np.ndarray
    ident_y: np.ndarray
    radius: np.ndarray
    scan_mask: np.ndarray


def _build_cache(height: int, width: int, params: CRTParams) -> CRTCache:
    ys = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    xs = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    x, y = np.meshgrid(xs, ys)
    r2 = x * x + y * y
    factor = 1.0 + np.float32(params.curvature) * r2
    src_x = x * factor
    src_y = y * factor
    map_x = (src_x + 1.0) * 0.5 * (width - 1)
    map_y = (src_y + 1.0) * 0.5 * (height - 1)
    ident_x = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width)).copy()
    ident_y = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width)).copy()
    # Radial distance in 0..1 for the vignette, 0 at the center.
    radius = np.sqrt(np.clip(r2, 0, 2)) / np.sqrt(2.0)
    scan = np.ones(height, dtype=np.float32)
    scan[1::2] = np.float32(1.0 - params.scanline)
    return CRTCache(width, height, map_x.astype(np.float32), map_y.astype(np.float32), ident_x, ident_y, radius.astype(np.float32), scan)


def _remap(image: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    """Bilinear sample. Coordinates outside the frame become black."""
    height, width = image.shape[:2]
    out = np.zeros_like(image)
    # Strip the frame so the temporaries stay small.
    step = 48
    src = image
    for y0 in range(0, height, step):
        y1 = min(height, y0 + step)
        mx = map_x[y0:y1]
        my = map_y[y0:y1]
        valid = (mx >= 0) & (mx <= width - 1) & (my >= 0) & (my <= height - 1)
        x = np.clip(mx, 0, width - 1)
        y = np.clip(my, 0, height - 1)
        x0 = np.floor(x).astype(np.int32)
        y0i = np.floor(y).astype(np.int32)
        x1 = np.minimum(x0 + 1, width - 1)
        y1i = np.minimum(y0i + 1, height - 1)
        wx = (x - x0)[..., None]
        wy = (y - y0i)[..., None]
        top = src[y0i, x0].astype(np.float32) * (1.0 - wx) + src[y0i, x1].astype(np.float32) * wx
        bot = src[y1i, x0].astype(np.float32) * (1.0 - wx) + src[y1i, x1].astype(np.float32) * wx
        sample = top * (1.0 - wy) + bot * wy
        sample[~valid] = 0
        out[y0:y1] = np.clip(sample, 0, 255).astype(np.uint8)
    return out


def _bloom(image: np.ndarray, amount: float, radius: float) -> np.ndarray:
    if amount <= 1e-4:
        return image
    blurred = Image.fromarray(image).filter(ImageFilter.GaussianBlur(radius=max(0.1, radius)))
    glow = np.asarray(blurred).astype(np.float32)
    base = image.astype(np.float32)
    # Screen the glow back on so highlights bloom and darks stay dark.
    screen = 255.0 - (255.0 - base) * (255.0 - glow) / 255.0
    mixed = base * (1.0 - amount) + screen * amount
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _chroma(image: np.ndarray, shift: float) -> np.ndarray:
    pixels = int(round(abs(shift)))
    if pixels <= 0:
        return image
    out = image.copy()
    # Red drifts one way, blue the other, green stays.
    out[:, pixels:, 0] = image[:, :-pixels, 0]
    out[:, :pixels, 0] = 0
    out[:, :-pixels, 2] = image[:, pixels:, 2]
    out[:, -pixels:, 2] = 0
    return out


def apply_crt(
    image: np.ndarray,
    strength: float,
    params: CRTParams | None = None,
    cache: CRTCache | None = None,
) -> tuple[np.ndarray, CRTCache]:
    """Apply the CRT look. ``strength`` is 0 (unchanged) to 1 (full)."""
    params = params or CRTParams()
    strength = 0.0 if strength < 0 else 1.0 if strength > 1 else float(strength)
    height, width = image.shape[:2]
    if cache is None or cache.width != width or cache.height != height:
        cache = _build_cache(height, width, params)
    if strength <= 1e-6:
        return image.copy(), cache

    map_x = (1.0 - strength) * cache.ident_x + strength * cache.map_x
    map_y = (1.0 - strength) * cache.ident_y + strength * cache.map_y
    curved = _remap(image, map_x, map_y)
    bloomed = _bloom(curved, params.bloom * strength, params.bloom_radius)
    shifted = _chroma(bloomed, params.chroma * strength)

    scan = 1.0 - (1.0 - cache.scan_mask) * strength
    vig = 1.0 - cache.radius * (params.vignette * strength)
    gain = scan[:, None] * vig
    out = np.clip(shifted.astype(np.float32) * gain[:, :, None], 0, 255).astype(np.uint8)
    return out, cache
