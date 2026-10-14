"""Small English grapheme-to-phoneme front end.

Irregular words used by the demos live in an original lexicon. Everything
else goes through letter rules written for this project. This is not the
SAM reciter and it is not the CMU dictionary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from retro_voice.phonemes import ALIASES, PHONES, VOWELS, canonical

# ARPAbet names plus the published SAM manual spellings (OH, NX, H, ...).
PHONEME_SYMBOLS = set(PHONES) | set(ALIASES)


@dataclass
class Phone:
    name: str
    stress: int = 0


_LEXICON_TEXT = """
a AH0
an AE N
and AE N D
all AO L
are AA R
as AE Z
at AE T
back B AE K
be B IY
bench B EH N CH
built B IH L T
but B AH T
by B AY
chorus K AO R AH S
clean K L IY N
do D UW
every EH V R IY
for F AO R
friend F R EH N D
from F R AH M
hand HH AE N D
hello HH AH L OW
hold HH OW L D
i AY
in IH N
is IH Z
it IH T
it's IH T S
its IH T S
know N OW
la L AA
late L EY T
light L AY T
like L AY K
line L AY N
lo L OW
me M IY
mouth M AW TH
music M Y UW Z IH K
my M AY
night N AY T
no N OW
not N AA T
now N AW
of AH V
on AA N
or AO R
our AW ER
pitch P IH CH
project P R AA JH EH K T
remember R IH M EH M B ER
robot R OW B AA T
room R UW M
sang S AE NG
show SH OW
sing S IH NG
slow S L OW
so S OW
the DH AH0
there DH EH R
they DH EY
this DH IH S
thought TH AO T
throat TH R OW T
tin T IH N
to T UW
tonight T AH N AY T
true T R UW
under AH N D ER
voice V OY S
was W AH Z
we W IY
what W AH T
wires W AY R Z
with W IH DH
wrote R OW T
yes Y EH S
you Y UW
your Y AO R
"""


def _parse_entry(line: str) -> tuple[str, list[Phone]]:
    parts = line.split()
    word, raws = parts[0], parts[1:]
    phones: list[Phone] = []
    marked = False
    for raw in raws:
        stress = 0
        if raw[-1].isdigit():
            stress = int(raw[-1])
            raw = raw[:-1]
            marked = True
        phones.append(Phone(canonical(raw), stress))
    if not marked:
        for phone in phones:
            if phone.name in VOWELS:
                phone.stress = 1
                break
    return word, phones


LEXICON: dict[str, list[Phone]] = {}
for _line in _LEXICON_TEXT.splitlines():
    _line = _line.strip()
    if not _line:
        continue
    _word, _phones = _parse_entry(_line)
    LEXICON[_word] = _phones


_TENSE = {"a": "EY", "e": "IY", "i": "AY", "o": "OW", "u": "UW"}
_LAX = {"a": "AE", "e": "EH", "i": "IH", "o": "AA", "u": "AH"}
_DIGRAPH = {
    "ch": ("CH",),
    "sh": ("SH",),
    "th": ("TH",),
    "ph": ("F",),
    "wh": ("W",),
    "ck": ("K",),
    "ng": ("NG",),
    "qu": ("K", "W"),
    "ee": ("IY",),
    "ea": ("IY",),
    "ai": ("EY",),
    "ay": ("EY",),
    "oa": ("OW",),
    "oo": ("UW",),
    "oi": ("OY",),
    "oy": ("OY",),
    "au": ("AO",),
    "aw": ("AO",),
    "ou": ("AW",),
    "ow": ("AW",),
}
_CONS = {
    "b": "B",
    "d": "D",
    "f": "F",
    "h": "HH",
    "j": "JH",
    "k": "K",
    "l": "L",
    "m": "M",
    "n": "N",
    "p": "P",
    "r": "R",
    "s": "S",
    "t": "T",
    "v": "V",
    "w": "W",
    "y": "Y",
    "z": "Z",
}


def _rules(word: str) -> list[Phone]:
    core = re.sub(r"[^a-z]", "", word.lower())
    if not core:
        return [Phone("AH", 0)]
    silent_e = (
        len(core) >= 4
        and core.endswith("e")
        and core[-2] not in "aeiou"
        and any(ch in "aeiou" for ch in core[:-2])
    )
    if silent_e:
        core = core[:-1]
    out: list[Phone] = []

    def add(name: str, stress: int = 0) -> None:
        out.append(Phone(canonical(name), stress))

    i = 0
    while i < len(core):
        tri = core[i : i + 3]
        bi = core[i : i + 2]
        if tri == "igh":
            add("AY", 1)
            i += 3
            continue
        if tri == "tch":
            add("CH")
            i += 3
            continue
        if bi in _DIGRAPH:
            for name in _DIGRAPH[bi]:
                add(name, 1 if name in VOWELS else 0)
            i += 2
            continue
        if bi in {"er", "ir", "ur"}:
            add("ER", 1)
            i += 2
            continue
        if bi == "ar":
            add("AA", 1)
            add("R")
            i += 2
            continue
        if bi == "or":
            add("AO", 1)
            add("R")
            i += 2
            continue
        ch = core[i]
        if ch in "aeiou":
            tense = i == len(core) - 1
            if silent_e and i == len(core) - 2 and core[i + 1] not in "aeiou":
                tense = True
            add(_TENSE[ch] if tense else _LAX[ch], 1)
            i += 1
            continue
        nxt = core[i + 1] if i + 1 < len(core) else ""
        if ch == "c":
            add("S" if nxt in "eiy" else "K")
        elif ch == "g":
            add("JH" if nxt in "eiy" else "G")
        elif ch == "x":
            add("K")
            add("S")
        elif ch == "q":
            add("K")
        elif ch == "y":
            # Word-final y is a vowel ("glory", "happy"); elsewhere it is a glide.
            if i == len(core) - 1 and i > 0:
                add("IY", 1)
            else:
                add("Y")
        else:
            add(_CONS.get(ch, "T"))
        i += 1
    if not any(phone.stress for phone in out):
        for phone in out:
            if phone.name in VOWELS:
                phone.stress = 1
                break
    if not out:
        out.append(Phone("AH", 0))
    return out


def pronounce(word: str) -> list[Phone]:
    key = re.sub(r"[^a-z']", "", word.lower())
    if key in LEXICON:
        return [Phone(phone.name, phone.stress) for phone in LEXICON[key]]
    bare = key.replace("'", "")
    if bare in LEXICON:
        return [Phone(phone.name, phone.stress) for phone in LEXICON[bare]]
    return _rules(bare)


def parse_phoneme_string(text: str) -> list[Phone]:
    """Parse spaced ARPAbet or a jammed SAM-style string such as HEHLOW."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("phoneme string is empty")
    symbols = sorted(set(PHONEME_SYMBOLS), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(symbol) for symbol in symbols))
    upper = cleaned.upper()
    phones: list[Phone] = []
    i = 0
    while i < len(upper):
        if upper[i].isspace():
            i += 1
            continue
        if upper[i] in ",.;!?":
            phones.append(Phone("PA", 0))
            i += 1
            continue
        match = pattern.match(upper, i)
        if match is None:
            snippet = upper[i : i + 12]
            raise ValueError(f"not a phoneme near {snippet!r} in {text!r}")
        stress = 0
        i = match.end()
        if i < len(upper) and upper[i].isdigit():
            stress = int(upper[i])
            i += 1
        phones.append(Phone(canonical(match.group()), stress))
    if not phones:
        raise ValueError("phoneme string is empty")
    return phones
