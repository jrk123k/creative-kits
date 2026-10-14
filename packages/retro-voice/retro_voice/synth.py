"""Parallel formant synthesizer.

Three two-pole resonators on a pulse excitation, plus a noise resonator for
fricatives and bursts. The coefficient update is the ordinary digital
resonator (radius from bandwidth, cosine from frequency), not a port of any
SAM routine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from retro_voice.g2p import Phone
from retro_voice.phonemes import PHONES, VOWEL_KINDS, shape_formants

SR_DEFAULT = 22050


@dataclass
class Micro:
    n: int
    f1: float
    f2: float
    f3: float
    bw1: float
    bw2: float
    bw3: float
    voice: float
    noise: float
    nf: float
    nbw: float
    f0: float
    f1b: float | None = None
    f2b: float | None = None
    f3b: float | None = None


def _fit(parts: list[Micro], total: int) -> list[Micro]:
    if total < 1:
        return []
    if not parts:
        parts = [Micro(total, 500, 1500, 2500, 80, 110, 160, 0, 0, 2000, 800, 100)]
    used = sum(part.n for part in parts)
    parts[-1].n += total - used
    if parts[-1].n < 1:
        parts[-1].n = 1
        overflow = sum(part.n for part in parts) - total
        for part in reversed(parts[:-1]):
            if overflow <= 0:
                break
            spare = part.n - 1
            take = min(spare, overflow)
            part.n -= take
            overflow -= take
    return [part for part in parts if part.n > 0]


def expand_phone(
    phone: Phone,
    samples: int,
    f0: float,
    mouth: int,
    throat: int,
    amplitude: float = 1.0,
    next_vowel: tuple[float, float, float] | None = None,
) -> list[Micro]:
    spec = PHONES[phone.name]
    f1, f2, f3 = shape_formants(spec.f1, spec.f2, spec.f3, mouth, throat)
    if phone.name == "HH" and next_vowel is not None:
        f1, f2, f3 = shape_formants(*next_vowel, mouth, throat)
    f1b = f2b = f3b = None
    if spec.f1b is not None:
        f1b, f2b, f3b = shape_formants(spec.f1b, spec.f2b or spec.f2, spec.f3b or spec.f3, mouth, throat)
    amp = max(0.0, amplitude)
    if spec.kind == "pause" or samples <= 0:
        return _fit([Micro(max(samples, 0), f1, f2, f3, spec.bw1, spec.bw2, spec.bw3, 0, 0, spec.nf, spec.nbw, f0)], samples)

    if spec.kind == "stop":
        closure_n = max(1, int(round(samples * 0.7)))
        burst_n = max(1, samples - closure_n)
        if closure_n + burst_n != samples:
            closure_n = samples - burst_n
        voice_bar = 0.28 * amp if spec.voiced_stop else 0.0
        closure = Micro(
            closure_n, 200, 700, 2100, 90, 140, 180,
            voice_bar, 0.0, spec.nf, spec.nbw, f0,
        )
        burst = Micro(
            burst_n, f1, f2, f3, spec.bw1, spec.bw2, spec.bw3,
            0.12 * amp if spec.voiced_stop else 0.0,
            1.15 * amp, spec.nf, spec.nbw, f0,
        )
        return _fit([closure, burst], samples)

    if spec.kind == "affricate":
        closure_n = max(1, int(round(samples * 0.28)))
        burst_n = max(1, int(round(samples * 0.16)))
        fric_n = max(1, samples - closure_n - burst_n)
        parts = [
            Micro(closure_n, 220, 800, 2200, 100, 150, 180, 0.2 * amp if spec.voiced_stop else 0.0, 0.0, spec.nf, spec.nbw, f0),
            Micro(burst_n, f1, f2, f3, spec.bw1, spec.bw2, spec.bw3, 0.0, 1.0 * amp, spec.nf, max(400, spec.nbw * 0.6), f0),
            Micro(fric_n, f1, f2, f3, spec.bw1, spec.bw2, spec.bw3, spec.voice * amp, spec.noise * amp, spec.nf, spec.nbw, f0),
        ]
        return _fit(parts, samples)

    return _fit(
        [
            Micro(
                samples, f1, f2, f3, spec.bw1, spec.bw2, spec.bw3,
                spec.voice * amp, spec.noise * amp, spec.nf, spec.nbw, f0,
                f1b, f2b, f3b,
            )
        ],
        samples,
    )


def paint(micros: list[Micro], start: int, curves: dict[str, np.ndarray]) -> None:
    cursor = start
    for part in micros:
        end = cursor + part.n
        sl = slice(cursor, end)
        if part.f1b is None:
            curves["f1"][sl] = part.f1
            curves["f2"][sl] = part.f2
            curves["f3"][sl] = part.f3
        else:
            curves["f1"][sl] = np.linspace(part.f1, part.f1b, part.n)
            curves["f2"][sl] = np.linspace(part.f2, part.f2b, part.n)
            curves["f3"][sl] = np.linspace(part.f3, part.f3b, part.n)
        curves["bw1"][sl] = part.bw1
        curves["bw2"][sl] = part.bw2
        curves["bw3"][sl] = part.bw3
        curves["voice"][sl] = part.voice
        curves["noise"][sl] = part.noise
        curves["nf"][sl] = part.nf
        curves["nbw"][sl] = part.nbw
        curves["f0"][sl] = part.f0
        cursor = end


def blank_curves(n: int, f0: float = 110.0) -> dict[str, np.ndarray]:
    return {
        "f1": np.full(n, 500.0),
        "f2": np.full(n, 1500.0),
        "f3": np.full(n, 2500.0),
        "bw1": np.full(n, 80.0),
        "bw2": np.full(n, 110.0),
        "bw3": np.full(n, 160.0),
        "voice": np.zeros(n),
        "noise": np.zeros(n),
        "nf": np.full(n, 2500.0),
        "nbw": np.full(n, 900.0),
        "f0": np.full(n, f0),
    }


def _smooth(values: np.ndarray, sample_rate: int, tau: float) -> np.ndarray:
    if tau <= 0 or len(values) < 2:
        return values
    coeff = math.exp(-1.0 / (tau * sample_rate))
    out = np.empty_like(values)
    out[0] = values[0]
    for index in range(1, len(values)):
        out[index] = values[index] + coeff * (out[index - 1] - values[index])
    return out


def _coeff(freq: float, bw: float, sample_rate: int) -> tuple[float, float, float]:
    freq = min(max(freq, 40.0), sample_rate * 0.45)
    bw = max(bw, 30.0)
    radius = math.exp(-math.pi * bw / sample_rate)
    b1 = 2.0 * radius * math.cos(2.0 * math.pi * freq / sample_rate)
    b2 = -(radius * radius)
    gain = 1.0 - radius
    return gain, b1, b2


def synthesize(curves: dict[str, np.ndarray], sample_rate: int = SR_DEFAULT, seed: int = 0) -> np.ndarray:
    n = len(curves["f0"])
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    f0 = _smooth(curves["f0"], sample_rate, 0.008)
    f1 = _smooth(curves["f1"], sample_rate, 0.012)
    f2 = _smooth(curves["f2"], sample_rate, 0.012)
    f3 = _smooth(curves["f3"], sample_rate, 0.012)
    voice = _smooth(np.clip(curves["voice"], 0, 2), sample_rate, 0.0025)
    noise_amp = _smooth(np.clip(curves["noise"], 0, 2), sample_rate, 0.002)
    nf = curves["nf"]
    nbw = curves["nbw"]
    bw1, bw2, bw3 = curves["bw1"], curves["bw2"], curves["bw3"]

    phase = np.cumsum(np.maximum(f0, 1.0) / sample_rate)
    frac = phase - np.floor(phase)
    open_q = 0.45
    pulse = np.zeros(n)
    mask = frac < open_q
    pulse[mask] = np.sin(np.pi * frac[mask] / open_q) ** 2
    derivative = np.empty(n)
    derivative[0] = 0.0
    derivative[1:] = pulse[1:] - pulse[:-1]
    # The pulse keeps the buzzy robot timbre. A sine at F0 is mixed back in
    # after the formant filters so low sung notes do not collapse onto the
    # second harmonic.
    excit = derivative * voice * 4.0
    fundamental = np.sin(2.0 * math.pi * phase) * voice

    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n) * noise_amp * 0.45

    out = np.zeros(n)
    z1 = z2 = z3 = z4 = z5 = z6 = zn1 = zn2 = 0.0
    hop = 8
    index = 0
    while index < n:
        end = min(n, index + hop)
        a1, b11, b21 = _coeff(float(f1[index]), float(bw1[index]), sample_rate)
        a2, b12, b22 = _coeff(float(f2[index]), float(bw2[index]), sample_rate)
        a3, b13, b23 = _coeff(float(f3[index]), float(bw3[index]), sample_rate)
        an, bn1, bn2 = _coeff(float(nf[index]), float(nbw[index]), sample_rate)
        for k in range(index, end):
            sample = excit[k]
            y1 = a1 * sample + b11 * z1 + b21 * z2
            z2, z1 = z1, y1
            y2 = a2 * sample + b12 * z3 + b22 * z4
            z4, z3 = z3, y2
            y3 = a3 * sample + b13 * z5 + b23 * z6
            z6, z5 = z5, y3
            yn = an * noise[k] + bn1 * zn1 + bn2 * zn2
            zn2, zn1 = zn1, yn
            out[k] = y1 + 0.62 * y2 + 0.24 * y3 + yn + 0.55 * fundamental[k]
        index = end

    # One-pole highpass to drop resonator offset.
    blocked = np.empty(n)
    blocked[0] = out[0]
    for index in range(1, n):
        blocked[index] = out[index] - out[index - 1] + 0.995 * blocked[index - 1]
    fade = min(n // 2, int(0.006 * sample_rate))
    if fade > 1:
        blocked[:fade] *= np.linspace(0.0, 1.0, fade)
        blocked[-fade:] *= np.linspace(1.0, 0.0, fade)
    blocked = np.nan_to_num(blocked, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(blocked))) if n else 0.0
    if peak > 1e-8:
        blocked *= 0.8 / peak
    return blocked


def next_vowel_targets(phones: list[Phone]) -> list[tuple[float, float, float] | None]:
    upcoming: tuple[float, float, float] | None = None
    found: list[tuple[float, float, float] | None] = [None] * len(phones)
    for index in range(len(phones) - 1, -1, -1):
        found[index] = upcoming
        spec = PHONES[phones[index].name]
        if spec.kind in VOWEL_KINDS:
            upcoming = (spec.f1, spec.f2, spec.f3)
    return found
