"""MML score parser.

One line is either a directive (``@tempo``, ``@wave``, ...) or a channel
track. Tracks are letters A-F, channels 1-6 of the PSG. The language is
documented in the README; this module only parses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np

from chip.tables import STOCK_NAMES, check_table, stock_tables

CHANNELS = "ABCDEF"
NOISE_CHANNELS = "EF"
LFO_CHANNEL = "A"


class ScoreError(ValueError):
    """A score broke the syntax or the PSG's limits."""


@dataclass
class Segment:
    """One note or noise burst. Times are seconds as Fractions."""

    t0: Fraction
    t1: Fraction
    note_end: Fraction
    midi: int | None
    vol: int
    pan_l: int
    pan_r: int
    wave: int
    noise: bool
    noise_reg: int
    lfo_mode: int
    lfo_rate: int
    lfo_div: int
    lfo_wave: int

    @property
    def sounding(self) -> bool:
        return self.t1 > self.t0


@dataclass
class Score:
    title: str
    tempo: Fraction
    master_l: int
    master_r: int
    seamless: bool
    waves: dict[int, np.ndarray]
    names: dict[str, int]
    channels: dict[str, list[Segment]]
    ends: dict[str, Fraction]
    loop_start: Fraction
    length: Fraction

    @property
    def tempo_bpm(self) -> float:
        return float(self.tempo)

    @property
    def length_seconds(self) -> float:
        return float(self.length)

    @property
    def length_beats(self) -> float:
        """Quarter-note length at the written tempo. Exact when the tempo never changes."""
        return float(self.length * self.tempo / 60)


def parse_score(text: str) -> Score:
    waves = stock_tables()
    names = dict(STOCK_NAMES)
    tempo = Fraction(120)
    master_l, master_r = 15, 15
    title = ""
    seamless = False
    raw_channels = {c: [] for c in CHANNELS}
    saw_channel = False
    current = None

    for lineno, line in enumerate(text.splitlines(), start=1):
        body = _strip_comment(line).strip()
        if not body:
            continue
        if body.startswith("@"):
            tempo, master_l, master_r, title, seamless = _directive(
                body, lineno, waves, names, tempo, master_l, master_r, title, seamless
            )
            continue
        if body[0] in CHANNELS and (len(body) == 1 or body[1].isspace()):
            letter, mml = _channel_line(body, lineno)
            current = letter
            saw_channel = True
            if mml:
                raw_channels[letter].append(mml)
            continue
        if current is None:
            raise ScoreError(f"line {lineno}: expected a channel letter A-F, got {body[:12]!r}")
        raw_channels[current].append(body)

    if not saw_channel:
        raise ScoreError("score has no channel lines (A-F)")

    channels: dict[str, list[Segment]] = {}
    ends: dict[str, Fraction] = {}
    loop_points: list[Fraction] = []
    length = Fraction(0)
    for letter in CHANNELS:
        segs, cursor, loop_at = _parse_channel(
            " ".join(raw_channels[letter]), letter, tempo, waves, names
        )
        channels[letter] = segs
        ends[letter] = cursor
        length = max(length, cursor)
        if loop_at is not None:
            loop_points.append(loop_at)

    if length <= 0 or not any(seg.sounding for segs in channels.values() for seg in segs):
        raise ScoreError("score has no notes")
    if any(point != loop_points[0] for point in loop_points):
        raise ScoreError("loop points (|) disagree; put | at the same time on each channel that uses it")
    loop_start = loop_points[0] if loop_points else Fraction(0)
    if loop_start < 0 or loop_start >= length:
        raise ScoreError("loop point must sit inside the score, before the last event")
    return Score(
        title=title,
        tempo=tempo,
        master_l=master_l,
        master_r=master_r,
        seamless=seamless,
        waves=waves,
        names=names,
        channels=channels,
        ends=ends,
        loop_start=loop_start,
        length=length,
    )


def load_score(path: str | Path) -> Score:
    file = Path(path)
    if not file.is_file():
        raise ScoreError(f"score not found: {file}")
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScoreError(f"could not read {file}: {exc}") from exc
    try:
        return parse_score(text)
    except ScoreError as exc:
        raise ScoreError(f"{file}: {exc}") from exc


def _strip_comment(line: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(line):
        if ch == ";":
            break
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out)


def _directive(body, lineno, waves, names, tempo, master_l, master_r, title, seamless):
    parts = body[1:].split(None, 1)
    if not parts:
        raise ScoreError(f"line {lineno}: empty directive")
    name = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    if name == "tempo":
        tempo = _fraction(rest, f"line {lineno}: @tempo needs a BPM")
        if tempo <= 0:
            raise ScoreError(f"line {lineno}: @tempo must be positive")
    elif name == "master":
        nums = _two_levels(rest.replace(",", " "), 15, f"line {lineno}: @master")
        master_l, master_r = nums
    elif name == "title":
        title = rest
    elif name == "seamless":
        if rest:
            raise ScoreError(f"line {lineno}: @seamless takes no value")
        seamless = True
    elif name == "wave":
        _parse_wave(rest, lineno, waves, names)
    else:
        raise ScoreError(f"line {lineno}: unknown directive @{name}")
    return tempo, master_l, master_r, title, seamless


def _parse_wave(rest: str, lineno: int, waves: dict[int, np.ndarray], names: dict[str, int]) -> None:
    bits = rest.split(None, 1)
    if len(bits) < 2:
        raise ScoreError(f"line {lineno}: @wave needs an id and a name or 32 samples")
    try:
        wid = int(bits[0])
    except ValueError as exc:
        raise ScoreError(f"line {lineno}: wavetable id must be an integer") from exc
    if not 0 <= wid <= 31:
        raise ScoreError(f"line {lineno}: wavetable id must be 0..31")
    spec = bits[1].strip()
    key = spec.lower()
    if key in names:
        waves[wid] = np.array(waves[names[key]], copy=True)
        return
    if "," not in spec:
        known = ", ".join(sorted(set(names)))
        raise ScoreError(f"line {lineno}: unknown wavetable {spec!r} (names: {known}, or 32 comma-separated samples)")
    try:
        values = [int(p.strip(), 10) for p in spec.split(",")]
    except ValueError as exc:
        raise ScoreError(f"line {lineno}: wavetable samples must be integers") from exc
    try:
        waves[wid] = check_table(values, f"line {lineno} wavetable")
    except ValueError as exc:
        raise ScoreError(str(exc)) from exc


def _channel_line(body: str, lineno: int) -> tuple[str, str]:
    letter = body[0]
    if letter not in CHANNELS or (len(body) > 1 and not body[1].isspace()):
        raise ScoreError(f"line {lineno}: expected a channel letter A-F, got {body[:12]!r}")
    return letter, body[1:].strip()


def _parse_channel(text: str, letter: str, tempo: Fraction, waves, names):
    state = _Chan(letter=letter, tempo=tempo)
    _walk(text, state, waves, names)
    if state.pending_tie:
        raise ScoreError(f"channel {letter}: tie '&' must be followed by a note")
    if len(state.segments) > 10000:
        raise ScoreError(f"channel {letter}: too many notes")
    return state.segments, state.cursor, state.loop_at


@dataclass
class _Chan:
    letter: str
    tempo: Fraction
    cursor: Fraction = Fraction(0)
    octave: int = 4
    length: Fraction = Fraction(4)
    dots: int = 0
    vol: int = 24
    pan_l: int = 15
    pan_r: int = 15
    wave: int = 0
    noise: bool = False
    noise_reg: int = 16
    q: int = 8
    lfo_mode: int = 0
    lfo_rate: int = 128
    lfo_div: int = 512
    lfo_wave: int = 5
    pending_tie: bool = False
    loop_at: Fraction | None = None
    segments: list[Segment] = field(default_factory=list)


_SEMITONE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def _walk(text: str, state: _Chan, waves, names) -> None:
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "|":
            if state.loop_at is not None:
                raise ScoreError(f"channel {state.letter}: only one '|'")
            state.loop_at = state.cursor
            i += 1
            continue
        if ch == "[":
            body, count, i = _extract_repeat(text, i, state.letter)
            if count < 1 or count > 256:
                raise ScoreError(f"channel {state.letter}: repeat count must be 1..256")
            for _ in range(count):
                _walk(body, state, waves, names)
            continue
        if ch == "]":
            raise ScoreError(f"channel {state.letter}: ']' without '['")
        if ch == "&":
            if not state.segments:
                raise ScoreError(f"channel {state.letter}: '&' with nothing to tie")
            state.segments[-1].t1 = state.segments[-1].note_end
            state.pending_tie = True
            i += 1
            continue
        if ch in _SEMITONE:
            i = _note(text, i, state, waves)
            continue
        if ch == "r":
            if state.pending_tie:
                raise ScoreError(f"channel {state.letter}: cannot tie into a rest")
            i = _rest(text, i, state)
            continue
        if ch == "o":
            val, i = _require_int(text, i + 1, state, "octave")
            if not 0 <= val <= 8:
                raise ScoreError(f"channel {state.letter}: octave must be 0..8")
            state.octave = val
            continue
        if ch == "<":
            state.octave = max(0, state.octave - 1)
            i += 1
            continue
        if ch == ">":
            state.octave = min(8, state.octave + 1)
            i += 1
            continue
        if ch == "v":
            val, i = _require_int(text, i + 1, state, "volume")
            if not 0 <= val <= 31:
                raise ScoreError(f"channel {state.letter}: volume must be 0..31")
            state.vol = val
            continue
        if ch == "q":
            val, i = _require_int(text, i + 1, state, "gate")
            if not 1 <= val <= 8:
                raise ScoreError(f"channel {state.letter}: gate q must be 1..8")
            state.q = val
            continue
        if ch == "t":
            num, i = _require_fraction(text, i + 1, state, "tempo")
            if num <= 0:
                raise ScoreError(f"channel {state.letter}: tempo must be positive")
            state.tempo = num
            continue
        if ch == "p":
            i = _pan(text, i + 1, state)
            continue
        if ch == "w":
            state.wave, i = _wave_ref(text, i + 1, state, waves, names)
            continue
        if ch == "n":
            i = _noise(text, i, state)
            continue
        if ch == "l":
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt in "frdw":
                i = _lfo(text, i, state, waves, names)
                continue
            length, dots, i = _length_token(text, i + 1, state, required=True)
            state.length = length
            state.dots = dots
            continue
        raise ScoreError(f"channel {state.letter}: unexpected {text[i:i+8]!r}")


def _note(text: str, i: int, state: _Chan, waves) -> int:
    name = text[i]
    i += 1
    acc = 0
    if i < len(text) and text[i] in "#+":
        acc = 1
        i += 1
    elif i < len(text) and text[i] == "-":
        acc = -1
        i += 1
    length, dots, i = _length_token(text, i, state, required=False)
    dur = _apply_dots(Fraction(4) / length, dots)
    midi = (state.octave + 1) * 12 + _SEMITONE[name] + acc
    _emit(state, dur, midi, waves)
    return i


def _rest(text: str, i: int, state: _Chan) -> int:
    length, dots, i = _length_token(text, i + 1, state, required=False)
    dur = _apply_dots(Fraction(4) / length, dots)
    sec = _seconds(dur, state.tempo)
    state.cursor += sec
    return i


def _emit(state: _Chan, dur: Fraction, midi: int | None, waves) -> None:
    if state.noise and state.letter not in NOISE_CHANNELS:
        raise ScoreError(f"channel {state.letter}: noise is only available on E and F (PSG channels 5 and 6)")
    if state.lfo_mode and state.letter != LFO_CHANNEL:
        raise ScoreError(f"channel {state.letter}: LFO is only available on A (it modulates channel 1 from channel 2)")
    if state.wave not in waves:
        raise ScoreError(f"channel {state.letter}: wavetable {state.wave} is not defined")
    if state.lfo_mode and state.lfo_wave not in waves:
        raise ScoreError(f"channel {state.letter}: LFO wavetable {state.lfo_wave} is not defined")
    sec = _seconds(dur, state.tempo)
    sound = sec * state.q / 8
    t0 = state.cursor
    note_end = t0 + sec
    # '&' has already extended the previous note to its full length.
    # This note keeps its own gate unless another '&' follows.
    t1 = t0 + sound
    state.pending_tie = False
    state.segments.append(
        Segment(
            t0=t0,
            t1=t1,
            note_end=note_end,
            midi=None if state.noise else int(midi if midi is not None else 60),
            vol=state.vol,
            pan_l=state.pan_l,
            pan_r=state.pan_r,
            wave=state.wave,
            noise=state.noise,
            noise_reg=state.noise_reg,
            lfo_mode=state.lfo_mode if state.letter == LFO_CHANNEL else 0,
            lfo_rate=state.lfo_rate if state.lfo_rate else 256,
            lfo_div=state.lfo_div,
            lfo_wave=state.lfo_wave,
        )
    )
    state.cursor = note_end
    if len(state.segments) > 10000:
        raise ScoreError(f"channel {state.letter}: too many notes")


def _pan(text: str, i: int, state: _Chan) -> int:
    left, i = _require_int(text, i, state, "pan")
    right = left
    if i < len(text) and text[i] == ",":
        right, i = _require_int(text, i + 1, state, "pan")
    if not 0 <= left <= 15 or not 0 <= right <= 15:
        raise ScoreError(f"channel {state.letter}: pan must be 0..15")
    state.pan_l = left
    state.pan_r = right
    return i


def _noise(text: str, i: int, state: _Chan) -> int:
    if i + 1 < len(text) and text[i + 1] == "f":
        val, i = _require_int(text, i + 2, state, "noise frequency")
        if not 0 <= val <= 31:
            raise ScoreError(f"channel {state.letter}: noise frequency must be 0..31")
        if state.letter not in NOISE_CHANNELS:
            raise ScoreError(f"channel {state.letter}: noise is only available on E and F")
        state.noise_reg = val
        state.noise = True
        return i
    val, i = _require_int(text, i + 1, state, "noise flag")
    if val not in (0, 1):
        raise ScoreError(f"channel {state.letter}: n takes 0 or 1 (or use nf)")
    if val == 1 and state.letter not in NOISE_CHANNELS:
        raise ScoreError(f"channel {state.letter}: noise is only available on E and F")
    state.noise = bool(val)
    return i


def _lfo(text: str, i: int, state: _Chan, waves, names) -> int:
    cmd = text[i : i + 2]
    if state.letter != LFO_CHANNEL and cmd != "lw":
        # lw is harmless on other channels; lf/lr/ld belong to the carrier.
        pass
    if cmd == "lf":
        val, i = _require_int(text, i + 2, state, "LFO depth")
        if not 0 <= val <= 3:
            raise ScoreError(f"channel {state.letter}: lf must be 0..3")
        if val and state.letter != LFO_CHANNEL:
            raise ScoreError("LFO (lf) only works on channel A; it modulates channel 1 from channel 2")
        state.lfo_mode = val
        return i
    if cmd == "lr":
        val, i = _require_int(text, i + 2, state, "LFO rate")
        if not 0 <= val <= 255:
            raise ScoreError(f"channel {state.letter}: lr must be 0..255 (0 means 256)")
        state.lfo_rate = 256 if val == 0 else val
        return i
    if cmd == "ld":
        val, i = _require_int(text, i + 2, state, "LFO divider")
        if not 1 <= val <= 4095:
            raise ScoreError(f"channel {state.letter}: ld must be 1..4095")
        state.lfo_div = val
        return i
    if cmd == "lw":
        state.lfo_wave, i = _wave_ref(text, i + 2, state, waves, names)
        return i
    raise ScoreError(f"channel {state.letter}: bad LFO command {cmd!r}")


def _wave_ref(text: str, i: int, state: _Chan, waves, names) -> tuple[int, int]:
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text):
        raise ScoreError(f"channel {state.letter}: expected a wavetable")
    if text[i].isdigit():
        val, i = _require_int(text, i, state, "wavetable")
        if val not in waves:
            raise ScoreError(f"channel {state.letter}: wavetable {val} is not defined")
        return val, i
    j = i
    while j < len(text) and text[j].isalpha():
        j += 1
    key = text[i:j].lower()
    if key not in names:
        known = ", ".join(sorted(set(names)))
        raise ScoreError(f"channel {state.letter}: unknown wavetable {key!r} ({known})")
    return names[key], j


def _length_token(text: str, i: int, state: _Chan, required: bool):
    num, i2 = _read_fraction(text, i)
    if num is None:
        if required:
            raise ScoreError(f"channel {state.letter}: expected a note length")
        length, dots = state.length, state.dots
    else:
        if num <= 0:
            raise ScoreError(f"channel {state.letter}: note length must be positive")
        length = num
        i = i2
        dots = 0
    while i < len(text) and text[i] == ".":
        dots += 1
        i += 1
    return length, dots, i


def _apply_dots(dur: Fraction, dots: int) -> Fraction:
    add = dur / 2
    for _ in range(dots):
        dur += add
        add /= 2
    return dur


def _extract_repeat(text: str, i: int, letter: str):
    depth = 1
    j = i + 1
    while j < len(text) and depth:
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
        j += 1
    if depth != 0:
        raise ScoreError(f"channel {letter}: unclosed '['")
    body = text[i + 1 : j - 1]
    num, k = _read_fraction(text, j)
    if num is None:
        count = 2
    else:
        if num.denominator != 1:
            raise ScoreError(f"channel {letter}: repeat count must be an integer")
        count = int(num)
        j = k
    return body, count, j


def _seconds(beats: Fraction, tempo: Fraction) -> Fraction:
    return beats * 60 / tempo


def _read_fraction(text: str, i: int) -> tuple[Fraction | None, int]:
    j = i
    while j < len(text) and text[j].isdigit():
        j += 1
    if j < len(text) and text[j] == "." and j + 1 < len(text) and text[j + 1].isdigit():
        j += 1
        while j < len(text) and text[j].isdigit():
            j += 1
    if j == i:
        return None, i
    return Fraction(text[i:j]), j


def _require_int(text: str, i: int, state: _Chan, what: str) -> tuple[int, int]:
    num, i = _require_fraction(text, i, state, what)
    if num.denominator != 1:
        raise ScoreError(f"channel {state.letter}: {what} must be an integer")
    return int(num), i


def _require_fraction(text: str, i: int, state: _Chan, what: str) -> tuple[Fraction, int]:
    while i < len(text) and text[i].isspace():
        i += 1
    num, i = _read_fraction(text, i)
    if num is None:
        raise ScoreError(f"channel {state.letter}: expected {what}")
    return num, i


def _fraction(text: str, message: str) -> Fraction:
    token = text.split()[0] if text.split() else ""
    num, _ = _read_fraction(token, 0)
    if num is None or _ != len(token):
        raise ScoreError(message)
    return num


def _two_levels(text: str, limit: int, what: str) -> tuple[int, int]:
    bits = text.split()
    if len(bits) != 2:
        raise ScoreError(f"{what} needs two levels, left and right")
    try:
        left, right = int(bits[0]), int(bits[1])
    except ValueError as exc:
        raise ScoreError(f"{what} levels must be integers") from exc
    if not 0 <= left <= limit or not 0 <= right <= limit:
        raise ScoreError(f"{what} levels must be 0..{limit}")
    return left, right
