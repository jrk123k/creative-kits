"""Compare each shot-list lyric with the time until the next shot.

The slot is the next row's start time minus this row's start time. The last
row uses the end time written in its own time cell. Spoken duration is
syllables at the configured rate, plus a pause for each punctuation mark.
Parenthetical stage notes are not spoken.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from continuity_checker.rates import Rates, default_rates
from continuity_checker.syllables import count_syllables, pause_seconds
from continuity_checker.tables import MarkdownTable, parse_tables

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text"}
_STAMP = re.compile(r"\d+:\d{2}:\d{2}(?:\.\d+)?|\d+:\d{1,2}(?:\.\d+)?")
_MD_MARKS = re.compile(r"[*`_]+")
_PAREN = re.compile(r"\([^)]*\)")
_REPEAT = re.compile(r"(?i)\brepeats?\b")


@dataclass(frozen=True)
class VoLine:
    file: str
    line: int
    shot: str
    time_text: str
    lyric: str
    spoken_text: str
    kind: str
    start_seconds: float | None
    stated_end_seconds: float | None
    slot_seconds: float | None
    slot_source: str
    syllables: int
    pause_seconds: float
    estimate_seconds: float | None
    margin_seconds: float | None
    status: str
    note: str = ""

    @property
    def severity(self) -> str:
        if self.status in {"overrun", "time-order"}:
            return "error"
        if self.status in {"tight", "empty", "unparsed"}:
            return "warning"
        return "info"


@dataclass
class VoReport:
    shotlist: str
    rates: Rates
    files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    lines: list[VoLine] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        names = ("ok", "tight", "overrun", "silent", "empty", "unparsed", "time-order")
        found = {name: 0 for name in names}
        for line in self.lines:
            found[line.status] = found.get(line.status, 0) + 1
        return found


def fit_path(path: Path, rates: Rates | None = None) -> VoReport:
    """Read one shot list, or every text file under a folder. Inputs are only read."""
    rates = rates or default_rates()
    target = path.expanduser()
    report = VoReport(shotlist=str(path), rates=rates)
    if target.is_dir():
        files = _text_files(target)
        checked = 0
        for file in files:
            text = _read(file)
            rows = fit_text(text, file.relative_to(target).as_posix(), rates)
            if rows is None:
                report.skipped.append(file.relative_to(target).as_posix())
                continue
            report.files.append(file.relative_to(target).as_posix())
            report.lines.extend(rows)
            checked += 1
        if checked == 0:
            raise FileNotFoundError(f"no shot-list table in {path}")
        return report
    if not target.is_file():
        raise FileNotFoundError(f"shot list not found: {path}")
    text = _read(target)
    rows = fit_text(text, target.name, rates)
    if rows is None:
        raise ValueError(f"no shot-list table (need #, time, and lyric/VO columns) in {path}")
    report.files.append(target.name)
    report.lines.extend(rows)
    return report


def fit_text(text: str, file_label: str, rates: Rates) -> list[VoLine] | None:
    """Return one result per shot row, or None when the file has no shot table."""
    chosen: list[tuple[MarkdownTable, int, int, int]] = []
    for table in parse_tables(text):
        columns = _columns(table.header)
        if columns is None:
            continue
        chosen.append((table, *columns))
    if not chosen:
        return None
    lines: list[VoLine] = []
    for table, shot_at, time_at, lyric_at in chosen:
        lines.extend(_fit_table(table, shot_at, time_at, lyric_at, file_label, rates))
    return lines


def _fit_table(
    table: MarkdownTable,
    shot_at: int | None,
    time_at: int,
    lyric_at: int,
    file_label: str,
    rates: Rates,
) -> list[VoLine]:
    parsed: list[tuple[int, str, str, str, float | None, float | None]] = []
    for line_no, cells in table.rows:
        shot = _clean_shot(cells[shot_at]) if shot_at is not None else f"row {line_no}"
        time_text = _plain(cells[time_at])
        lyric = cells[lyric_at]
        start, stated_end = _parse_time_cell(time_text)
        parsed.append((line_no, shot, time_text, lyric, start, stated_end))

    results: list[VoLine] = []
    for index, (line_no, shot, time_text, lyric, start, stated_end) in enumerate(parsed):
        spoken, kind, note = _spoken(lyric)
        nxt = _next_start(parsed, index)
        slot, source, slot_note = _slot(start, stated_end, nxt)
        if slot_note:
            note = f"{note} {slot_note}".strip()
        syllables = count_syllables(spoken) if kind == "speech" else 0
        pauses = round(pause_seconds(spoken, rates.pauses or {}), 3) if kind == "speech" else 0.0
        estimate = _estimate(syllables, pauses, rates) if kind == "speech" else (0.0 if kind == "silent" else None)
        margin = _margin(slot, estimate)
        status = _status(kind, slot, margin, rates.tight_margin_seconds)
        results.append(
            VoLine(
                file=file_label,
                line=line_no,
                shot=shot,
                time_text=time_text,
                lyric=_plain(lyric),
                spoken_text=spoken,
                kind=kind,
                start_seconds=_round(start),
                stated_end_seconds=_round(stated_end),
                slot_seconds=slot,
                slot_source=source,
                syllables=syllables,
                pause_seconds=pauses,
                estimate_seconds=estimate,
                margin_seconds=margin,
                status=status,
                note=note,
            )
        )
    return results


def _columns(header: tuple[str, ...]) -> tuple[int | None, int, int] | None:
    shot_at = None
    time_at = None
    lyric_at = None
    for index, cell in enumerate(header):
        kind = _header_kind(cell)
        if kind == "shot" and shot_at is None:
            shot_at = index
        elif kind == "time" and time_at is None:
            time_at = index
        elif kind == "lyric" and lyric_at is None:
            lyric_at = index
    if time_at is None or lyric_at is None:
        return None
    return shot_at, time_at, lyric_at


def _header_kind(cell: str) -> str:
    name = _plain(cell).lower()
    if name in {"#", "no", "no.", "number", "shot", "shot #", "id"} or name.startswith("shot"):
        return "shot"
    if "time" in name or name in {"timing", "timecode", "tc", "in", "in/out"}:
        return "time"
    if any(token in name for token in ("lyric", "voiceover", "voice-over", "dialogue", "dialog")):
        return "lyric"
    if name in {"vo", "line", "copy", "script"}:
        return "lyric"
    return ""


def _spoken(cell: str) -> tuple[str, str, str]:
    raw = cell.strip()
    note = ""
    if _REPEAT.search(raw):
        note = "Estimate times the written line once. The cell says it repeats."
    plain = _plain(raw)
    if re.fullmatch(r"\s*\(.*\)\s*", plain):
        return "", "silent", note
    spoken = _PAREN.sub(" ", plain)
    spoken = spoken.replace('"', " ").replace("“", " ").replace("”", " ")
    spoken = re.sub(r"\s+", " ", spoken).strip(" \t")
    if not re.search(r"[A-Za-z]", spoken):
        return "", "silent" if plain else "empty", note
    return spoken, "speech", note


def _parse_time_cell(cell: str) -> tuple[float | None, float | None]:
    stamps = _STAMP.findall(cell)
    if not stamps:
        return None, None
    start = _clock(stamps[0])
    end = _clock(stamps[1]) if len(stamps) > 1 else None
    return start, end


def _clock(token: str) -> float:
    parts = token.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return int(parts[0]) * 60 + float(parts[1])


def _next_start(
    parsed: list[tuple[int, str, str, str, float | None, float | None]],
    index: int,
) -> float | None:
    for _, _, _, _, start, _ in parsed[index + 1 :]:
        if start is not None:
            return start
    return None


def _slot(
    start: float | None,
    stated_end: float | None,
    nxt: float | None,
) -> tuple[float | None, str, str]:
    if start is None:
        return None, "", ""
    if nxt is not None:
        note = ""
        if stated_end is not None and abs(stated_end - nxt) > 0.05:
            note = (
                f"Time cell ends at {_fmt(stated_end)}s; "
                f"the slot uses the next shot at {_fmt(nxt)}s."
            )
        return _round(nxt - start), "next-shot", note
    if stated_end is not None:
        return _round(stated_end - start), "cell-end", ""
    return None, "", "No next shot and no end time in the cell, so the slot is unknown."


def _estimate(syllables: int, pauses: float, rates: Rates) -> float:
    speech = syllables / rates.speaking_rate_syllables_per_second
    return round(speech + pauses, 3)


def _margin(slot: float | None, estimate: float | None) -> float | None:
    if slot is None or estimate is None:
        return None
    return round(slot - estimate, 3)


def _status(kind: str, slot: float | None, margin: float | None, tight: float) -> str:
    if slot is not None and slot < 0:
        return "time-order"
    if kind == "silent":
        return "silent"
    if kind == "empty":
        return "empty"
    if slot is None or margin is None:
        return "unparsed"
    if margin < 0:
        return "overrun"
    if margin <= tight:
        return "tight"
    return "ok"


def _clean_shot(cell: str) -> str:
    text = _plain(cell)
    return text or "?"


def _plain(cell: str) -> str:
    text = _MD_MARKS.sub("", cell)
    return re.sub(r"\s+", " ", text).strip()


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 3)


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not UTF-8") from exc


def _text_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        found.append(path)
    found.sort()
    return found
