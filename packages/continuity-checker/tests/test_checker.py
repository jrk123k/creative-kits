"""Checker behavior against the fictional sample corpus."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from continuity_checker.cli import main
from continuity_checker.engine import check
from continuity_checker.globmatch import glob_match
from continuity_checker.report import render_json, render_markdown
from continuity_checker.rules import RuleError, load_rules

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules.yaml"
DRAFTS = ROOT / "examples" / "drafts"
SOURCES = ROOT / "examples" / "sources" / "projects"


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES)


@pytest.fixture(scope="module")
def corpus(rules):
    return check(DRAFTS, rules, RULES)


def _ids(result, rule_id):
    return [finding for finding in result.findings if finding.rule_id == rule_id]


def test_globs():
    assert glob_match("harbor-waltz/TEST_PROMPTS_3.md", "harbor-waltz/**")
    assert glob_match("harbor-waltz/TEST_PROMPTS_3.md", "**/TEST_PROMPTS*")
    assert glob_match("veloria-show/NEWS_DRAFT.md", "**/*news*")
    assert glob_match("nova-pixel/BRIEF.md", "nova-*/**")
    assert not glob_match("veloria-show/note.md", "harbor-waltz/**")
    assert not glob_match("harbor-waltz/SHOTLIST_v2.md", "**/*prompt*")


def test_rules_file_loads_every_type(rules):
    types = {rule.type for rule in rules}
    assert types == {
        "required_verbatim",
        "forbidden_in_context",
        "name_spelling",
        "term_lock",
        "custom",
    }
    ids = [rule.id for rule in rules]
    assert len(ids) == len(set(ids))
    assert len(rules) >= 40


def test_identity_blocks_are_verbatim_from_the_bibles(rules):
    bible = (SOURCES / "harbor-waltz" / "CHARACTER_BIBLE_v1.md").read_text(encoding="utf-8")
    bible_flat = re.sub(r"\s+", " ", bible.replace("*", ""))
    imagine = [
        rule
        for rule in rules
        if rule.type == "required_verbatim" and rule.id.endswith("-imagine")
    ]
    assert len(imagine) == 5
    for rule in imagine:
        assert re.sub(r"\s+", " ", rule.text) in bible_flat, rule.id

    brief = (SOURCES / "nova-pixel" / "BRIEF.md").read_text(encoding="utf-8")
    nova = next(rule for rule in rules if rule.id == "nova-look-v1")
    assert nova.text in brief

    costume = (SOURCES / "veloria-show" / "COSTUME_BRIEF.md").read_text(encoding="utf-8")
    diva = next(rule for rule in rules if rule.id == "diva-offstage-look")
    assert diva.text in costume

    news = (SOURCES / "veloria-show" / "NEWS_PACKAGE.md").read_text(encoding="utf-8")
    colin = next(rule for rule in rules if rule.id == "colin-figment-wardrobe")
    sarah = next(rule for rule in rules if rule.id == "sarah-ashford-wardrobe")
    assert colin.prefer in news or "navy blazer" in news
    assert "charcoal suit" in news


def test_sources_checksums():
    sums = (ROOT / "examples" / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(sums) >= 5
    for line in sums:
        digest, rel = line.split(None, 1)
        blob = (ROOT / "examples" / "sources" / rel).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == digest, rel


def test_corpus_finds_paraphrased_prompts(corpus):
    hero = _ids(corpus, "harbor-hero-id-imagine")
    assert hero
    assert any("TEST_PROMPTS" in f.file for f in hero)
    assert _ids(corpus, "nova-gown-not-canon")
    assert _ids(corpus, "ban-sphero-in-news")


def test_cli_writes_reports(tmp_path, monkeypatch):
    md = tmp_path / "out.md"
    js = tmp_path / "out.json"
    code = main(
        [
            str(DRAFTS),
            "--rules",
            str(RULES),
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
    assert render_markdown(check(DRAFTS, load_rules(RULES), RULES))
    assert render_json(check(DRAFTS, load_rules(RULES), RULES))


def test_bad_rules_file(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nrules:\n  - id: x\n    type: custom\n    pattern: '('\n",
        encoding="utf-8",
    )
    with pytest.raises(RuleError):
        load_rules(bad)
