"""Markdown and JSON reports. Field names stay stable so callers can script around the JSON."""

from __future__ import annotations

import json
from collections import Counter

from continuity_checker import __version__
from continuity_checker.models import SEVERITIES, CheckResult, Finding


def render_markdown(result: CheckResult) -> str:
    counts = result.by_severity()
    total = len(result.findings)
    by_rule = _by_rule(result)
    lines: list[str] = [
        "# Continuity report",
        "",
        f"Checked **{len(result.files)}** file(s) in `{result.drafts_dir}` "
        f"against **{result.rules_loaded}** rule(s) in `{result.rules_file}`.",
        "",
        f"**Findings:** {total} "
        f"({counts['error']} error, {counts['warning']} warning, {counts['info']} info).",
        "",
        "| Severity | Findings |",
        "|---|---|",
    ]
    for severity in SEVERITIES:
        lines.append(f"| {severity} | {counts[severity]} |")
    lines.extend(["", "## By rule", "", "| Severity | Rule | Findings | Title |", "|---|---|---|---|"])
    if by_rule:
        for rule_id, severity, title, count in by_rule:
            safe_title = title.replace("|", "/").replace("\n", " ")
            lines.append(f"| {severity} | `{rule_id}` | {count} | {safe_title} |")
    else:
        lines.append("| — | — | 0 | No findings. |")
    lines.extend(["", "## Findings", ""])
    if not result.findings:
        lines.append("No continuity breaks in the files that were checked.")
        lines.append("")
    for index, finding in enumerate(result.findings, start=1):
        lines.extend(_finding_md(index, finding))
    clean = [name for name in result.files if not any(item.file == name for item in result.findings)]
    lines.extend(["## Files with no findings", ""])
    if clean:
        lines.extend(f"- `{name}`" for name in clean)
    else:
        lines.append("Every scanned file has at least one finding.")
    lines.append("")
    return "\n".join(lines)


def render_json(result: CheckResult) -> str:
    counts = result.by_severity()
    payload = {
        "tool": "continuity-check",
        "version": __version__,
        "drafts_dir": result.drafts_dir,
        "rules_file": result.rules_file,
        "summary": {
            "files_scanned": len(result.files),
            "files": result.files,
            "rules_loaded": result.rules_loaded,
            "findings": len(result.findings),
            "by_severity": counts,
            "by_rule": [
                {"rule_id": rule_id, "severity": severity, "title": title, "count": count}
                for rule_id, severity, title, count in _by_rule(result)
            ],
        },
        "findings": [_finding_json(finding) for finding in result.findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _by_rule(result: CheckResult) -> list[tuple[str, str, str, int]]:
    counter: Counter[str] = Counter()
    meta: dict[str, tuple[str, str]] = {}
    for finding in result.findings:
        counter[finding.rule_id] += 1
        meta[finding.rule_id] = (finding.severity, finding.title)
    rows = [
        (rule_id, meta[rule_id][0], meta[rule_id][1], counter[rule_id]) for rule_id in counter
    ]
    rows.sort(key=lambda row: (SEVERITIES.index(row[1]), -row[3], row[0]))
    return rows


def _finding_md(index: int, finding: Finding) -> list[str]:
    message = finding.message.strip()
    if message and message[-1] not in ".!?":
        message += "."
    source = f" Source: {finding.source}." if finding.source else ""
    block = [
        f"### {index}. {finding.severity} — {finding.title}",
        "",
        f"**File:** `{finding.file}`  ",
        f"**Line:** {finding.line}  ",
        f"**Rule:** `{finding.rule_id}` ({finding.rule_type})  ",
        f"**Message:** {message}{source}  ",
        f"**Snippet:** `{_code(finding.snippet)}`",
        "",
        "**Suggested fix:**",
        "",
    ]
    for line in finding.suggested_fix.splitlines() or [""]:
        block.append(f"> {line}" if line else ">")
    block.append("")
    return block


def _finding_json(finding: Finding) -> dict[str, object]:
    payload: dict[str, object] = {
        "severity": finding.severity,
        "file": finding.file,
        "line": finding.line,
        "rule": finding.rule_id,
        "rule_type": finding.rule_type,
        "title": finding.title,
        "message": finding.message,
        "snippet": finding.snippet,
        "suggested_fix": finding.suggested_fix,
    }
    if finding.source:
        payload["source"] = finding.source
    return payload


def _code(text: str) -> str:
    return text.replace("`", "'")
