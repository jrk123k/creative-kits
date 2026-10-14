"""80s vocal chain: ring mod, a resonant state-variable filter, sample-and-hold, bitcrush, chorus.

The filter is the Chamberlin state-variable structure (low-pass, band-pass,
high-pass with a resonance control). It is written from the public signal
flow, not taken from a SID emulator.
"""

from __future__ import annotations

import math

import numpy as np

from retro_voice.controls import EffectChain


def bitcrush(audio: np.ndarray, bits: int) -> np.ndarray:
    if bits <= 0 or bits >= 16:
        return audio
    levels = (1 << int(bits)) - 1
    shaped = np.clip(audio, -1.0, 1.0)
    quantized = np.round((shaped + 1.0) * 0.5 * levels) / levels * 2.0 - 1.0
    return quantized


def sample_and_hold(audio: np.ndarray, factor: int) -> np.ndarray:
    factor = int(factor)
    if factor <= 1 or len(audio) == 0:
        return audio
    index = (np.arange(len(audio)) // factor) * factor
    return audio[index]


def ring_mod(audio: np.ndarray, sample_rate: int, freq: float, mix: float) -> np.ndarray:
    if freq <= 0 or mix <= 0 or len(audio) == 0:
        return audio
    time = np.arange(len(audio)) / sample_rate
    wet = audio * np.sin(2.0 * math.pi * freq * time)
    return audio * (1.0 - mix) + wet * mix


def sid_filter(
    audio: np.ndarray,
    sample_rate: int,
    cutoff: float,
    resonance: float,
    mode: str,
) -> np.ndarray:
    if mode == "off" or len(audio) == 0:
        return audio
    cutoff = min(max(cutoff, 40.0), sample_rate * 0.22)
    damp = 1.15 - 0.95 * min(max(resonance, 0.0), 0.98)
    freq = 2.0 * math.sin(math.pi * cutoff / sample_rate)
    low = 0.0
    band = 0.0
    out = np.empty(len(audio))
    for index, sample in enumerate(audio):
        high = float(sample) - low - damp * band
        band += freq * high
        low += freq * band
        if mode == "lp":
            out[index] = low
        elif mode == "bp":
            out[index] = band
        else:
            out[index] = high
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def chorus(
    audio: np.ndarray,
    sample_rate: int,
    mix: float,
    rate: float,
    depth_ms: float,
    delay_ms: float,
) -> np.ndarray:
    if mix <= 0 or len(audio) == 0:
        return audio
    count = len(audio)
    time = np.arange(count) / sample_rate
    delay = (delay_ms + depth_ms * np.sin(2.0 * math.pi * rate * time)) * sample_rate / 1000.0
    wet = np.empty(count)
    for index in range(count):
        position = index - delay[index]
        if position < 1:
            wet[index] = audio[index]
            continue
        left = int(position)
        if left + 1 >= count:
            wet[index] = audio[min(left, count - 1)]
            continue
        frac = position - left
        wet[index] = audio[left] * (1.0 - frac) + audio[left + 1] * frac
    return audio * (1.0 - mix) + wet * mix


def apply_chain(audio: np.ndarray, sample_rate: int, chain: EffectChain) -> np.ndarray:
    chain = chain.validated()
    out = np.array(audio, dtype=np.float64, copy=True)
    if chain.ring_hz > 0 and chain.ring_mix > 0:
        out = ring_mod(out, sample_rate, chain.ring_hz, chain.ring_mix)
    if chain.filter_mode != "off":
        out = sid_filter(out, sample_rate, chain.cutoff, chain.resonance, chain.filter_mode)
    if chain.downsample > 1:
        out = sample_and_hold(out, chain.downsample)
    if 0 < chain.bitcrush < 16:
        out = bitcrush(out, chain.bitcrush)
    if chain.chorus_mix > 0:
        out = chorus(
            out,
            sample_rate,
            chain.chorus_mix,
            chain.chorus_rate,
            chain.chorus_depth_ms,
            chain.chorus_delay_ms,
        )
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 1.0:
        out *= 0.98 / peak
    return out
