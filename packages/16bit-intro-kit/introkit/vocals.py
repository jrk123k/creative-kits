"""Vocal windows, inline or merged from a WhisperX-style alignment."""

from __future__ import annotations

import json
from pathlib import Path

from introkit.errors import ConfigError


def load_alignment(path: Path) -> dict | list:
    try:
        data = json.loads(Path(path).read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"alignment {path} is not JSON: {exc}") from exc
    return data


def extract_words(data: dict | list) -> list[dict]:
    """Prefer word_segments, else each segment's words, else the segments themselves."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise ConfigError("alignment JSON must be an object or a list of words")
    if data.get("word_segments"):
        return list(data["word_segments"])
    words: list[dict] = []
    segments = data.get("segments")
    if not segments:
        raise ConfigError("alignment JSON has no word_segments or segments")
    for seg in segments:
        nested = seg.get("words")
        if nested:
            words.extend(nested)
        else:
            words.append(
                {
                    "word": seg.get("text") or seg.get("word") or "",
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "speaker": seg.get("speaker"),
                }
            )
    return words


def merge_words(words: list[dict], gap: float, speaker: str | None = None) -> list[dict]:
    """Merge words into lines. A gap strictly greater than `gap` seconds starts a line.

    Words are merged when the silence between them is less than or equal to `gap`.
    """
    lines: list[dict] = []
    kept = 0
    for raw in words:
        if "start" not in raw or "end" not in raw or raw["start"] is None or raw["end"] is None:
            raise ConfigError(f"alignment word is missing start/end: {raw!r}")
        word_speaker = raw.get("speaker")
        if speaker and word_speaker not in (None, "", speaker):
            continue
        kept += 1
        start = float(raw["start"])
        end = float(raw["end"])
        if end < start:
            raise ConfigError(f"alignment word ends before it starts: {raw!r}")
        text = str(raw.get("word") if raw.get("word") is not None else raw.get("text") or "").strip()
        # 1e-4 absorbs binary noise so a gap of exactly the threshold still merges.
        if lines and start - float(lines[-1]["end"]) <= gap + 1e-4:
            prev = lines[-1]
            prev["end"] = max(float(prev["end"]), end)
            prev["text"] = (str(prev["text"]) + " " + text).strip()
        else:
            lines.append({"start": start, "end": end, "text": text, "mouth": True})
    if speaker and kept == 0:
        raise ConfigError(f"alignment has no words for speaker {speaker!r}")
    if not lines:
        raise ConfigError("alignment produced no vocal lines")
    return lines
