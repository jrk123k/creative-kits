"""Nearest-color palette snap in OKLab, with optional Bayer dither.

The TG16 clamp reuses ``palette_snap.palette.snap_image`` from the intro kit
(PC Engine 9-bit lattice, 3 bits per channel). This module does not reimplement
that lattice.
"""

from __future__ import annotations

import numpy as np

from palette_snap.palette import snap_image

# 8×8 Bayer matrix, values 0..63. Thresholds below map this to [-0.5, 0.5].
BAYER_8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float64,
)


def srgb_u8_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """uint8 sRGB (..., 3) -> float64 OKLab (..., 3)."""
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_ = np.cbrt(np.maximum(l, 0.0))
    m_ = np.cbrt(np.maximum(m, 0.0))
    s_ = np.cbrt(np.maximum(s, 0.0))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return np.stack((L, A, B), axis=-1)


def oklab_to_srgb_u8(lab: np.ndarray) -> np.ndarray:
    """float OKLab (..., 3) -> uint8 sRGB. Used by tests and dither checks."""
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    l_ = L + 0.3963377774 * A + 0.2158037573 * B
    m_ = L - 0.1055613458 * A - 0.0638541728 * B
    s_ = L - 0.0894841775 * A - 1.2914855480 * B
    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    lin = np.clip(np.stack((r, g, b), axis=-1), 0.0, 1.0)
    srgb = np.where(
        lin <= 0.0031308,
        12.92 * lin,
        1.055 * np.power(lin, 1.0 / 2.4) - 0.055,
    )
    return np.clip(np.rint(srgb * 255.0), 0, 255).astype(np.uint8)


def _as_rgba(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[-1] not in (3, 4):
        raise ValueError("image must be HxWx3 or HxWx4")
    if arr.dtype != np.uint8:
        raise ValueError("image must be uint8")
    if arr.shape[-1] == 3:
        alpha = np.full(arr.shape[:2] + (1,), 255, dtype=np.uint8)
        return np.concatenate((arr, alpha), axis=-1)
    return np.ascontiguousarray(arr)


def _dedupe_rows(rgb: np.ndarray) -> np.ndarray:
    seen: set[tuple[int, int, int]] = set()
    out: list[tuple[int, int, int]] = []
    for row in np.asarray(rgb, dtype=np.uint8).reshape(-1, 3):
        key = (int(row[0]), int(row[1]), int(row[2]))
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    if not out:
        return np.zeros((0, 3), dtype=np.uint8)
    return np.array(out, dtype=np.uint8)


def extract_palette(reference: np.ndarray, n: int | None, *, tg16: bool = False) -> np.ndarray:
    """Opaque colors from ``reference``, most frequent first.

    ``n`` caps the count. Ties break toward the color that appears first.
    With ``tg16``, colors are clamped onto the PC Engine lattice before counting
    so duplicates that land on one hardware color merge.
    """
    rgba = _as_rgba(reference)
    rgb = rgba[..., :3]
    if tg16:
        rgb = snap_image(rgb)
    opaque = rgba[..., 3] > 0
    cols = rgb.reshape(-1, 3)[opaque.reshape(-1)]
    if cols.size == 0:
        raise ValueError("reference image has no opaque pixels")
    packed = (
        cols[:, 0].astype(np.int32) << 16
        | cols[:, 1].astype(np.int32) << 8
        | cols[:, 2].astype(np.int32)
    )
    uniq, first, counts = np.unique(packed, return_index=True, return_counts=True)
    if n is not None and n < 1:
        raise ValueError("colors must be >= 1")
    take = len(uniq) if n is None else min(int(n), len(uniq))
    order = np.lexsort((first, -counts))[:take]
    chosen = uniq[order]
    out = np.stack(
        ((chosen >> 16) & 255, (chosen >> 8) & 255, chosen & 255),
        axis=1,
    ).astype(np.uint8)
    return out


def _nn_step(pal_lab: np.ndarray) -> float:
    if len(pal_lab) < 2:
        return 0.0
    diff = pal_lab[:, None, :] - pal_lab[None, :, :]
    dist = np.sqrt(np.einsum("ijc,ijc->ij", diff, diff))
    np.fill_diagonal(dist, np.inf)
    return float(np.median(dist.min(axis=1)))


def _bayer_field(h: int, w: int) -> np.ndarray:
    thresh = (BAYER_8 + 0.5) / 64.0 - 0.5
    return thresh[np.arange(h) % 8][:, np.arange(w) % 8]


def _nearest(pixels_lab: np.ndarray, pal_lab: np.ndarray, chunk: int = 16384) -> np.ndarray:
    idx = np.empty(pixels_lab.shape[0], dtype=np.int32)
    for start in range(0, pixels_lab.shape[0], chunk):
        sl = pixels_lab[start : start + chunk]
        diff = sl[:, None, :] - pal_lab[None, :, :]
        dist2 = np.einsum("pnc,pnc->pn", diff, diff)
        idx[start : start + chunk] = np.argmin(dist2, axis=1)
    return idx


def snap_rgba(
    image: np.ndarray,
    palette: np.ndarray,
    *,
    dither: bool = False,
    dither_strength: float = 1.0,
    tg16: bool = False,
) -> np.ndarray:
    """Map ``image`` onto ``palette`` in OKLab. Alpha is copied.

    Pixels with alpha 0 keep their original RGB. Ordered dither, when on,
    adds a Bayer threshold to OKLab L only. The threshold is in [-0.5, 0.5]
    and the nudge is ``threshold * nn_distance * 0.5 * strength``, so strength
    1 stays inside the cell of an exact palette color and splits a lightness
    that sits on the midpoint.

    ``tg16`` clamps the palette, then the written RGB, with ``snap_image``.
    """
    rgba = _as_rgba(image)
    if dither_strength < 0:
        raise ValueError("dither strength must be >= 0")
    pal = np.asarray(palette, dtype=np.uint8).reshape(-1, 3)
    if pal.size == 0:
        raise ValueError("palette is empty")
    if tg16:
        pal = _dedupe_rows(snap_image(pal.reshape(1, -1, 3)).reshape(-1, 3))
        if pal.size == 0:
            raise ValueError("palette is empty")
    h, w, _ = rgba.shape
    src_rgb = rgba[..., :3]
    lab = srgb_u8_to_oklab(src_rgb)
    pal_lab = srgb_u8_to_oklab(pal)
    if dither and dither_strength > 0 and len(pal) > 1:
        step = _nn_step(pal_lab)
        lab = np.array(lab, copy=True)
        lab[..., 0] += _bayer_field(h, w) * step * 0.5 * float(dither_strength)
    idx = _nearest(lab.reshape(-1, 3), pal_lab)
    out_rgb = pal[idx].reshape(h, w, 3)
    if tg16:
        out_rgb = snap_image(out_rgb)
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[..., :3] = out_rgb
    out[..., 3] = rgba[..., 3]
    clear = rgba[..., 3] == 0
    out[..., :3][clear] = src_rgb[clear]
    return out
