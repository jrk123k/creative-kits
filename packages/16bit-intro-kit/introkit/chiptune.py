"""Fallback title cue. A short PC Engine-style phrase, not a transcription.

The arrangement is the reference cut fallback: a D-minor call and answer at 92 bpm,
written here in intervals from D so `key`, `mode`, `bpm`, and `speed` can move it.
23 beats fill the phrase. At 92 bpm and 1.5x that is exactly 10.0 seconds.
"""

from __future__ import annotations

import numpy as np

SR = 44100
PHRASE_BEATS = 23.0

# MIDI numbers as written in D (D4 = 62). See _transpose.
_LEAD = [
    (0, 1, 74),
    (1, 1, 77),
    (2, 1, 81),
    (3, 1, 79),
    (4, 1, 77),
    (5, 1, 74),
    (6, 1, 72),
    (7, 1, 69),
    (12, 1, 69),
    (13, 1, 72),
    (14, 1, 74),
    (15, 2, 77),
    (17, 1, 74),
    (18, 1, 72),
    (19, 3.2, 74),
]
_HARM = [
    (0, 4, 65),
    (4, 4, 62),
    (8, 4, 69),
    (12, 4, 65),
    (16, 3, 62),
    (19, 3.2, 62),
]
_BASS = [
    (0, 4, 38),
    (4, 4, 41),
    (8, 4, 43),
    (12, 4, 38),
    (16, 3, 45),
    (19, 3.2, 38),
]
_TICKS = [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]

_NOTE = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}

# Natural minor pitch classes from the root, mapped onto the major scale.
_MINOR_TO_MAJOR = {0: 0, 2: 2, 3: 4, 5: 5, 7: 7, 8: 9, 10: 11}

METHOD = "fallback"
REASON = (
    "YIN on the first 15s of The Seventh Observation did not hold a melody: "
    "the vocal pitch wandered, the bass band was silent until a D2 at 12.9s, "
    "and the only steady tone was a D5 pad. Chroma centers on D. Tempo is not "
    "a sharp grid (a broad peak near 180 bpm), so the title is an original "
    "D-minor phrase at 92 bpm played at 1.5x. key, mode, bpm, and speed "
    "transpose and time-scale that same phrase."
)


def note_pc(key: str) -> int:
    name = key.strip().upper().replace("♯", "#").replace("♭", "B")
    if name not in _NOTE:
        known = ", ".join(sorted(set(_NOTE)))
        raise ValueError(f"unknown key {key!r} (use one of {known})")
    return _NOTE[name]


def playback_bpm(bpm: float, speed: float) -> float:
    if bpm <= 0 or speed <= 0:
        raise ValueError("bpm and speed must be positive")
    return float(bpm) * float(speed)


def phrase_seconds(bpm: float, speed: float) -> float:
    """Length of the 23-beat phrase after the speed multiplier."""
    return PHRASE_BEATS * 60.0 / playback_bpm(bpm, speed)


def _transpose(midi: int, key: str, mode: str) -> int:
    rel = int(midi) - 62  # from D4
    pc = rel % 12
    octave = rel // 12
    if mode == "major":
        if pc not in _MINOR_TO_MAJOR:
            raise ValueError(f"note class {pc} is outside the minor scale")
        pc = _MINOR_TO_MAJOR[pc]
    elif mode != "minor":
        raise ValueError("mode must be minor or major")
    return 60 + note_pc(key) + octave * 12 + pc


def _table(kind: str) -> np.ndarray:
    n = 32
    i = np.arange(n)
    if kind == "square":
        w = np.where(i < 16, 1.0, -1.0)
    elif kind == "pulse":
        w = np.where(i < 8, 1.0, -1.0)
    elif kind == "tri":
        up = np.linspace(-1.0, 1.0, 16, endpoint=False)
        down = np.linspace(1.0, -1.0, 16, endpoint=False)
        w = np.concatenate([up, down])
    else:
        raise ValueError(kind)
    return w.astype(np.float64)


def _voice(notes, wave: str, vol: float, n: int, beat: float, key: str, mode: str) -> np.ndarray:
    buf = np.zeros(n, dtype=np.float64)
    table = _table(wave)
    for start_beat, length, midi in notes:
        start = start_beat * beat
        dur = length * beat
        i0 = int(round(start * SR))
        i1 = min(n, int(round((start + dur) * SR)))
        count = i1 - i0
        if count <= 2:
            continue
        freq = 440.0 * 2.0 ** ((_transpose(midi, key, mode) - 69) / 12.0)
        phase = (np.arange(count) * freq / SR) % 1.0
        idx = (phase * 32).astype(np.int32) & 31
        env = np.ones(count)
        att = min(int(0.008 * SR), count // 4)
        rel = min(int(0.04 * SR), count // 3)
        if att > 0:
            env[:att] = np.linspace(0.0, 1.0, att, endpoint=False)
        if rel > 0:
            env[-rel:] *= np.linspace(1.0, 0.0, rel, endpoint=False)
        buf[i0:i1] += table[idx] * env * vol
    return buf


def _ticks(beats: list[float], n: int, beat: float, vol: float = 0.07) -> np.ndarray:
    """15-bit LFSR noise, a short tick on each beat. Deterministic."""
    buf = np.zeros(n, dtype=np.float64)
    state = 0x51
    span = int(0.028 * SR)
    for step in beats:
        i0 = int(round(step * beat * SR))
        i1 = min(n, i0 + span)
        for i in range(i0, i1):
            bit = ((state >> 0) ^ (state >> 1)) & 1
            state = ((state >> 1) | (bit << 14)) & 0x7FFF
            if state == 0:
                state = 1
            u = (i - i0) / span
            buf[i] += (1.0 if (state & 1) else -1.0) * (1.0 - u) * vol
    return buf


def synthesize(key: str = "D", mode: str = "minor", bpm: float = 92.0, speed: float = 1.5) -> np.ndarray:
    """Stereo float32 phrase. Peak at or under 0.9. Length follows bpm and speed."""
    beat = 60.0 / playback_bpm(bpm, speed)
    n = int(round(SR * phrase_seconds(bpm, speed)))
    lead = _voice(_LEAD, "pulse", 0.34, n, beat, key, mode)
    harm = _voice(_HARM, "square", 0.16, n, beat, key, mode)
    bass = _voice(_BASS, "tri", 0.40, n, beat, key, mode)
    noise = _ticks(_TICKS, n, beat, 0.055)
    left = lead * 0.95 + harm * 0.45 + bass + noise
    right = lead * 0.55 + harm * 0.95 + bass + noise * 0.8
    mix = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(mix))) if n else 0.0
    if peak > 0:
        mix *= min(1.0, 0.85 / peak)
    return mix.astype(np.float32)


def fit(audio: np.ndarray, seconds: float, sr: int = SR) -> np.ndarray:
    """Trim or pad to exactly `seconds`. A trim that cuts the phrase fades 10 ms."""
    n = int(round(seconds * sr))
    if n < 0:
        raise ValueError("seconds must be >= 0")
    if audio.shape[0] == n:
        return audio
    if audio.shape[0] > n:
        out = np.array(audio[:n], copy=True)
        if audio.shape[0] - n > int(0.05 * sr):
            fade = min(int(0.01 * sr), max(1, n // 2))
            ramp = np.linspace(1.0, 0.0, fade, endpoint=False, dtype=np.float32)
            out[-fade:, 0] *= ramp
            out[-fade:, 1] *= ramp
        return out
    pad = np.zeros((n - audio.shape[0], audio.shape[1]), dtype=np.float32)
    return np.concatenate([audio, pad], axis=0)
