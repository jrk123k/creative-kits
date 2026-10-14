"""Data the checker passes between loading, scanning, and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
SEVERITIES = tuple(SEVERITY_ORDER)


@dataclass(frozen=True)
class Region:
    """A slice of a draft. Line numbers are 1-based and inclusive."""

    start_line: int
    end_line: int
    text: str
    kind: str


@dataclass(frozen=True)
class Scope:
    projects: tuple[str, ...] = ()
    globs: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def matches(self, rel: str, glob_match, extra_parts: tuple[str, ...] = ()) -> bool:
        """Project scope matches a folder name on the file path or above the drafts root.

        That way a rule for ``harbor-waltz`` still applies if a caller points the
        checker at the project folder itself, not only at a parent that contains it.
        """
        rel = rel.replace("\\", "/")
        if self.exclude and any(glob_match(rel, pattern) for pattern in self.exclude):
            return False
        if self.projects:
            parts = {part.lower() for part in rel.split("/") if part}
            parts.update(part.lower() for part in extra_parts if part)
            if not any(project.lower() in parts for project in self.projects):
                return False
        if self.globs and not any(glob_match(rel, pattern) for pattern in self.globs):
            return False
        return True


@dataclass(frozen=True)
class Rule:
    id: str
    type: str
    severity: str
    title: str
    scope: Scope
    suggested_fix: str
    message: str
    source: str
    name: str = ""
    aliases: tuple[str, ...] = ()
    text: str = ""
    terms: tuple[str, ...] = ()
    prefer: str = ""
    canonical: str = ""
    pattern: str = ""
    case_sensitive: bool = False
    ignore_negated: bool = True
    honor_negative_headings: bool = True
    where: str = "anywhere"
    ignore_line_pattern: str = ""
    unless_pattern: str = ""


@dataclass(frozen=True)
class Finding:
    severity: str
    file: str
    line: int
    rule_id: str
    rule_type: str
    title: str
    message: str
    snippet: str
    suggested_fix: str
    source: str = ""

    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER[self.severity], self.file, self.line, self.rule_id)


@dataclass
class CheckResult:
    drafts_dir: str
    rules_file: str
    rules_loaded: int
    files: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def by_severity(self) -> dict[str, int]:
        counts = {name: 0 for name in SEVERITIES}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts
