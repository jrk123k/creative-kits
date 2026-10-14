"""Text and JSON melody scores.

A ``.rvscore`` file is a header plus one note per line::

    tempo 100
    preset lead
    lyrics: It's not what we thought to-night

    C4 1 It's
    E4 1 not

Inline lyric tokens are joined and parsed with the hyphen rules, so put one
syllable token on each note (``to-`` then ``night``, and ``-`` for a melisma).
A ``lyrics:`` header is the other way to supply the line.
"""

from __future__ import annotations

import json
from pathlib import Path

from retro_voice.controls import VoiceControls, voice_preset
from retro_voice.notes import Note, parse_pitch


def _controls_from_mapping(data: dict, base: VoiceControls | None = None) -> VoiceControls:
    controls = base or VoiceControls()
    if data.get("preset"):
        controls = voice_preset(str(data["preset"]))
    updates = {}
    for key in ("pitch", "speed", "mouth", "throat"):
        if data.get(key) is not None:
            updates[key] = int(data[key])
    if updates:
        controls = VoiceControls(
            pitch=updates.get("pitch", controls.pitch),
            speed=updates.get("speed", controls.speed),
            mouth=updates.get("mouth", controls.mouth),
            throat=updates.get("throat", controls.throat),
        )
    return controls.validated()


def notes_from_pairs(pairs: list[tuple[int | None, float]]) -> list[Note]:
    notes: list[Note] = []
    cursor = 0.0
    for midi, beats in pairs:
        beats = float(beats)
        if beats <= 0:
            raise ValueError("note duration must be positive")
        notes.append(Note(midi=midi, start_beat=cursor, dur_beats=beats))
        cursor += beats
    if not notes:
        raise ValueError("score has no notes")
    return notes


def load_score(path: str) -> tuple[list[Note], str | None, float | None, VoiceControls]:
    file = Path(path)
    if file.suffix.lower() == ".json":
        return _load_json(file)
    return _load_text(file)


def _load_json(file: Path) -> tuple[list[Note], str | None, float | None, VoiceControls]:
    data = json.loads(file.read_text(encoding="utf-8"))
    controls = _controls_from_mapping(data)
    tempo = float(data["tempo"]) if data.get("tempo") is not None else None
    lyrics = data.get("lyrics")
    pairs = []
    for item in data.get("notes", []):
        pitch = item.get("pitch", item.get("n", item.get("note")))
        beats = item.get("beats", item.get("dur"))
        if pitch is None or beats is None:
            raise ValueError(f"note entry needs pitch and beats: {item}")
        pairs.append((parse_pitch(str(pitch)), beats))
    return notes_from_pairs(pairs), lyrics, tempo, controls


def _load_text(file: Path) -> tuple[list[Note], str | None, float | None, VoiceControls]:
    header: dict[str, str] = {}
    lyric_header: str | None = None
    pairs: list[tuple[int | None, float]] = []
    tokens: list[str] = []
    for line_no, raw in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("lyrics:"):
            lyric_header = line.split(":", 1)[1].strip()
            continue
        parts = line.split()
        key = parts[0].lower()
        if key in {"tempo", "pitch", "speed", "mouth", "throat", "preset"} and len(parts) == 2 and not _looks_like_note(parts[0]):
            header[key] = parts[1]
            continue
        if len(parts) < 2:
            raise ValueError(f"{file.name}:{line_no}: expected 'C4 1 syllable'")
        try:
            midi = parse_pitch(parts[0])
            beats = float(parts[1])
        except ValueError as exc:
            raise ValueError(f"{file.name}:{line_no}: {exc}") from exc
        pairs.append((midi, beats))
        if len(parts) > 2:
            tokens.append(" ".join(parts[2:]))
    if lyric_header and tokens:
        raise ValueError("score has both a lyrics: header and lyric tokens on note lines")
    lyrics = lyric_header if lyric_header is not None else (" ".join(tokens) if tokens else None)
    tempo = float(header["tempo"]) if "tempo" in header else None
    controls = _controls_from_mapping(header)
    return notes_from_pairs(pairs), lyrics, tempo, controls


def _looks_like_note(token: str) -> bool:
    try:
        parse_pitch(token)
    except ValueError:
        return False
    return True


def dump_score(
    path: str,
    notes: list[Note],
    lyrics: str,
    bpm: float,
    controls: VoiceControls,
    preset_name: str | None = None,
) -> None:
    """Write one syllable token per sounding note. Rests get no lyric."""
    from retro_voice.lyrics import parse_lyrics

    syllables = parse_lyrics(lyrics)
    sounding = [note for note in notes if note.midi is not None]
    if len(syllables) != len(sounding):
        raise ValueError("cannot dump a score whose syllables and notes disagree")
    lines = [f"tempo {bpm:g}"]
    if preset_name:
        lines.append(f"preset {preset_name}")
    lines.append(f"pitch {controls.pitch}")
    lines.append(f"speed {controls.speed}")
    lines.append(f"mouth {controls.mouth}")
    lines.append(f"throat {controls.throat}")
    lines.append("")
    syl_iter = iter(syllables)
    for note in notes:
        if note.midi is None:
            lines.append(f"rest {note.dur_beats:g}")
            continue
        syl = next(syl_iter)
        if syl.melisma:
            token = "-"
        elif syl.phonemes is not None:
            token = syl.display
        else:
            token = syl.grapheme
            continues = any(
                other.word_id == syl.word_id
                and not other.melisma
                and other.phonemes is None
                and other.slice_index > syl.slice_index
                for other in syllables
            )
            if continues:
                token += "-"
        lines.append(f"{note.name} {note.dur_beats:g} {token}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
