"""Markdown and JSON for the voiceover fit check."""

from __future__ import annotations

import json

from continuity_checker import __version__
from continuity_checker.vo_fit import VoLine, VoReport

_FLAGGED = {"overrun", "tight", "empty", "unparsed", "time-order"}


def render_markdown(report: VoReport) -> str:
    counts = report.counts()
    rate = report.rates.speaking_rate_syllables_per_second
    tight = report.rates.tight_margin_seconds
    lines: list[str] = [
        "# Voiceover fit report",
        "",
        f"Read **{len(report.lines)}** shot line(s) from `{report.shotlist}`.",
        "",
        f"Speaking rate **{rate:g}** syllables/s. "
        f"A fit with **{tight:.2f}s** or less to spare is tight. "
        f"Rates: `{report.rates.source}`.",
        "",
        f"**Overruns:** {counts.get('overrun', 0)}. "
        f"**Tight:** {counts.get('tight', 0)}. "
        f"**Ok:** {counts.get('ok', 0)}. "
        f"**Silent:** {counts.get('silent', 0)}.",
        "",
        "| Status | Lines |",
        "|---|---|",
    ]
    for name in ("overrun", "tight", "ok", "silent", "empty", "unparsed", "time-order"):
        lines.append(f"| {name} | {counts.get(name, 0)} |")
    lines.extend(["", "## Flags", ""])
    flagged = [item for item in report.lines if item.status in _FLAGGED]
    if not flagged:
        lines.append("No overruns or tight fits.")
        lines.append("")
    for index, item in enumerate(flagged, start=1):
        lines.extend(_flag_md(index, item))
    lines.extend(["## Lines", ""])
    lines.append("| Shot | Line | Slot (s) | Syllables | Estimate (s) | Margin (s) | Status |")
    lines.append("|---|---|---|---|---|---|---|")
    if not report.lines:
        lines.append("| — | — | — | — | — | — | No shot rows. |")
    for item in report.lines:
        lines.append(
            f"| {item.shot} | {item.line} | {_num(item.slot_seconds)} | {item.syllables} | "
            f"{_num(item.estimate_seconds)} | {_num(item.margin_seconds)} | {item.status} |"
        )
    notes = [item for item in report.lines if item.note]
    lines.extend(["", "## Notes", ""])
    if notes:
        for item in notes:
            lines.append(f"- **{item.shot}** (line {item.line}): {item.note}")
    else:
        lines.append("No notes.")
    lines.append("")
    if report.skipped:
        lines.extend(["## Files with no shot table", ""])
        lines.extend(f"- `{name}`" for name in report.skipped)
        lines.append("")
    return "\n".join(lines)


def render_json(report: VoReport) -> str:
    counts = report.counts()
    payload = {
        "tool": "vo-fit",
        "version": __version__,
        "shotlist": report.shotlist,
        "rates": report.rates.as_dict(),
        "summary": {
            "files": report.files,
            "files_skipped": report.skipped,
            "lines": len(report.lines),
            "by_status": counts,
            "overruns": counts.get("overrun", 0),
            "tight": counts.get("tight", 0),
        },
        "lines": [_line_json(item) for item in report.lines],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _flag_md(index: int, item: VoLine) -> list[str]:
    spoken = item.spoken_text or item.lyric
    block = [
        f"### {index}. {item.severity} — {item.status} — {item.shot}",
        "",
        f"**File:** `{item.file}`  ",
        f"**Line:** {item.line}  ",
        f"**Slot:** {_num(item.slot_seconds)}s ({item.slot_source or 'unknown'})  ",
        f"**Estimate:** {_num(item.estimate_seconds)}s  ",
        f"**Margin:** {_num(item.margin_seconds)}s  ",
        f"**Syllables:** {item.syllables}  ",
        f"**Spoken:** {spoken}",
        "",
    ]
    if item.note:
        block.extend([item.note, ""])
    return block


def _line_json(item: VoLine) -> dict[str, object]:
    return {
        "file": item.file,
        "line": item.line,
        "shot": item.shot,
        "time": item.time_text,
        "lyric": item.lyric,
        "spoken_text": item.spoken_text,
        "kind": item.kind,
        "start_seconds": item.start_seconds,
        "stated_end_seconds": item.stated_end_seconds,
        "slot_seconds": item.slot_seconds,
        "slot_source": item.slot_source,
        "syllables": item.syllables,
        "pause_seconds": item.pause_seconds,
        "estimate_seconds": item.estimate_seconds,
        "margin_seconds": item.margin_seconds,
        "status": item.status,
        "note": item.note,
    }


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"
