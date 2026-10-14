"""Markdown and JSON for the voice-bible comparison."""

from __future__ import annotations

import json

from continuity_checker import __version__
from continuity_checker.voice_bible import VoiceFinding, VoiceReport


def render_markdown(report: VoiceReport) -> str:
    counts = report.by_severity()
    total = len(report.findings)
    lines: list[str] = [
        "# Voice bible report",
        "",
        f"Checked **{len(report.files)}** file(s) in `{report.drafts_dir}` "
        f"against **{len(report.bible.bots)}** bot(s) in `{report.bible_path}`.",
        "",
        f"**Findings:** {total} "
        f"({counts['error']} error, {counts['warning']} warning, {counts['info']} info).",
        "",
        "## Bots",
        "",
        "| Bot | voiceId | Status | Retired |",
        "|---|---|---|---|",
    ]
    for bot in report.bible.bots:
        retired = ", ".join(bot.stale) if bot.stale else "—"
        lines.append(f"| {bot.name} | `{bot.voice_id}` | {bot.status} | {retired} |")
    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("No stale or mismatched voices in the files that were checked.")
        lines.append("")
    for index, finding in enumerate(report.findings, start=1):
        lines.extend(_finding_md(index, finding))
    clean = [name for name in report.files if not any(item.file == name for item in report.findings)]
    lines.extend(["## Files with no findings", ""])
    if clean:
        lines.extend(f"- `{name}`" for name in clean)
    else:
        lines.append("Every scanned file has at least one finding.")
    lines.append("")
    return "\n".join(lines)


def render_json(report: VoiceReport) -> str:
    counts = report.by_severity()
    payload = {
        "tool": "voice-bible-check",
        "version": __version__,
        "drafts_dir": report.drafts_dir,
        "bible": report.bible_path,
        "bots": [
            {
                "bot": bot.name,
                "voice_id": bot.voice_id,
                "status": bot.status,
                "stale_aliases": list(bot.stale),
                "line": bot.line,
            }
            for bot in report.bible.bots
        ],
        "summary": {
            "files_scanned": len(report.files),
            "files": report.files,
            "bots_loaded": len(report.bible.bots),
            "findings": len(report.findings),
            "by_severity": counts,
        },
        "findings": [_finding_json(finding) for finding in report.findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _finding_md(index: int, finding: VoiceFinding) -> list[str]:
    message = finding.message.strip()
    if message and message[-1] not in ".!?":
        message += "."
    who = finding.speaker or finding.bot or "—"
    block = [
        f"### {index}. {finding.severity} — {finding.kind.replace('_', ' ')}",
        "",
        f"**File:** `{finding.file}`  ",
        f"**Line:** {finding.line}  ",
        f"**Speaker:** {who}  ",
        f"**Voice in draft:** {finding.voice_in_draft or '—'}  ",
        f"**Locked voiceId:** {finding.locked_voice_id or '—'}  ",
        f"**Message:** {message}  ",
    ]
    if finding.snippet:
        block.append(f"**Snippet:** `{finding.snippet.replace('`', "'")}`")
    block.extend(["", "**Suggested fix:**", ""])
    for line in finding.suggested_fix.splitlines() or [""]:
        block.append(f"> {line}" if line else ">")
    block.append("")
    return block


def _finding_json(finding: VoiceFinding) -> dict[str, object]:
    return {
        "severity": finding.severity,
        "file": finding.file,
        "line": finding.line,
        "kind": finding.kind,
        "speaker": finding.speaker,
        "bot": finding.bot,
        "voice_in_draft": finding.voice_in_draft,
        "locked_voice_id": finding.locked_voice_id,
        "message": finding.message,
        "snippet": finding.snippet,
        "suggested_fix": finding.suggested_fix,
    }
