"""Eight-bar drum machine and bass line, synthesized from oscillators and noise."""

from __future__ import annotations

import math

import numpy as np

from retro_voice.notes import beats_to_samples, parse_pitch

# Eighth-note roots for eight bars in C. Each bar is eight eighths.
_BASS = [
    "C2 C2 G2 G2 C2 C2 E2 E2",
    "F2 F2 E2 E2 D2 D2 C2 C2",
    "A1 A1 C2 C2 E2 E2 G2 G2",
    "F2 F2 E2 E2 D2 C2 B1 G1",
    "C2 E2 G2 E2 C2 E2 G2 A2",
    "F2 A2 G2 F2 E2 D2 C2 E2",
    "D2 F2 E2 C2 D2 B1 C2 E2",
    "G1 A1 B1 C2 D2 E2 G1 C2",
]


def _place(buffer: np.ndarray, start: int, clip: np.ndarray) -> None:
    if start >= len(buffer) or len(clip) == 0:
        return
    end = min(len(buffer), start + len(clip))
    buffer[start:end] += clip[: end - start]


def _kick(sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    n = int(0.18 * sample_rate)
    t = np.arange(n) / sample_rate
    freq = 150.0 * np.exp(-t * 28.0) + 46.0
    phase = np.cumsum(freq) / sample_rate * 2.0 * math.pi
    body = np.sin(phase) * np.exp(-t * 16.0)
    click = rng.standard_normal(n) * np.exp(-t * 180.0)
    return body * 0.95 + click * 0.25


def _snare(sample_rate: int, rng: np.random.Generator, length: float = 0.16) -> np.ndarray:
    n = int(length * sample_rate)
    t = np.arange(n) / sample_rate
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=noise[0])
    tone = np.sin(2.0 * math.pi * 196.0 * t) * np.exp(-t * 22.0)
    amp = np.exp(-t * 18.0)
    return (noise * 0.55 + tone * 0.45) * amp


def _hat(sample_rate: int, rng: np.random.Generator, open_hat: bool) -> np.ndarray:
    dur = 0.11 if open_hat else 0.035
    n = int(dur * sample_rate)
    t = np.arange(n) / sample_rate
    noise = rng.standard_normal(n)
    high = np.diff(noise, prepend=noise[0])
    high = np.diff(high, prepend=high[0])
    decay = 40.0 if open_hat else 95.0
    return high * np.exp(-t * decay) * (0.55 if open_hat else 0.4)


def _bass_note(freq: float, n: int, sample_rate: int) -> np.ndarray:
    if n < 2:
        return np.zeros(max(n, 0))
    phase = (np.cumsum(np.full(n, freq / sample_rate))) % 1.0
    square = np.where(phase < 0.32, 1.0, -1.0)
    coeff = 1.0 - math.exp(-2.0 * math.pi * 320.0 / sample_rate)
    out = np.empty(n)
    acc = 0.0
    for index, sample in enumerate(square):
        acc += coeff * (float(sample) - acc)
        out[index] = acc
    attack = min(n, int(0.004 * sample_rate))
    release = min(n // 2, int(0.03 * sample_rate))
    envelope = np.ones(n)
    if attack > 1:
        envelope[:attack] = np.linspace(0.0, 1.0, attack)
    if release > 1:
        envelope[-release:] *= np.linspace(1.0, 0.0, release)
    return out * envelope * 0.8


def render_beat(bpm: float, sample_rate: int = 22050, bars: int = 8, seed: int = 1) -> np.ndarray:
    if bpm <= 0 or bars < 1:
        raise ValueError("beat needs a positive tempo and at least one bar")
    total_beats = bars * 4
    n = beats_to_samples(total_beats, bpm, sample_rate)
    drums = np.zeros(n)
    bass = np.zeros(n)
    rng = np.random.default_rng(seed)
    kick = _kick(sample_rate, rng)
    snare = _snare(sample_rate, rng)
    snare_short = _snare(sample_rate, rng, 0.09)
    hat_closed = _hat(sample_rate, rng, False)
    hat_open = _hat(sample_rate, rng, True)

    for bar in range(bars):
        origin = bar * 4
        _place(drums, beats_to_samples(origin, bpm, sample_rate), kick)
        _place(drums, beats_to_samples(origin + 2, bpm, sample_rate), kick * 0.92)
        _place(drums, beats_to_samples(origin + 1, bpm, sample_rate), snare)
        _place(drums, beats_to_samples(origin + 3, bpm, sample_rate), snare)
        if bar in (3, 7):
            _place(drums, beats_to_samples(origin + 3.5, bpm, sample_rate), kick * 0.7)
        if bar == bars - 1:
            _place(drums, beats_to_samples(origin + 2.5, bpm, sample_rate), snare_short * 0.7)
            _place(drums, beats_to_samples(origin + 3.25, bpm, sample_rate), snare_short * 0.55)
            _place(drums, beats_to_samples(origin + 3.75, bpm, sample_rate), snare_short * 0.4)
        for step in range(8):
            beat = origin + step * 0.5
            open_hat = step in (3, 7)
            clip = hat_open if open_hat else hat_closed
            accent = 1.0 if step % 2 == 0 else 0.65
            _place(drums, beats_to_samples(beat, bpm, sample_rate), clip * accent)

    pattern = []
    for bar, row in enumerate(_BASS):
        if bar >= bars:
            break
        pattern.extend(row.split())
    for index, name in enumerate(pattern[: bars * 8]):
        start_beat = index * 0.5
        end_beat = start_beat + 0.46
        start = beats_to_samples(start_beat, bpm, sample_rate)
        end = beats_to_samples(end_beat, bpm, sample_rate)
        midi = parse_pitch(name)
        assert midi is not None
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        _place(bass, start, _bass_note(freq, max(1, end - start), sample_rate))

    # A short kick duck so the drums punch through the bass.
    duck = np.ones(n)
    window = max(1, int(0.08 * sample_rate))
    envelope = np.linspace(0.55, 1.0, window)
    for bar in range(bars):
        for beat in (0, 2):
            start = beats_to_samples(bar * 4 + beat, bpm, sample_rate)
            end = min(n, start + window)
            duck[start:end] = np.minimum(duck[start:end], envelope[: end - start])
    mixed = drums * 0.85 + bass * duck * 0.62
    peak = float(np.max(np.abs(mixed))) if n else 0.0
    if peak > 1e-8:
        mixed *= 0.82 / peak
    return mixed
