"""Markdown tables. A table is a pipe row, a separator of dashes, then body rows."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEP_CELL = re.compile(r":?-{3,}:?")


@dataclass(frozen=True)
class MarkdownTable:
    header: tuple[str, ...]
    header_line: int
    rows: tuple[tuple[int, tuple[str, ...]], ...]


def parse_tables(text: str) -> list[MarkdownTable]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    tables: list[MarkdownTable] = []
    index = 0
    while index < len(lines):
        if _is_row(lines[index]) and index + 1 < len(lines) and _is_separator(lines[index + 1]):
            header = _cells(lines[index])
            width = len(header)
            rows: list[tuple[int, tuple[str, ...]]] = []
            cursor = index + 2
            while cursor < len(lines) and _is_row(lines[cursor]) and not _is_separator(lines[cursor]):
                rows.append((cursor + 1, _pad(_cells(lines[cursor]), width)))
                cursor += 1
            tables.append(MarkdownTable(header=header, header_line=index + 1, rows=tuple(rows)))
            index = cursor
            continue
        index += 1
    return tables


def _is_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_separator(line: str) -> bool:
    if not _is_row(line):
        return False
    cells = [cell.strip() for cell in _cells(line)]
    filled = [cell for cell in cells if cell]
    return bool(filled) and all(_SEP_CELL.fullmatch(cell) for cell in filled)


def _cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return tuple(cell.strip() for cell in stripped.split("|"))


def _pad(cells: tuple[str, ...], width: int) -> tuple[str, ...]:
    if len(cells) >= width:
        return cells[:width]
    return cells + ("",) * (width - len(cells))
