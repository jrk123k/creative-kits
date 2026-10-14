"""Apply rules to a directory of drafts."""

from __future__ import annotations

import re
from pathlib import Path

from continuity_checker.globmatch import glob_match
from continuity_checker.models import CheckResult, Finding, Region, Rule
from continuity_checker.prompts import find_prompt_regions

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text"}
NEGATION_WINDOW = 60
# Letters and digits count as word characters. Underscores and punctuation do not,
# so `_london_old` still matches the term london_old, and unlit does not match lit.
BOUNDARY = r"[^\W_]"
NEGATION_RE = re.compile(
    rf"(?i)(?<!{BOUNDARY})("
    r"no|not|never|without|avoid(?:ing)?|"
    r"forbidden|forbid|ban(?:ned|ning)?|"
    r"don'?t|do not|must not|cannot|can'?t|"
    r"prohibited|negative|minus"
    rf")(?!{BOUNDARY})"
)
NEGATIVE_HEADING_RE = re.compile(
    r"(?i)\b(?:negatives?|avoid|anti-looks?|do-?nots?|never use|don'?t use)\b"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SNIPPET_LIMIT = 320


def check(drafts_dir: Path, rules: list[Rule], rules_file: Path | None = None) -> CheckResult:
    root = drafts_dir.expanduser().resolve()
    result = CheckResult(
        drafts_dir=str(drafts_dir),
        rules_file=str(rules_file) if rules_file else "",
        rules_loaded=len(rules),
    )
    files = list(_iter_drafts(root))
    result.files = [path.relative_to(root).as_posix() for path in files]
    compiled = [_CompiledRule.build(rule) for rule in rules]
    ancestors = _ancestor_names(root)
    findings: list[Finding] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(_encoding_finding(rel))
            continue
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        findings.extend(_check_text(rel, text, compiled, ancestors))
    findings = _dedupe(findings)
    findings.sort(key=lambda finding: finding.sort_key())
    result.findings = findings
    return result


def _iter_drafts(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        found.append(path)
    found.sort()
    return found


def _ancestor_names(root: Path) -> tuple[str, ...]:
    names: list[str] = []
    current = root
    for _ in range(8):
        if current.name:
            names.append(current.name)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return tuple(names)


def _check_text(
    rel: str,
    text: str,
    rules: list[_CompiledRule],
    ancestors: tuple[str, ...] = (),
) -> list[Finding]:
    lines = text.splitlines()
    headings = _headings(lines)
    prompts = find_prompt_regions(lines)
    applicable = [
        rule for rule in rules if rule.rule.scope.matches(rel, glob_match, ancestors)
    ]
    findings: list[Finding] = []
    for rule in applicable:
        if rule.rule.type == "required_verbatim":
            findings.extend(_verbatim(rel, text, lines, prompts, rule))
        else:
            findings.extend(_matches(rel, text, lines, headings, prompts, rule))
    return findings


def _verbatim(
    rel: str,
    text: str,
    lines: list[str],
    prompts: list[Region],
    compiled: _CompiledRule,
) -> list[Finding]:
    rule = compiled.rule
    regions = prompts if rule.where == "prompt" else [Region(1, max(len(lines), 1), text, "file")]
    locked = _norm(rule.text)
    findings: list[Finding] = []
    for region in regions:
        if locked and locked in _norm(region.text):
            continue
        match = compiled.name_re.search(region.text) if compiled.name_re else None
        if not match:
            continue
        line_no, line_text, _start, _end = _locate(region, match.start(), match.end())
        findings.append(
            _finding(
                rule,
                rel,
                line_no,
                line_text,
                message=rule.message
                or f"{rule.name} is named in this prompt, but the locked description is not there word for word.",
                fix=_verbatim_fix(rule),
                focus=match.group(0),
            )
        )
    return findings


def _matches(
    rel: str,
    text: str,
    lines: list[str],
    headings: list[str],
    prompts: list[Region],
    compiled: _CompiledRule,
) -> list[Finding]:
    rule = compiled.rule
    if compiled.pattern_re is None:
        return []
    regions = prompts if rule.where == "prompt" else [Region(1, max(len(lines), 1), text, "file")]
    findings: list[Finding] = []
    for region in regions:
        for match in compiled.pattern_re.finditer(region.text):
            if not match.group(0):
                continue
            line_no, line_text, start, end = _locate(region, match.start(), match.end())
            if rule.honor_negative_headings and line_no - 1 < len(headings):
                if NEGATIVE_HEADING_RE.search(headings[line_no - 1]):
                    continue
            if compiled.ignore_line_re and compiled.ignore_line_re.search(line_text):
                continue
            if compiled.unless_re and compiled.unless_re.search(line_text):
                continue
            if rule.ignore_negated and _negated(line_text, start, end):
                continue
            matched = match.group(0)
            findings.append(
                _finding(
                    rule,
                    rel,
                    line_no,
                    line_text,
                    message=_match_message(rule, matched),
                    fix=_match_fix(rule, matched),
                    focus=matched,
                )
            )
    return findings


def _verbatim_fix(rule: Rule) -> str:
    fix = rule.suggested_fix or f"Paste the locked {rule.name} description word for word before the scene."
    fix = _fill(fix, rule, "")
    if rule.text and rule.text not in fix:
        fix = fix.rstrip() + "\n\n" + rule.text
    return fix


def _encoding_finding(rel: str) -> Finding:
    return Finding(
        severity="error",
        file=rel,
        line=1,
        rule_id="file-encoding",
        rule_type="custom",
        title="File is not UTF-8",
        message="This draft is not valid UTF-8, so the rules were not applied to it.",
        snippet="",
        suggested_fix="Save the file as UTF-8 and run the checker again.",
    )


def _match_message(rule: Rule, matched: str) -> str:
    if rule.message:
        return _fill(rule.message, rule, matched)
    if rule.type == "name_spelling":
        return f"Spelling {matched!r} is not the locked form {rule.canonical!r}."
    if rule.type == "term_lock":
        return f"Locked term is {rule.prefer!r}, not {matched!r}."
    if rule.type == "forbidden_in_context":
        return f"{matched!r} is not allowed in this context."
    if rule.title:
        return f"{rule.title}. Matched {matched!r}."
    return f"Custom pattern matched {matched!r}."


def _match_fix(rule: Rule, matched: str) -> str:
    if rule.suggested_fix:
        return _fill(rule.suggested_fix, rule, matched)
    if rule.type == "name_spelling":
        return f"Replace {matched!r} with {rule.canonical!r}."
    if rule.type == "term_lock":
        return f"Replace {matched!r} with {rule.prefer!r}."
    if rule.type == "forbidden_in_context":
        return f"Remove {matched!r}."
    return "Edit this line so it matches the lock."


def _fill(template: str, rule: Rule, matched: str) -> str:
    values = {
        "matched": matched,
        "name": rule.name,
        "text": rule.text,
        "prefer": rule.prefer,
        "canonical": rule.canonical,
        "id": rule.id,
    }
    filled = template
    for key, value in values.items():
        filled = filled.replace("{" + key + "}", value)
    return filled


def _finding(
    rule: Rule,
    rel: str,
    line_no: int,
    line_text: str,
    message: str,
    fix: str,
    focus: str,
) -> Finding:
    return Finding(
        severity=rule.severity,
        file=rel,
        line=line_no,
        rule_id=rule.id,
        rule_type=rule.type,
        title=rule.title,
        message=message,
        snippet=_snippet(line_text, focus),
        suggested_fix=fix,
        source=rule.source,
    )


def _snippet(line_text: str, focus: str) -> str:
    text = re.sub(r"\s+", " ", line_text).strip()
    if len(text) <= SNIPPET_LIMIT:
        return text
    lowered = text.lower()
    at = lowered.find(focus.lower()) if focus else -1
    if at < 0:
        return text[: SNIPPET_LIMIT - 3].rstrip() + "..."
    window = SNIPPET_LIMIT - 3
    begin = max(0, at - window // 3)
    end = min(len(text), begin + window)
    begin = max(0, end - window)
    piece = text[begin:end].strip()
    if begin > 0:
        piece = "..." + piece
    if end < len(text):
        piece = piece + "..."
    return piece


def _negated(line: str, start: int, end: int) -> bool:
    left = max(0, start - NEGATION_WINDOW)
    right = min(len(line), end + NEGATION_WINDOW)
    return NEGATION_RE.search(line[left:right]) is not None


def _locate(region: Region, start: int, end: int) -> tuple[int, str, int, int]:
    line_offset = region.text.count("\n", 0, start)
    line_begin = region.text.rfind("\n", 0, start) + 1
    line_end = region.text.find("\n", start)
    if line_end < 0:
        line_end = len(region.text)
    return (
        region.start_line + line_offset,
        region.text[line_begin:line_end],
        start - line_begin,
        end - line_begin,
    )


def _headings(lines: list[str]) -> list[str]:
    current = ""
    found: list[str] = []
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            current = match.group(2)
        found.append(current)
    return found


def _norm(text: str) -> str:
    """Word-for-word compare that still tolerates markdown bold and wrapped lines."""
    without_bold = text.replace("*", "")
    return re.sub(r"\s+", " ", without_bold).strip()


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.file, finding.line, finding.rule_id, finding.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _boundary(term: str) -> str:
    return rf"(?<!{BOUNDARY}){re.escape(term)}(?!{BOUNDARY})"


class _CompiledRule:
    def __init__(self, rule: Rule, name_re, pattern_re, ignore_line_re, unless_re):
        self.rule = rule
        self.name_re = name_re
        self.pattern_re = pattern_re
        self.ignore_line_re = ignore_line_re
        self.unless_re = unless_re

    @classmethod
    def build(cls, rule: Rule) -> _CompiledRule:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        name_re = None
        if rule.type == "required_verbatim":
            names = sorted({rule.name, *rule.aliases}, key=len, reverse=True)
            name_re = re.compile("|".join(_boundary(name) for name in names), flags)
        pattern_re = None
        if rule.type in {"forbidden_in_context", "name_spelling", "term_lock"}:
            terms = sorted(set(rule.terms), key=len, reverse=True)
            pattern_re = re.compile("|".join(_boundary(term) for term in terms), flags)
        elif rule.type == "custom":
            pattern_re = re.compile(rule.pattern)
        ignore_line_re = re.compile(rule.ignore_line_pattern) if rule.ignore_line_pattern else None
        unless_re = re.compile(rule.unless_pattern) if rule.unless_pattern else None
        return cls(rule, name_re, pattern_re, ignore_line_re, unless_re)
