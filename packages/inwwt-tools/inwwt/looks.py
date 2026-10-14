"""Standalone era looks, and the pixelate-then-dither collapse used by the transition.

Stages, each usable on its own:

* ``crt`` — curvature, scanlines, bloom, vignette, chroma
* ``pixelate`` — area-average down, nearest-neighbor back up
* ``dither`` — Bayer or Floyd–Steinberg onto a C64 palette
* ``c64`` — pixelate to a C64-width grid, then dither, nearest back up
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from inwwt.crt import CRTCache, CRTParams, apply_crt
from inwwt.dither import quantize
from inwwt.palette import get_palette


@dataclass
class LookParams:
    palette: str = "pepto"
    dither: str = "bayer"
    bayer_size: int = 4
    spread: float = 48.0
    pixel_scale: int = 6
    c64_width: int = 320
    crt: CRTParams | None = None

    def palette_array(self) -> np.ndarray:
        return get_palette(self.palette)


def resize(image: np.ndarray, width: int, height: int, resample: Image.Resampling) -> np.ndarray:
    if image.shape[1] == width and image.shape[0] == height:
        return image
    resized = Image.fromarray(image).resize((max(1, width), max(1, height)), resample)
    return np.asarray(resized)


def pixelate(image: np.ndarray, factor: int) -> np.ndarray:
    factor = max(1, int(factor))
    if factor == 1:
        return image
    height, width = image.shape[:2]
    tw = max(1, width // factor)
    th = max(1, height // factor)
    small = resize(image, tw, th, Image.Resampling.BOX)
    return resize(small, width, height, Image.Resampling.NEAREST)


def downscale_toward(image: np.ndarray, amount: float, target_width: int) -> np.ndarray:
    """Slide the working width from full resolution toward ``target_width``."""
    height, width = image.shape[:2]
    amount = 0.0 if amount < 0 else 1.0 if amount > 1 else amount
    target = min(width, max(1, int(target_width)))
    tw = int(round(width + (target - width) * amount))
    tw = max(1, min(width, tw))
    th = max(1, int(round(height * (tw / width))))
    return resize(image, tw, th, Image.Resampling.BOX)


def collapse(
    image: np.ndarray,
    pixel_amount: float,
    dither_amount: float,
    params: LookParams,
) -> np.ndarray:
    """Pixelate (``pixel_amount``) then dither (``dither_amount``), both 0..1.

    At dither 1 the returned frame uses only palette colors. Nearest-neighbor
    upscale keeps the blocks square and hard.
    """
    height, width = image.shape[:2]
    if pixel_amount <= 1e-6 and dither_amount <= 1e-6:
        return image
    small = downscale_toward(image, pixel_amount, params.c64_width)
    if dither_amount > 1e-6:
        quant = quantize(
            small,
            params.palette_array(),
            params.dither,
            bayer_size=params.bayer_size,
            spread=params.spread,
        )
        if dither_amount < 1:
            mixed = small.astype(np.float32) * (1.0 - dither_amount) + quant.astype(np.float32) * dither_amount
            small = np.clip(mixed, 0, 255).astype(np.uint8)
        else:
            small = quant
    return resize(small, width, height, Image.Resampling.NEAREST)


def apply_look(
    image: np.ndarray,
    look: str,
    params: LookParams | None = None,
    cache: CRTCache | None = None,
) -> tuple[np.ndarray, CRTCache | None]:
    params = params or LookParams()
    look = look.strip().lower()
    if look in {"none", "off", ""}:
        return image, cache
    if look == "crt":
        frame, cache = apply_crt(image, 1.0, params.crt or CRTParams(), cache)
        return frame, cache
    if look == "pixelate":
        return pixelate(image, params.pixel_scale), cache
    if look == "dither":
        return quantize(
            image,
            params.palette_array(),
            params.dither,
            bayer_size=params.bayer_size,
            spread=params.spread,
        ), cache
    if look == "c64":
        return collapse(image, 1.0, 1.0, params), cache
    if look == "full":
        frame, cache = apply_crt(image, 1.0, params.crt or CRTParams(), cache)
        return collapse(frame, 1.0, 1.0, params), cache
    raise ValueError(f"unknown look {look!r}; choose none, crt, pixelate, dither, c64, or full")
