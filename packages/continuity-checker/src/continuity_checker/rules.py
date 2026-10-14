"""Load the YAML rules file. Unknown keys are errors, so a typo does not silently do nothing."""

from __future__ import annotations

from pathlib import Path

import yaml

from continuity_checker.models import SEVERITIES, Rule, Scope

RULE_TYPES = {
    "required_verbatim": "required_verbatim",
    "forbidden_in_context": "forbidden_in_context",
    "name_spelling": "name_spelling",
    "term_lock": "term_lock",
    "custom": "custom",
    "custom_regex": "custom",
    "regex": "custom",
}

TOP_LEVEL_KEYS = {"version", "descriptions", "rules"}
RULE_KEYS = {
    "id",
    "type",
    "severity",
    "title",
    "scope",
    "suggested_fix",
    "suggest",
    "message",
    "source",
    "note",
    "name",
    "aliases",
    "text",
    "terms",
    "prefer",
    "reject",
    "canonical",
    "misspellings",
    "pattern",
    "case_sensitive",
    "ignore_negated",
    "honor_negative_headings",
    "where",
    "in",
    "ignore_line_pattern",
    "unless_pattern",
}
SCOPE_KEYS = {"projects", "globs", "exclude"}


class RuleError(Exception):
    """The rules file is unreadable or a rule is incomplete."""


def load_rules(path: Path) -> list[Rule]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleError(f"{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuleError(f"{path}: the file must be a mapping with a 'rules' list")
    unknown = set(raw) - TOP_LEVEL_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise RuleError(f"{path}: unknown top-level key(s): {names}")
    version = raw.get("version", 1)
    if version != 1:
        raise RuleError(f"{path}: unsupported version {version!r} (this checker reads version 1)")
    items = raw.get("rules")
    if not isinstance(items, list):
        raise RuleError(f"{path}: 'rules' must be a list")

    rules: list[Rule] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        rule = _parse_rule(path, index, item)
        if rule.id in seen:
            raise RuleError(f"{path}: duplicate rule id {rule.id!r}")
        seen.add(rule.id)
        rules.append(rule)
    return rules


def _parse_rule(path: Path, index: int, item: object) -> Rule:
    where = f"{path}: rule #{index}"
    if not isinstance(item, dict):
        raise RuleError(f"{where} must be a mapping")
    rule_id = item.get("id")
    if isinstance(rule_id, str) and rule_id.strip():
        where = f"{path}: rule {rule_id.strip()!r}"
    else:
        raise RuleError(f"{where} is missing a string id")
    unknown = set(item) - RULE_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise RuleError(f"{where} has unknown key(s): {names}")

    raw_type = item.get("type")
    if not isinstance(raw_type, str) or raw_type.strip() not in RULE_TYPES:
        known = ", ".join(sorted({key for key in RULE_TYPES if key != "regex" and key != "custom_regex"}))
        raise RuleError(f"{where} has unknown type {raw_type!r}. Use one of: {known}")
    rule_type = RULE_TYPES[raw_type.strip()]

    severity = str(item.get("severity", "error")).strip().lower()
    if severity not in SEVERITIES:
        raise RuleError(f"{where} severity must be error, warning, or info")

    title = _optional_str(item.get("title"), where, "title") or rule_id.strip()
    message = _optional_str(item.get("message"), where, "message")
    source = _optional_str(item.get("source"), where, "source")
    suggested = item.get("suggested_fix", item.get("suggest", ""))
    suggested_fix = _optional_str(suggested, where, "suggested_fix")
    scope = _parse_scope(item.get("scope"), where)
    where_value = item.get("where", item.get("in", None))
    location = _optional_str(where_value, where, "where") if where_value is not None else ""

    name = _optional_str(item.get("name"), where, "name")
    aliases = tuple(_str_list(item.get("aliases"), where, "aliases"))
    text = _optional_str(item.get("text"), where, "text")
    prefer = _optional_str(item.get("prefer"), where, "prefer")
    canonical = _optional_str(item.get("canonical"), where, "canonical")
    pattern = _optional_str(item.get("pattern"), where, "pattern")
    ignore_line_pattern = _optional_str(item.get("ignore_line_pattern"), where, "ignore_line_pattern")
    unless_pattern = _optional_str(item.get("unless_pattern"), where, "unless_pattern")

    if rule_type == "required_verbatim":
        if not name:
            raise RuleError(f"{where} (required_verbatim) needs 'name'")
        if not text:
            raise RuleError(f"{where} (required_verbatim) needs 'text'")
        terms: tuple[str, ...] = ()
        location = location or "prompt"
    elif rule_type == "forbidden_in_context":
        terms = tuple(_str_list(item.get("terms"), where, "terms", required=True))
        location = location or "anywhere"
    elif rule_type == "name_spelling":
        if not canonical:
            raise RuleError(f"{where} (name_spelling) needs 'canonical'")
        terms = tuple(_str_list(item.get("misspellings"), where, "misspellings", required=True))
        location = location or "anywhere"
    elif rule_type == "term_lock":
        if not prefer:
            raise RuleError(f"{where} (term_lock) needs 'prefer'")
        terms = tuple(_str_list(item.get("reject"), where, "reject", required=True))
        location = location or "anywhere"
    else:
        if not pattern:
            raise RuleError(f"{where} (custom) needs 'pattern'")
        _compile_user_pattern(pattern, where, "pattern")
        terms = ()
        location = location or "anywhere"

    if location not in {"prompt", "file", "anywhere"}:
        raise RuleError(f"{where} where must be prompt, file, or anywhere")
    if ignore_line_pattern:
        _compile_user_pattern(ignore_line_pattern, where, "ignore_line_pattern")
    if unless_pattern:
        _compile_user_pattern(unless_pattern, where, "unless_pattern")

    case_sensitive = bool(item.get("case_sensitive", False))
    ignore_negated = bool(item.get("ignore_negated", True))
    honor_negative = bool(item.get("honor_negative_headings", True))
    if rule_type == "required_verbatim":
        ignore_negated = False
        honor_negative = False

    return Rule(
        id=rule_id.strip(),
        type=rule_type,
        severity=severity,
        title=title,
        scope=scope,
        suggested_fix=suggested_fix,
        message=message,
        source=source,
        name=name,
        aliases=aliases,
        text=text,
        terms=terms,
        prefer=prefer,
        canonical=canonical,
        pattern=pattern,
        case_sensitive=case_sensitive,
        ignore_negated=ignore_negated,
        honor_negative_headings=honor_negative,
        where=location,
        ignore_line_pattern=ignore_line_pattern,
        unless_pattern=unless_pattern,
    )


def _parse_scope(raw: object, where: str) -> Scope:
    if raw is None:
        return Scope()
    if isinstance(raw, str):
        return Scope(globs=(raw,))
    if isinstance(raw, list):
        return Scope(globs=tuple(_str_list(raw, where, "scope")))
    if not isinstance(raw, dict):
        raise RuleError(f"{where}: scope must be a glob, a list of globs, or a mapping")
    unknown = set(raw) - SCOPE_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise RuleError(f"{where}: unknown scope key(s): {names}")
    return Scope(
        projects=tuple(_str_list(raw.get("projects"), where, "scope.projects")),
        globs=tuple(_str_list(raw.get("globs"), where, "scope.globs")),
        exclude=tuple(_str_list(raw.get("exclude"), where, "scope.exclude")),
    )


def _optional_str(value: object, where: str, field: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    raise RuleError(
        f"{where}: {field} must be a string. If YAML ate a word like yes, no, on, or off, quote it."
    )


def _str_list(value: object, where: str, field: str, required: bool = False) -> list[str]:
    if value is None:
        if required:
            raise RuleError(f"{where}: {field} is required")
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise RuleError(
            f"{where}: {field} must be a string or a list of strings. "
            "Quote words YAML treats as booleans (yes, no, on, off)."
        )
    if required and not value:
        raise RuleError(f"{where}: {field} needs at least one entry")
    return [item.strip() for item in value]


def _compile_user_pattern(pattern: str, where: str, field: str) -> None:
    import re

    try:
        re.compile(pattern)
    except re.error as exc:
        raise RuleError(f"{where}: {field} is not a valid regex ({exc})") from exc
