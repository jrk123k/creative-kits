"""Pitch estimate used to check that sung notes land on the written pitch.

This looks for the lowest strong harmonic in a short Fourier transform. A
pulse-plus-formant voice often has more energy in a higher harmonic than in
the fundamental, and an autocorrelation peak will follow that harmonic.
"""

from __future__ import annotations

import numpy as np


def estimate_f0(audio: np.ndarray, sample_rate: int, fmin: float = 70, fmax: float = 900) -> float:
    audio = np.asarray(audio, dtype=np.float64)
    if len(audio) < 16:
        raise ValueError("audio is too short to estimate pitch")
    audio = audio - np.mean(audio)
    window = audio * np.hanning(len(audio))
    spectrum = np.abs(np.fft.rfft(window))
    freqs = np.fft.rfftfreq(len(audio), 1.0 / sample_rate)
    band = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(band):
        raise ValueError("pitch search range is empty")
    weighted = spectrum.copy()
    weighted[~band] = 0.0
    peak = float(weighted.max())
    if peak < 1e-8:
        raise ValueError("audio has no energy in the pitch range")
    threshold = 0.22 * peak
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    for index in range(1, len(weighted) - 1):
        mag = weighted[index]
        if mag < threshold or mag < weighted[index - 1] or mag < weighted[index + 1]:
            continue
        left, center, right = weighted[index - 1], mag, weighted[index + 1]
        denom = left - 2.0 * center + right
        shift = 0.0 if denom == 0 else 0.5 * (left - right) / denom
        shift = max(-0.5, min(0.5, shift))
        return float(freqs[index] + shift * df)
    return float(freqs[int(np.argmax(weighted))])
