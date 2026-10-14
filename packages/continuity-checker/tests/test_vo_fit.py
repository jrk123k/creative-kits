"""Voiceover fit: syllables, pauses, slots from the next shot, and the sample shot list."""

from __future__ import annotations

import json
from pathlib import Path

from continuity_checker.rates import RatesError, default_rates, load_rates
from continuity_checker.syllables import count_syllables, pause_seconds, syllables_in_word
from continuity_checker.vo_fit import fit_path, fit_text
from continuity_checker.vo_fit_cli import main
from continuity_checker.vo_report import render_json, render_markdown

ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "samples" / "harbor-waltz" / "SHOTLIST_v2.md"
RATES = ROOT / "vo_rates.yaml"


def test_syllables_for_lyric_words():
    expected = {
        "buckle": 2,
        "morning": 2,
        "pulling": 2,
        "dough": 1,
        "the": 1,
        "technicolor": 4,
        "simoleons": 4,
        "roses": 2,
        "floral": 2,
        "baby's": 2,
        "eyes": 1,
        "ignored": 2,
        "watching": 2,
        "gizzard": 2,
        "skidoo": 2,
        "didn't": 2,
        "don't": 1,
        "little": 2,
        "pavement": 2,
        "shoe": 1,
        "prize": 1,
        "certain": 2,
        "tumble": 2,
        "header": 2,
        "fire": 1,
        "bought": 1,
        "stacking": 2,
        "sweetie": 2,
        "fate's": 1,
        "it's": 1,
        "I'm": 1,
        "people": 2,
    }
    for word, count in expected.items():
        assert syllables_in_word(word) == count, word
    assert count_syllables("I buckle down all morning, pulling shifts for the dough.") == 13
    assert count_syllables("One kick to the gizzard, and she told me to skidoo.") == 13
    assert count_syllables("To see the technicolor fire in my baby's eyes.") == 13


def test_pauses_ignore_hyphens_and_count_ellipsis_once():
    pauses = default_rates().pauses
    assert pauses is not None
    assert pause_seconds("bing-dop…", pauses) == pauses["ellipsis"]
    assert pause_seconds("Hello, world.", pauses) == pauses["comma"] + pauses["period"]
    assert pause_seconds("Wait...", pauses) == pauses["ellipsis"]
    assert pause_seconds("2.5 seconds", pauses) == 0


def test_slot_comes_from_the_next_shot_not_a_stale_end(tmp_path):
    shot = tmp_path / "shots.md"
    shot.write_text(
        "\n".join(
            [
                "| # | Time | Lyric |",
                "|---|---|---|",
                "| S01 | 0:00.0–0:09.9 | Hi there. |",
                "| S02 | 0:02.0–0:03.0 | Yo. |",
                "| S03 | 0:03.0 | (instrumental) |",
            ]
        ),
        encoding="utf-8",
    )
    lines = fit_text(shot.read_text(encoding="utf-8"), "shots.md", default_rates())
    assert lines is not None
    assert lines[0].slot_seconds == 2.0
    assert lines[0].slot_source == "next-shot"
    assert "next shot" in lines[0].note
    assert lines[1].slot_seconds == 1.0
    # Last row has a start, no end, and no following shot. There is no speech to time.
    assert lines[2].status == "silent"
    assert lines[2].slot_seconds is None


def test_overrun_tight_and_rate_change(tmp_path):
    shot = tmp_path / "shots.md"
    shot.write_text(
        "\n".join(
            [
                "| Shot | Time | VO |",
                "|---|---|---|",
                "| A | 0:00.0 | Hello there friend. |",
                "| B | 0:01.0–0:02.0 | (music) |",
            ]
        ),
        encoding="utf-8",
    )
    text = shot.read_text(encoding="utf-8")
    brisk = fit_text(text, "shots.md", default_rates())
    assert brisk is not None
    assert brisk[0].status == "overrun"
    assert brisk[0].margin_seconds is not None and brisk[0].margin_seconds < 0
    assert brisk[0].slot_seconds == 1.0
    slow = default_rates()
    faster = type(slow)(
        speaking_rate_syllables_per_second=12,
        tight_margin_seconds=0.05,
        pauses=dict(slow.pauses or {}),
        source="test",
    )
    quick = fit_text(text, "shots.md", faster)
    assert quick is not None
    assert quick[0].status == "ok"
    assert quick[0].estimate_seconds < brisk[0].estimate_seconds


def test_parenthetical_notes_are_not_spoken():
    text = "\n".join(
        [
            "| # | Time | Lyric |",
            "|---|---|---|",
            "| S01 | 0:00.0–0:02.9 | *Pop it down with a bing-dop…* (first chant, starts 0:00.8) |",
            "| S02 | 0:02.9–0:04.0 | *(instrumental break)* |",
        ]
    )
    lines = fit_text(text, "x.md", default_rates())
    assert lines is not None
    assert lines[0].spoken_text == "Pop it down with a bing-dop…"
    assert "chant" not in lines[0].spoken_text
    assert lines[0].syllables == 7
    assert lines[1].kind == "silent"
    assert lines[1].syllables == 0


def test_sample_shot_list():
    report = fit_path(SHOT, load_rates(RATES))
    by_shot = {line.shot: line for line in report.lines}
    assert len(report.lines) == 7
    assert set(by_shot) == {"C1", "C2", "C3", "S01", "S02", "S10", "S21"}
    assert by_shot["S01"].status == "ok"
    assert by_shot["S21"].syllables == 13
    assert by_shot["S21"].status == "tight"
    for card in ("C1", "C2", "C3"):
        assert by_shot[card].status == "silent"
    assert all(line.status != "overrun" for line in report.lines)
    markdown = render_markdown(report)
    payload = json.loads(render_json(report))
    assert "Voiceover fit report" in markdown
    assert "S21" in markdown
    assert "estimate_seconds" in payload["lines"][0]
    assert payload["summary"]["overruns"] == 0


def test_rates_file_rejects_unknown_keys(tmp_path):
    path = tmp_path / "rates.yaml"
    path.write_text("version: 1\nspeaking_rate_syllables_per_second: 4.5\nextra: 1\n", encoding="utf-8")
    try:
        load_rates(path)
    except RatesError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected RatesError")


def test_cli_is_read_only_and_refuses_the_input_tree(tmp_path):
    drafts = tmp_path / "in"
    drafts.mkdir()
    shot = drafts / "SHOTLIST.md"
    original = "\n".join(
        [
            "| # | Time | Lyric |",
            "|---|---|---|",
            "| S01 | 0:00.0–0:05.0 | Hello. |",
            "| S02 | 0:05.0–0:06.0 | (music out) |",
        ]
    )
    shot.write_text(original, encoding="utf-8")
    before = shot.read_bytes()
    stamp = shot.stat().st_mtime_ns
    out = tmp_path / "reports"
    md = out / "vo-fit.md"
    js = out / "vo-fit.json"
    assert main([str(shot), "--md", str(md), "--json", str(js)]) == 0
    assert shot.read_bytes() == before
    assert shot.stat().st_mtime_ns == stamp
    body = json.loads(js.read_text(encoding="utf-8"))
    assert body["lines"][0]["status"] == "ok"
    assert "Slot" in md.read_text(encoding="utf-8")
    inside = drafts / "leak.md"
    assert main([str(shot), "--md", str(inside), "--json", str(js)]) == 2
    assert not inside.exists()
    assert shot.read_bytes() == before
