"""Quantize an image onto a fixed palette.

Bayer ordered dither is implemented here (the standard recursive matrix).
Floyd–Steinberg is implemented two ways:

* ``floyd_steinberg`` — Pillow's Floyd–Steinberg, which is the textbook
  filter (7/16, 3/16, 5/16, 1/16) in C. Video uses this.
* ``floyd_steinberg_native`` — the same filter in Python, used to pin the
  arithmetic in tests. It is the right choice only for tiny images.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

_PILLOW_PALETTES: dict[tuple[tuple[int, int, int], ...], Image.Image] = {}


def bayer_matrix(n: int) -> np.ndarray:
    """Return the n×n Bayer matrix, n a power of two.

    The 4×4 case is the familiar::

        0  8  2 10
        12 4 14  6
        3 11  1  9
        15 7 13  5
    """
    if n < 1 or n & (n - 1):
        raise ValueError("Bayer size must be a power of two")
    m = np.array([[0]], dtype=np.int32)
    while m.shape[0] < n:
        m = np.block(
            [
                [4 * m + 0, 4 * m + 2],
                [4 * m + 3, 4 * m + 1],
            ]
        )
    return m


def nearest(image: np.ndarray, palette: np.ndarray, chunk_rows: int = 64) -> np.ndarray:
    """Snap every pixel to the closest palette color (squared RGB distance)."""
    src = image.astype(np.float32, copy=False)
    pal = np.ascontiguousarray(palette, dtype=np.float32)
    out = np.empty(src.shape, dtype=np.uint8)
    h = src.shape[0]
    for y0 in range(0, h, chunk_rows):
        y1 = min(h, y0 + chunk_rows)
        block = src[y0:y1]
        delta = block[:, :, None, :] - pal[None, None, :, :]
        dist = np.einsum("...c,...c->...", delta, delta)
        idx = np.argmin(dist, axis=-1)
        out[y0:y1] = pal[idx]
    return out


def bayer(
    image: np.ndarray,
    palette: np.ndarray,
    *,
    size: int = 4,
    spread: float = 48.0,
) -> np.ndarray:
    """Ordered dither. ``spread`` is the peak-to-peak threshold in 8-bit levels."""
    h, w = image.shape[:2]
    matrix = bayer_matrix(size).astype(np.float32)
    # Center the threshold on zero so a palette color stays put when spread is modest.
    norm = (matrix + 0.5) / float(size * size) - 0.5
    tiles_y = (h + size - 1) // size
    tiles_x = (w + size - 1) // size
    tiled = np.tile(norm, (tiles_y, tiles_x))[:h, :w]
    adjusted = image.astype(np.float32) + tiled[:, :, None] * float(spread)
    np.clip(adjusted, 0, 255, out=adjusted)
    return nearest(adjusted, palette)


def _pillow_palette(palette: np.ndarray) -> Image.Image:
    colors = tuple(tuple(int(c) for c in row) for row in palette)
    cached = _PILLOW_PALETTES.get(colors)
    if cached is not None:
        return cached
    img = Image.new("P", (16, 16))
    flat: list[int] = []
    for i in range(256):
        r, g, b = colors[i % len(colors)]
        flat.extend((r, g, b))
    img.putpalette(flat)
    _PILLOW_PALETTES[colors] = img
    return img


def floyd_steinberg(image: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Floyd–Steinberg dither onto ``palette`` (Pillow's C implementation)."""
    src = Image.fromarray(np.ascontiguousarray(image), mode="RGB")
    quantized = src.quantize(palette=_pillow_palette(palette), dither=Image.Dither.FLOYDSTEINBERG)
    return np.asarray(quantized.convert("RGB"))


def floyd_steinberg_native(image: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Textbook Floyd–Steinberg. Serpentine is off; errors use integer //16.

    Distribution from the current pixel ``*``::

            *   7/16
        3/16 5/16 1/16
    """
    h, w = image.shape[:2]
    work = image.astype(np.int16, copy=True)
    pal = palette.astype(np.int16, copy=False)
    out_idx = np.empty((h, w), dtype=np.int32)
    n = int(pal.shape[0])
    for y in range(h):
        for x in range(w):
            r = int(work[y, x, 0])
            g = int(work[y, x, 1])
            b = int(work[y, x, 2])
            best = 0
            best_d = 1 << 30
            for i in range(n):
                dr = r - int(pal[i, 0])
                dg = g - int(pal[i, 1])
                db = b - int(pal[i, 2])
                dist = dr * dr + dg * dg + db * db
                if dist < best_d:
                    best_d = dist
                    best = i
            out_idx[y, x] = best
            er = r - int(pal[best, 0])
            eg = g - int(pal[best, 1])
            eb = b - int(pal[best, 2])
            if x + 1 < w:
                work[y, x + 1, 0] += (er * 7) // 16
                work[y, x + 1, 1] += (eg * 7) // 16
                work[y, x + 1, 2] += (eb * 7) // 16
            if y + 1 < h:
                if x > 0:
                    work[y + 1, x - 1, 0] += (er * 3) // 16
                    work[y + 1, x - 1, 1] += (eg * 3) // 16
                    work[y + 1, x - 1, 2] += (eb * 3) // 16
                work[y + 1, x, 0] += (er * 5) // 16
                work[y + 1, x, 1] += (eg * 5) // 16
                work[y + 1, x, 2] += (eb * 5) // 16
                if x + 1 < w:
                    work[y + 1, x + 1, 0] += (er * 1) // 16
                    work[y + 1, x + 1, 1] += (eg * 1) // 16
                    work[y + 1, x + 1, 2] += (eb * 1) // 16
    return palette[out_idx]


def quantize(
    image: np.ndarray,
    palette: np.ndarray,
    method: str,
    *,
    bayer_size: int = 4,
    spread: float = 48.0,
) -> np.ndarray:
    method = method.strip().lower()
    if method in {"none", "nearest"}:
        return nearest(image, palette)
    if method == "bayer":
        return bayer(image, palette, size=bayer_size, spread=spread)
    if method in {"floyd", "floyd-steinberg", "fs"}:
        return floyd_steinberg(image, palette)
    raise ValueError(f"unknown dither method {method!r}; choose nearest, bayer, or floyd")
