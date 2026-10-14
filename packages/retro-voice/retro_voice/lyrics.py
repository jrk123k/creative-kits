"""Syllable splitter for sung lines.

Convention, one note per resulting syllable:

- Hyphens break a word into syllables: ``to-night``, ``beau- ti- ful``.
- A lone ``-`` holds the previous syllable across another note (melisma):
  ``thought - friend``.
- A trailing hyphen keeps the word open through a following melisma:
  ``glo- - ry`` is the word "glory" on three notes.
- Square brackets force phonemes for that one note: ``[TH AO T]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from retro_voice.g2p import Phone, pronounce
from retro_voice.phonemes import VOWELS, is_vowel


class LyricAlignError(ValueError):
    pass


@dataclass
class Syllable:
    grapheme: str
    melisma: bool = False
    phonemes: list[Phone] | None = None
    word: str = ""
    word_id: int = -1
    slice_index: int = 0
    slice_count: int = 1

    @property
    def display(self) -> str:
        if self.melisma:
            return "-"
        if self.phonemes is not None:
            return "[" + " ".join(phone.name for phone in self.phonemes) + "]"
        return self.grapheme


_PUNCT = ".,!?;:\"“”()[]{}"


def parse_lyrics(text: str) -> list[Syllable]:
    if text is None or not str(text).strip():
        raise LyricAlignError("lyrics are empty")
    raw = str(text).replace("—", "-").replace("–", "-").replace("‐", "-")
    bracketed: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        bracketed.append(match.group(1).strip())
        return f" __PH{len(bracketed) - 1}__ "

    raw = re.sub(r"\[([^\]]*)\]", _stash, raw)
    tokens = raw.split()
    syllables: list[Syllable] = []
    word_buf: list[Syllable] = []
    word_serial = 0

    def flush() -> None:
        nonlocal word_buf, word_serial
        if not word_buf:
            return
        graphemes = [syl.grapheme for syl in word_buf if not syl.melisma and syl.phonemes is None]
        word = "".join(graphemes).lower()
        slices = [syl for syl in word_buf if not syl.melisma and syl.phonemes is None]
        for index, syl in enumerate(slices):
            syl.word = word
            syl.word_id = word_serial
            syl.slice_index = index
            syl.slice_count = len(slices)
        for syl in word_buf:
            if syl.melisma or syl.phonemes is not None:
                syl.word = word
                syl.word_id = word_serial
        syllables.extend(word_buf)
        word_buf = []
        word_serial += 1

    for token in tokens:
        phoneme_match = re.fullmatch(r"__PH(\d+)__", token)
        if phoneme_match:
            body = bracketed[int(phoneme_match.group(1))]
            if not body:
                raise LyricAlignError("empty phoneme bracket []")
            from retro_voice.g2p import parse_phoneme_string

            phones = parse_phoneme_string(body)
            flush()
            syllables.append(
                Syllable(grapheme=body, phonemes=phones, word=body, word_id=-1)
            )
            continue
        if token == "-":
            if not word_buf and not syllables:
                raise LyricAlignError("melisma '-' has no previous syllable")
            melisma = Syllable(grapheme="-", melisma=True)
            if word_buf:
                word_buf.append(melisma)
            else:
                syllables.append(melisma)
            continue
        token = token.strip(_PUNCT)
        if not token:
            continue
        if token == "-":
            continue
        ends_open = token.endswith("-")
        parts = token.split("-")
        expanded: list[tuple[str, str]] = []
        for index, part in enumerate(parts):
            if part == "":
                if index not in (0, len(parts) - 1):
                    expanded.append(("melisma", ""))
                continue
            expanded.append(("syl", part.strip(_PUNCT)))
        if not expanded:
            raise LyricAlignError(f"could not read lyric token {token!r}")
        for kind, grapheme in expanded:
            if kind == "melisma":
                word_buf.append(Syllable(grapheme="-", melisma=True))
            else:
                if not grapheme:
                    raise LyricAlignError(f"empty syllable in {token!r}")
                word_buf.append(Syllable(grapheme=grapheme))
        if not ends_open:
            flush()
    flush()
    if not syllables:
        raise LyricAlignError("lyrics did not contain any syllables")
    if syllables[0].melisma:
        raise LyricAlignError("melisma '-' has no previous syllable")
    return syllables


def distribute(phones: list[Phone], count: int) -> list[list[Phone]]:
    if count < 1:
        raise LyricAlignError("a word needs at least one syllable")
    if count == 1:
        return [list(phones)]
    vowel_at = [i for i, phone in enumerate(phones) if phone.name in VOWELS]
    if len(vowel_at) == count:
        slices: list[list[Phone]] = []
        for index, vowel_index in enumerate(vowel_at):
            start = 0 if index == 0 else vowel_at[index - 1] + 1
            end = len(phones) if index == count - 1 else vowel_index + 1
            # Maximal onset: consonants between vowels belong to the next syllable,
            # which is what `start = previous vowel + 1` already does. The non-final
            # slice must end at its vowel so those consonants are not stolen back.
            if index != count - 1:
                end = vowel_index + 1
            slices.append(phones[start:end])
        return slices
    if len(vowel_at) == 0:
        base, extra = divmod(len(phones), count)
        slices = []
        cursor = 0
        for index in range(count):
            width = base + (1 if index < extra else 0)
            if width < 1:
                raise LyricAlignError("not enough phonemes for the hyphenated syllables")
            slices.append(phones[cursor : cursor + width])
            cursor += width
        return slices
    raise LyricAlignError(
        f"lyrics split a word into {count} syllables but the pronunciation has "
        f"{len(vowel_at)} vowel sound{'s' if len(vowel_at) != 1 else ''}: "
        + " ".join(phone.name for phone in phones)
    )


def phones_for_syllables(syllables: list[Syllable]) -> list[list[Phone]]:
    """Return the phone list sung on each syllable, melisma included."""
    grouped: dict[int, list[list[Phone]]] = {}
    for syl in syllables:
        if syl.melisma or syl.phonemes is not None or syl.word_id < 0:
            continue
        if syl.word_id in grouped:
            continue
        pronounced = pronounce(syl.word)
        try:
            grouped[syl.word_id] = distribute(pronounced, syl.slice_count)
        except LyricAlignError as exc:
            raise LyricAlignError(f"{syl.word!r}: {exc}") from exc

    resolved: list[list[Phone]] = []
    previous: list[Phone] | None = None
    for syl in syllables:
        if syl.melisma:
            if not previous:
                raise LyricAlignError("melisma '-' has no previous syllable")
            vowels = [phone for phone in previous if is_vowel(phone.name)]
            chosen = vowels[-1:] if vowels else previous[-1:]
            phones = [Phone(phone.name, phone.stress) for phone in chosen]
        elif syl.phonemes is not None:
            phones = [Phone(phone.name, phone.stress) for phone in syl.phonemes]
        else:
            phones = [
                Phone(phone.name, phone.stress)
                for phone in grouped[syl.word_id][syl.slice_index]
            ]
        if not phones:
            raise LyricAlignError(f"syllable {syl.display!r} has no phonemes")
        resolved.append(phones)
        previous = phones
    return resolved


def alignment_preview(pitch_names: list[str], syllables: list[Syllable]) -> str:
    rows = []
    for pitch, syl in zip(pitch_names, syllables):
        rows.append(f"  {pitch:<6} {syl.display}")
    return "\n".join(rows)
