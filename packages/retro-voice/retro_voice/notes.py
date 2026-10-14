"""Note names and the timed note events shared by scores and MIDI."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")


@dataclass
class Note:
    """One monophonic event on a beat grid. ``midi is None`` for a rest."""

    midi: int | None
    start_beat: float
    dur_beats: float
    velocity: int = 96

    @property
    def name(self) -> str:
        if self.midi is None:
            return "rest"
        return midi_name(self.midi)

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.dur_beats


def parse_pitch(token: str) -> int | None:
    text = token.strip()
    if text.lower() in {"r", "rest", "silence"}:
        return None
    match = _NOTE_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a note name: {token!r} (use C4, F#3, Bb3, or rest)")
    pitch_class = _PITCH[match.group(1).upper()]
    accidental = match.group(2)
    if accidental == "#":
        pitch_class += 1
    elif accidental == "b":
        pitch_class -= 1
    octave = int(match.group(3))
    midi = (octave + 1) * 12 + pitch_class
    if midi < 0 or midi > 127:
        raise ValueError(f"note {token} is outside MIDI 0–127")
    return midi


def midi_name(midi: int) -> str:
    midi = int(midi)
    return f"{_NAMES[midi % 12]}{midi // 12 - 1}"


def midi_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((int(midi) - 69) / 12.0))


def beats_to_samples(beats: float, bpm: float, sample_rate: int) -> int:
    if bpm <= 0:
        raise ValueError("tempo must be positive")
    return int(round(float(beats) * 60.0 * sample_rate / float(bpm)))
