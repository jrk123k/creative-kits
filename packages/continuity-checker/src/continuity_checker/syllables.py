"""Spoken-duration estimate: vowel-group syllables plus punctuation pauses.

This is not a pronunciation dictionary. It is stable enough to compare a
lyric line with a shot slot, and the speaking rate in the rates file is the
knob when a project speaks faster or slower than the default.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
_VOWELS = set("aeiouy")
_ONE_SYLLABLE = {"don't", "won't", "can't", "shan't"}
_SIBILANT = re.compile(r"(?:[sxz]|ch|sh)$")
# Adjacent vowels are one group. These words split them.
_EXCEPTIONS = {
    "simoleons": 4,  # si-mo-le-ons; "eo" is two syllables
    "pavement": 2,  # pave-ment; the e is the silent e of "pave"
}


def syllables_in_word(word: str) -> int:
    raw = word.strip().lower().replace("’", "'")
    if not raw:
        return 0
    if raw in _ONE_SYLLABLE:
        return 1
    if raw.endswith("n't"):
        base = re.sub(r"[^a-z]", "", raw[:-3])
        return syllables_in_word(base) + 1 if base else 1
    if raw.endswith("'s"):
        base = re.sub(r"[^a-z]", "", raw[:-2])
        if not base:
            return 1
        extra = 1 if _SIBILANT.search(base) else 0
        return syllables_in_word(base) + extra
    letters = re.sub(r"[^a-z]", "", raw)
    if letters in _EXCEPTIONS:
        return _EXCEPTIONS[letters]
    if not letters:
        return 0
    if len(letters) <= 3:
        return 1
    count = _vowel_groups(letters)
    if letters.endswith("ed") and len(letters) > 4 and letters[-3] not in "td" and count > 1:
        count -= 1
    elif letters.endswith("e") and not letters.endswith(("le", "ee", "ie", "oe", "ye")) and count > 1:
        count -= 1
    return max(1, count)


def count_syllables(text: str) -> int:
    return sum(syllables_in_word(match.group(0)) for match in _WORD.finditer(text))


def pause_seconds(text: str, pauses: Mapping[str, float]) -> float:
    """Add a pause for each punctuation mark. Hyphens inside words are not pauses."""
    remaining = text
    total = len(re.findall(r"…|\.{3}", remaining)) * pauses["ellipsis"]
    remaining = re.sub(r"…|\.{3}", " ", remaining)
    remaining = re.sub(r"(?<=\d)\.(?=\d)", "", remaining)
    marks = {
        ",": "comma",
        ";": "semicolon",
        ":": "colon",
        ".": "period",
        "?": "question",
        "!": "excl_mark",
        "—": "emdash",
        "–": "endash",
    }
    for char, key in marks.items():
        total += remaining.count(char) * pauses[key]
    return total


def _vowel_groups(letters: str) -> int:
    count = 0
    previous = False
    for char in letters:
        vowel = char in _VOWELS
        if vowel and not previous:
            count += 1
        previous = vowel
    return count
