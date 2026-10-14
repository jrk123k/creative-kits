"""Command line: continuity-check <drafts_dir> --rules rules.yaml"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from continuity_checker import __version__
from continuity_checker.engine import check
from continuity_checker.report import render_json, render_markdown
from continuity_checker.rules import RuleError, load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="continuity-check",
        description="Check drafts against continuity rules.",
    )
    parser.add_argument("drafts_dir", nargs="?", help="Folder of scripts, prompts, and shot lists")
    parser.add_argument("--rules", required=False, help="Path to rules.yaml")
    parser.add_argument("--md", default="continuity-report.md", help="Markdown report path, or - for stdout")
    parser.add_argument("--json", default="continuity-report.json", help="JSON report path, or - for stdout")
    parser.add_argument("--version", action="version", version=f"continuity-check {__version__}")
    args = parser.parse_args(argv)

    if not args.drafts_dir or not args.rules:
        parser.print_help(sys.stderr)
        print("\nerror: drafts_dir and --rules are required", file=sys.stderr)
        return 2

    drafts_dir = Path(args.drafts_dir)
    rules_path = Path(args.rules)
    if not drafts_dir.is_dir():
        print(f"error: drafts folder not found: {drafts_dir}", file=sys.stderr)
        return 2
    if not rules_path.is_file():
        print(f"error: rules file not found: {rules_path}", file=sys.stderr)
        return 2
    try:
        rules = load_rules(rules_path)
    except RuleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = check(drafts_dir, rules, rules_path)
    markdown = render_markdown(result)
    payload = render_json(result)
    wrote: list[str] = []
    if args.md == "-":
        sys.stdout.write(markdown)
    else:
        Path(args.md).write_text(markdown, encoding="utf-8")
        wrote.append(str(Path(args.md)))
    if args.json == "-":
        sys.stdout.write(payload)
    else:
        Path(args.json).write_text(payload, encoding="utf-8")
        wrote.append(str(Path(args.json)))

    counts = result.by_severity()
    print(
        f"{len(result.files)} file(s), {len(result.findings)} finding(s) "
        f"({counts['error']} error, {counts['warning']} warning, {counts['info']} info)",
        file=sys.stderr,
    )
    for path in wrote:
        print(f"wrote {path}", file=sys.stderr)
    return 1 if counts["error"] else 0
