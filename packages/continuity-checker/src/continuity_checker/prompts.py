"""Find the regions of a draft that count as prompts.

A prompt is one of:

* the paragraph under a line that starts with ``Prompt:``
* the body of a heading that is itself a prompt (``Primary prompt``,
  ``Imagine-ready``, a heading that says ``paste``)
* a markdown table cell whose column header contains ``prompt``
"""

from __future__ import annotations

import re

from continuity_checker.models import Region

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
# The heading must *be* a prompt, not merely mention the word in passing
# ("append to every clip prompt" is instructions about prompts).
HEADING_PROMPT_RE = re.compile(
    r"(?i)^(?:\d+[.)]\s*)?(?:(?:primary|image|visual|final)\s+)?prompts?\b"
    r"|\bimagine-ready\b"
    r"|\bpaste\b"
)
PROMPT_LINE_RE = re.compile(
    r"(?i)^\s*(?:\*\*)?(?:(?:primary|image|visual)\s+)?prompt\b[^:\n]*:\s*(.*)$"
)


def find_prompt_regions(lines: list[str]) -> list[Region]:
    regions: list[Region] = []
    index = 0
    count = len(lines)
    while index < count:
        heading = HEADING_RE.match(lines[index])
        if heading and HEADING_PROMPT_RE.search(heading.group(2)):
            start = index
            index += 1
            while index < count and not HEADING_RE.match(lines[index]):
                index += 1
            regions.append(
                Region(start + 1, index, "\n".join(lines[start:index]), "section")
            )
            continue
        labeled = PROMPT_LINE_RE.match(lines[index])
        if labeled:
            start = index
            chunks: list[str] = []
            inline = labeled.group(1).strip()
            if inline:
                chunks.append(inline)
            index += 1
            while index < count and lines[index].strip() and not HEADING_RE.match(lines[index]):
                chunks.append(lines[index])
                index += 1
            if not chunks:
                continue
            content_line = start if inline else start + 1
            regions.append(
                Region(content_line + 1, index, "\n".join(chunks), "paragraph")
            )
            continue
        index += 1
    regions.extend(_table_prompt_cells(lines))
    return regions


def _table_prompt_cells(lines: list[str]) -> list[Region]:
    regions: list[Region] = []
    index = 0
    while index < len(lines) - 1:
        if _is_table_row(lines[index]) and _is_separator(lines[index + 1]):
            headers = _split_row(lines[index])
            prompt_columns = [
                column for column, header in enumerate(headers) if re.search(r"(?i)prompt", header)
            ]
            index += 2
            while index < len(lines) and _is_table_row(lines[index]):
                if prompt_columns:
                    cells = _split_row(lines[index])
                    for column in prompt_columns:
                        if column < len(cells) and cells[column].strip():
                            regions.append(
                                Region(index + 1, index + 1, cells[column].strip(), "table-cell")
                            )
                index += 1
            continue
        index += 1
    return regions


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped.startswith("|") and "-" in stripped and re.fullmatch(r"[|\-:\s]+", stripped))


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]
