"""Command line: vo-fit <shotlist> [--rates vo_rates.yaml]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from continuity_checker import __version__
from continuity_checker.guard import GuardError, reject_output_inside_inputs
from continuity_checker.rates import RatesError, default_rates, load_rates
from continuity_checker.vo_fit import fit_path
from continuity_checker.vo_report import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vo-fit",
        description="Estimate whether each shot-list lyric fits the slot before the next shot.",
    )
    parser.add_argument("shotlist", nargs="?", help="Shot-list markdown file, or a folder of them")
    parser.add_argument("--rates", help="Rates YAML. Omit to use 4.5 syllables/s and the built-in pauses.")
    parser.add_argument("--out", default="reports/vo-fit", help="Folder for the reports, separate from the shot list")
    parser.add_argument("--md", help="Markdown report path, or - for stdout. Default: <out>/vo-fit.md")
    parser.add_argument("--json", help="JSON report path, or - for stdout. Default: <out>/vo-fit.json")
    parser.add_argument("--version", action="version", version=f"vo-fit {__version__}")
    args = parser.parse_args(argv)

    if not args.shotlist:
        parser.print_help(sys.stderr)
        print("\nerror: shotlist is required", file=sys.stderr)
        return 2

    shotlist = Path(args.shotlist)
    try:
        rates = load_rates(Path(args.rates)) if args.rates else default_rates()
    except RatesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out)
    md_path = Path(args.md) if args.md else out / "vo-fit.md"
    json_path = Path(args.json) if args.json else out / "vo-fit.json"
    try:
        reject_output_inside_inputs([shotlist], [md_path, json_path])
        report = fit_path(shotlist, rates)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    markdown = render_markdown(report)
    payload = render_json(report)
    try:
        wrote = _write_pair(md_path, markdown, json_path, payload)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counts = report.counts()
    print(
        f"{len(report.lines)} line(s), {counts.get('overrun', 0)} overrun, "
        f"{counts.get('tight', 0)} tight, {counts.get('ok', 0)} ok, {counts.get('silent', 0)} silent",
        file=sys.stderr,
    )
    for path in wrote:
        print(f"wrote {path}", file=sys.stderr)
    return 1 if counts.get("overrun", 0) or counts.get("time-order", 0) else 0


def _write_pair(md_path: Path, markdown: str, json_path: Path, payload: str) -> list[str]:
    wrote: list[str] = []
    if str(md_path) == "-":
        sys.stdout.write(markdown)
    else:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
        wrote.append(str(md_path))
    if str(json_path) == "-":
        sys.stdout.write(payload)
    else:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(payload, encoding="utf-8")
        wrote.append(str(json_path))
    return wrote


if __name__ == "__main__":
    raise SystemExit(main())
