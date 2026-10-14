"""Voice bible checks against the fictional crew sample."""

from __future__ import annotations

import json
from pathlib import Path

from continuity_checker.voice_bible import check_drafts, check_text, load_bible
from continuity_checker.voice_bible_cli import main
from continuity_checker.voice_report import render_json, render_markdown

ROOT = Path(__file__).resolve().parents[1]
BIBLE = ROOT / "samples" / "crew-voice-bible" / "VOICE_BIBLE.md"
OLD_BIBLE = ROOT / "examples" / "sources" / "projects" / "crew-voice-bible" / "VOICE_BIBLE.md"
DRAFTS = ROOT / "samples" / "drafts"


def _kinds(findings):
    return [(finding.kind, finding.speaker, finding.voice_in_draft) for finding in findings]


def test_bible_parses_locked_proposed_and_retired_ids():
    bible = load_bible(BIBLE)
    by_name = {bot.name: bot for bot in bible.bots}
    assert set(by_name) == {
        "Harbor",
        "Ledger",
        "Quill",
        "Lens",
        "Stack",
        "Index",
        "Signal",
        "Ember",
    }
    assert by_name["Ledger"].voice_id == "ara"
    assert "carina" in by_name["Ledger"].stale
    assert by_name["Stack"].stale == ("sirius",)
    assert by_name["Quill"].stale == ("lumen",)
    assert by_name["Lens"].stale == ("altair",)
    assert by_name["Harbor"].status == "locked"
    assert by_name["Ember"].voice_id == "ursa"
    assert by_name["Ember"].status == "proposed"
    assert by_name["Signal"].voice_id == "vega"
    older = load_bible(OLD_BIBLE)
    assert "Ember" not in {bot.name for bot in older.bots}
    assert "carina" in {item for bot in older.bots for item in bot.stale}


def test_ledger_as_carina_is_a_stale_alias():
    bible = load_bible(BIBLE)
    text = "This draft still lists Ledger as 'carina'.\nLedger=ara.\n"
    findings = check_text(text, "IDEA.md", bible)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.kind == "stale_alias"
    assert finding.bot == "Ledger"
    assert finding.voice_in_draft == "carina"
    assert finding.locked_voice_id == "ara"


def test_mismatch_proposed_and_stale():
    bible = load_bible(BIBLE)
    text = "\n".join(
        [
            "Harbor=ara.",
            "changed from carina.",
            "Ledger carina -> ara.",
            "Ember=ursa.",
            "Quill=lumen.",
            "Stack (tools) meets Harbor.",
            "Signal overload on the costume.",
        ]
    )
    findings = check_text(text, "notes.md", bible)
    kinds = _kinds(findings)
    assert ("mismatch", "Harbor", "ara") in kinds
    assert ("stale_alias", "Quill", "lumen") in kinds
    assert ("proposed", "Ember", "ursa") in kinds


def test_sample_drafts_cli(tmp_path):
    md = tmp_path / "vb.md"
    js = tmp_path / "vb.json"
    code = main(
        [
            str(DRAFTS),
            "--bible",
            str(BIBLE),
            "--md",
            str(md),
            "--json",
            str(js),
        ]
    )
    assert code in (0, 1)
    assert md.exists() and js.exists()
    data = json.loads(js.read_text(encoding="utf-8"))
    assert "findings" in data
    bible = load_bible(BIBLE)
    result = check_drafts(DRAFTS, bible)
    assert render_markdown(result)
    assert render_json(result)
