"""Command line: voice-bible-check <drafts_dir> --bible VOICE_BIBLE.md"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from continuity_checker import __version__
from continuity_checker.guard import GuardError, reject_output_inside_inputs
from continuity_checker.voice_bible import BibleError, check_drafts, load_bible
from continuity_checker.voice_report import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="voice-bible-check",
        description="Flag draft voices that disagree with VOICE_BIBLE.md.",
    )
    parser.add_argument("drafts_dir", nargs="?", help="Folder of drafts, or one draft file")
    parser.add_argument("--bible", help="Path to VOICE_BIBLE.md")
    parser.add_argument(
        "--out",
        default="reports/voice-bible",
        help="Folder for the reports, separate from the drafts and the bible",
    )
    parser.add_argument("--md", help="Markdown report path, or - for stdout. Default: <out>/voice-bible.md")
    parser.add_argument("--json", help="JSON report path, or - for stdout. Default: <out>/voice-bible.json")
    parser.add_argument("--version", action="version", version=f"voice-bible-check {__version__}")
    args = parser.parse_args(argv)

    if not args.drafts_dir or not args.bible:
        parser.print_help(sys.stderr)
        print("\nerror: drafts_dir and --bible are required", file=sys.stderr)
        return 2

    drafts = Path(args.drafts_dir)
    bible_path = Path(args.bible)
    if not drafts.exists():
        print(f"error: drafts not found: {drafts}", file=sys.stderr)
        return 2
    if not bible_path.is_file():
        print(f"error: voice bible not found: {bible_path}", file=sys.stderr)
        return 2

    out = Path(args.out)
    md_path = Path(args.md) if args.md else out / "voice-bible.md"
    json_path = Path(args.json) if args.json else out / "voice-bible.json"
    try:
        reject_output_inside_inputs([drafts, bible_path], [md_path, json_path])
        bible = load_bible(bible_path)
        report = check_drafts(drafts, bible)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BibleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    markdown = render_markdown(report)
    payload = render_json(report)
    wrote: list[str] = []
    try:
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
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counts = report.by_severity()
    print(
        f"{len(report.files)} file(s), {len(report.findings)} finding(s) "
        f"({counts['error']} error, {counts['warning']} warning, {counts['info']} info)",
        file=sys.stderr,
    )
    for path in wrote:
        print(f"wrote {path}", file=sys.stderr)
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
