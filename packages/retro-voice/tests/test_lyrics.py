from retro_voice.demo_data import HARMONY_LYRICS, HARMONY_NOTES, LEAD_LYRICS, LEAD_NOTES
from retro_voice.g2p import pronounce
from retro_voice.lyrics import LyricAlignError, parse_lyrics, phones_for_syllables

import pytest


def test_hyphen_splits_a_word_into_syllables():
    syllables = parse_lyrics("to-night")
    assert [syl.grapheme for syl in syllables] == ["to", "night"]
    assert {syl.word for syl in syllables} == {"tonight"}
    phones = phones_for_syllables(syllables)
    assert [phone.name for phone in phones[0]] == ["T", "AH"]
    assert [phone.name for phone in phones[1]] == ["N", "AY", "T"]


def test_spaced_hyphens_and_melisma():
    syllables = parse_lyrics("beau- ti- ful")
    assert [syl.grapheme for syl in syllables] == ["beau", "ti", "ful"]
    assert syllables[0].word == "beautiful"

    held = parse_lyrics("to- - night")
    assert [syl.display for syl in held] == ["to", "-", "night"]
    phones = phones_for_syllables(held)
    assert [phone.name for phone in phones[1]] == ["AH"]


def test_standalone_melisma_and_brackets():
    syllables = parse_lyrics("thought - friend")
    assert [syl.display for syl in syllables] == ["thought", "-", "friend"]
    phones = phones_for_syllables(syllables)
    assert phones[1][0].name == "AO"

    forced = parse_lyrics("[HH EH L OW]")
    assert [phone.name for phone in forced[0].phonemes] == ["HH", "EH", "L", "OW"]


def test_melisma_cannot_lead():
    with pytest.raises(LyricAlignError):
        parse_lyrics("- hello")


def test_demo_lines_match_the_melodies():
    assert len(parse_lyrics(LEAD_LYRICS)) == len(LEAD_NOTES)
    assert len(parse_lyrics(HARMONY_LYRICS)) == len(HARMONY_NOTES)
    # The title line is in the lyric, and the hyphen is a real melisma.
    assert "-" in [syl.display for syl in parse_lyrics(LEAD_LYRICS)]


def test_vowel_count_mismatch_is_explicit():
    # "thought" has one vowel; hyphenating it into two syllables must fail clearly.
    with pytest.raises(LyricAlignError, match="syllables"):
        phones_for_syllables(parse_lyrics("thou- ght"))
    assert pronounce("thought")[1].name == "AO"
