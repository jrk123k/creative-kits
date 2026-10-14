"""HuC6280 PSG model. Accurate enough to sound like a PC Engine, not cycle-exact.

Clock
    The CPU master clock is 7.16 MHz. The PSG divider runs at half that,
    3.58 MHz, which is the manual's ``fmaster / 2``.

Tone
    A channel holds 32 samples. The waveform index advances once every
    ``F`` PSG clocks, where ``F`` is the 12-bit frequency register
    (R3:R2, 1..4095). Pitch is::

        hz = 3_580_000 / (32 * F)

    A4 is register 254 (440.45 Hz), matching the Hudson scale table.

Volume
    Channel level (R4) is 5-bit, 1.5 dB per step, 31 = loudest.
    Left/right balance (R5) and the main level (R1) are 4-bit, 3 dB
    per step, 15 = loudest. A 0 on any of the three stages that feed
    a speaker cuts that speaker. Attenuation of 45 dB or more is silence.

Noise
    Channels 5 and 6 only (E and F in a score). The noise register's low
    5 bits are inverted to a period, matching Geargrafx: period 32 when
    the field is 31, otherwise ``(~field & 31) << 6`` PSG clocks.
    The generator is an 18-bit LFSR, taps at bits 0, 1, 11, 12, and 17.
    Output is a full-scale 0 or 31, not the channel wavetable.

LFO
    Channels 1 and 2 only. Channel 2's wavetable is the modulator and
    channel 1 is the carrier. Modulator samples are signed 5-bit
    (value - 16). LFO control 1, 2, 3 adds that value shifted left by
    0, 2, or 4 bits onto channel 1's frequency register. The modulator
    steps once every ``F2 * FLF`` PSG clocks. Channel 2 itself keeps
    playing unless its volume is 0; this renderer does not force-mute it.
"""

from __future__ import annotations

import numpy as np

CPU_CLOCK = 7_160_000
PSG_CLOCK = CPU_CLOCK // 2  # 3_580_000
SR = 44100
LFSR_MASK = 0x3FFFF
PEAK = 0.89


def midi_to_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((float(midi) - 69.0) / 12.0)


def midi_to_divider(midi: float) -> int:
    """12-bit HuC6280 period for a MIDI note. 69 (A4) -> 254."""
    hz = midi_to_hz(midi)
    if hz <= 0:
        return 4095
    div = int(round(PSG_CLOCK / (32.0 * hz)))
    return max(1, min(4095, div))


def noise_period(reg: int) -> int:
    """PSG clocks between LFSR steps. Higher register values are higher pitch."""
    field = int(reg) & 0x1F
    if field == 0x1F:
        return 32
    return ((~field) & 0x1F) << 6


def lfsr_step(seed: int) -> int:
    seed &= LFSR_MASK
    bit = (seed ^ (seed >> 1) ^ (seed >> 11) ^ (seed >> 12) ^ (seed >> 17)) & 1
    return ((seed >> 1) | (bit << 17)) & LFSR_MASK


def side_gain(level: int, side: int, main: int) -> float:
    """Linear gain for one speaker. ``level`` is 0..31, ``side`` and ``main`` are 0..15."""
    if level <= 0 or side <= 0 or main <= 0:
        return 0.0
    steps = (31 - int(level)) + 2 * (15 - int(side)) + 2 * (15 - int(main))
    if steps >= 30:
        return 0.0
    return float(10 ** (-1.5 * steps / 20.0))


def center(samples: np.ndarray) -> np.ndarray:
    """Map 0..31 wavetable samples onto about -1..+1, 16 at zero."""
    return (samples.astype(np.float64) - 16.0) / 16.0
