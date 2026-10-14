"""Drop-in replacements for ``introkit.chiptune``.

The intro kit's title tail calls ``synthesize(key, mode, bpm, speed)`` and
``fit(audio, seconds)``. Those names here render the same 23-beat D-minor
phrase, on the PSG instead of the old float oscillators. See the README
for the two-line import swap.
"""

from __future__ import annotations

import numpy as np

from chip.psg import SR
from chip.render import render_preset

PHRASE_BEATS = 23.0
METHOD = "psg"
REASON = (
    "The title is the demo fallback phrase: 23 beats in D minor, rendered "
    "by the HuC6280 PSG (pulse lead, square harmony, triangle bass, noise ticks). "
    "It is an original arrangement, not a transcription of the song. key, mode, "
    "bpm, and speed transpose and time-scale that phrase. At 92 bpm and speed "
    "1.5 the phrase is 10.0 seconds."
)

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
# Same table as introkit/chiptune.py so a major title still moves the thirds.
_MINOR_TO_MAJOR = {0: 0, 2: 2, 3: 4, 5: 5, 7: 7, 8: 9, 10: 11}


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
    rel = int(midi) - 62  # from D4, the key the phrase is written in
    pc = rel % 12
    octave = rel // 12
    if mode == "major":
        if pc not in _MINOR_TO_MAJOR:
            raise ValueError(f"note class {pc} is outside the minor scale")
        pc = _MINOR_TO_MAJOR[pc]
    elif mode != "minor":
        raise ValueError("mode must be minor or major")
    return 60 + note_pc(key) + octave * 12 + pc


def synthesize(key: str = "D", mode: str = "minor", bpm: float = 92.0, speed: float = 1.5) -> np.ndarray:
    """Stereo float32 title phrase. Peak at or under 0.9. Length follows bpm and speed."""
    if mode not in ("minor", "major"):
        raise ValueError("mode must be minor or major")
    tempo = playback_bpm(bpm, speed)

    def mapper(midi: int) -> int:
        return _transpose(midi, key, mode)

    return render_preset("title_loop", tempo=tempo, transpose=mapper, seamless=True)


def fit(audio: np.ndarray, seconds: float, sr: int = SR) -> np.ndarray:
    """Trim or pad to exactly ``seconds``. A trim that cuts the phrase fades 10 ms."""
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
