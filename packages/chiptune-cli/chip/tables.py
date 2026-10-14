"""Stock 32-sample, 5-bit HuC6280 wavetables.

Samples are unsigned 0..31, the same numbers you would write into PSG
register R6. Silence-centered playback subtracts 16 inside the renderer.
"""

from __future__ import annotations

import numpy as np

# Square. First half high, second half low.
SQUARE = np.array([31] * 16 + [0] * 16, dtype=np.int16)

# Rising saw, one count per step.
SAW = np.arange(32, dtype=np.int16)

# Triangle, peak on the second half so the wrap from 1 back to 0 is a single step.
TRIANGLE = np.array(
    [
        0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
        31, 29, 27, 25, 23, 21, 19, 17, 15, 13, 11, 9, 7, 5, 3, 1,
    ],
    dtype=np.int16,
)

# 25% pulse. Brighter than the square, useful for leads.
PULSE = np.array([31] * 8 + [0] * 24, dtype=np.int16)

# 5-bit sine. Quantized from sin(2π i / 32), scaled to the full 0..31 range.
SINE = np.array(
    [
        16, 19, 21, 24, 26, 28, 30, 31, 31, 31, 30, 28, 26, 24, 21, 19,
        16, 12, 10, 7, 5, 3, 1, 0, 0, 0, 1, 3, 5, 7, 10, 12,
    ],
    dtype=np.int16,
)

# Organ-ish additive wave: fundamental + a softer octave, twelfth, and
# double octave, then quantized to 5 bits. Hollow, not buzzy.
ORGAN = np.array(
    [
        16, 22, 28, 31, 31, 29, 27, 25, 23, 22, 21, 20, 19, 18, 17, 16,
        16, 15, 14, 13, 12, 11, 10, 9, 8, 6, 4, 2, 0, 0, 3, 9,
    ],
    dtype=np.int16,
)

# id -> table. These ids are preloaded into every score.
STOCK: dict[int, np.ndarray] = {
    0: SQUARE,
    1: SAW,
    2: TRIANGLE,
    3: ORGAN,
    4: PULSE,
    5: SINE,
}

STOCK_NAMES: dict[str, int] = {
    "square": 0,
    "saw": 1,
    "triangle": 2,
    "organ": 3,
    "pulse": 4,
    "sine": 5,
}


def stock_tables() -> dict[int, np.ndarray]:
    """Copies of the stock tables, safe to overwrite per score."""
    return {i: np.array(w, copy=True) for i, w in STOCK.items()}


def check_table(values: np.ndarray, what: str = "wavetable") -> np.ndarray:
    arr = np.asarray(values, dtype=np.int16).reshape(-1)
    if arr.shape != (32,):
        raise ValueError(f"{what} needs 32 samples, got {arr.size}")
    if int(arr.min()) < 0 or int(arr.max()) > 31:
        raise ValueError(f"{what} samples must be 0..31")
    return arr
