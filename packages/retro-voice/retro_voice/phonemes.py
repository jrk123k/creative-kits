"""Clean-room phoneme targets.

Formant numbers are rounded adult-male averages in the ranges published by
acoustic phonetics (Peterson & Barney, Hillenbrand and colleagues). They are
not copied from any Software Automatic Mouth table. Bandwidths and durations
are original to this synthesizer.

Phoneme *names* accept ARPAbet and the classic SAM user-manual spellings
(AH, EH, TH, NX, …) so existing lyric sheets can be typed in. The names are
an input alphabet only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhoneSpec:
    name: str
    kind: str
    f1: float = 500.0
    f2: float = 1500.0
    f3: float = 2500.0
    f1b: float | None = None
    f2b: float | None = None
    f3b: float | None = None
    bw1: float = 80.0
    bw2: float = 110.0
    bw3: float = 160.0
    dur: float = 0.09
    voice: float = 1.0
    noise: float = 0.0
    nf: float = 2500.0
    nbw: float = 900.0
    voiced_stop: bool = False


def _v(name, f1, f2, f3, dur=0.12, bw1=70, bw2=100, bw3=150) -> PhoneSpec:
    return PhoneSpec(name, "vowel", f1, f2, f3, dur=dur, bw1=bw1, bw2=bw2, bw3=bw3)


def _d(name, f1, f2, f3, f1b, f2b, f3b, dur=0.17) -> PhoneSpec:
    return PhoneSpec(
        name, "diphthong", f1, f2, f3, f1b, f2b, f3b, dur=dur, bw1=75, bw2=110, bw3=160
    )


PHONES: dict[str, PhoneSpec] = {
    "IY": _v("IY", 270, 2290, 3010, dur=0.12),
    "IH": _v("IH", 400, 1920, 2560, dur=0.09),
    "EH": _v("EH", 530, 1840, 2480, dur=0.10),
    "AE": _v("AE", 690, 1660, 2490, dur=0.13),
    "AA": _v("AA", 730, 1090, 2440, dur=0.13),
    "AO": _v("AO", 570, 840, 2410, dur=0.13),
    "UH": _v("UH", 450, 1030, 2250, dur=0.09),
    "UW": _v("UW", 300, 870, 2240, dur=0.12),
    "AH": _v("AH", 640, 1190, 2390, dur=0.10),
    "AX": _v("AX", 500, 1500, 2500, dur=0.07, bw1=110, bw2=140, bw3=180),
    "ER": _v("ER", 490, 1350, 1690, dur=0.12, bw3=120),
    "EY": _d("EY", 480, 1900, 2600, 320, 2200, 2900),
    "OW": _d("OW", 500, 900, 2400, 360, 780, 2300),
    "AY": _d("AY", 700, 1200, 2500, 400, 2000, 2700),
    "AW": _d("AW", 700, 1200, 2500, 450, 900, 2300),
    "OY": _d("OY", 520, 850, 2400, 380, 2000, 2700),
    "P": PhoneSpec("P", "stop", dur=0.08, voice=0, noise=0, nf=1800, nbw=800),
    "B": PhoneSpec("B", "stop", dur=0.07, voice=0, nf=250, nbw=200, voiced_stop=True),
    "T": PhoneSpec("T", "stop", dur=0.07, voice=0, nf=4200, nbw=900),
    "D": PhoneSpec("D", "stop", dur=0.06, voice=0, nf=3200, nbw=700, voiced_stop=True),
    "K": PhoneSpec("K", "stop", dur=0.08, voice=0, nf=2100, nbw=700),
    "G": PhoneSpec("G", "stop", dur=0.07, voice=0, nf=1700, nbw=500, voiced_stop=True),
    "F": PhoneSpec("F", "fricative", dur=0.09, voice=0, noise=0.55, nf=4200, nbw=1800),
    "V": PhoneSpec("V", "fricative", dur=0.08, voice=0.45, noise=0.4, nf=2500, nbw=1200, f1=300, f2=1100, f3=2300),
    "TH": PhoneSpec("TH", "fricative", dur=0.09, voice=0, noise=0.45, nf=4500, nbw=2000),
    "DH": PhoneSpec("DH", "fricative", dur=0.07, voice=0.4, noise=0.35, nf=3200, nbw=1400, f1=300, f2=1300, f3=2400),
    "S": PhoneSpec("S", "fricative", dur=0.11, voice=0, noise=0.9, nf=4500, nbw=1400),
    "Z": PhoneSpec("Z", "fricative", dur=0.09, voice=0.4, noise=0.7, nf=4200, nbw=1200, f1=300, f2=1400, f3=2500),
    "SH": PhoneSpec("SH", "fricative", dur=0.11, voice=0, noise=0.85, nf=2700, nbw=800),
    "ZH": PhoneSpec("ZH", "fricative", dur=0.09, voice=0.4, noise=0.65, nf=2500, nbw=700, f1=300, f2=1600, f3=2500),
    "HH": PhoneSpec("HH", "fricative", dur=0.07, voice=0.15, noise=0.55, nf=2000, nbw=1400),
    "CH": PhoneSpec("CH", "affricate", dur=0.12, voice=0, noise=0.85, nf=2800, nbw=800),
    "JH": PhoneSpec("JH", "affricate", dur=0.11, voice=0.25, noise=0.7, nf=2500, nbw=700, voiced_stop=True),
    "M": PhoneSpec("M", "nasal", f1=280, f2=900, f3=2200, bw1=140, bw2=160, dur=0.08, voice=0.62),
    "N": PhoneSpec("N", "nasal", f1=280, f2=1450, f3=2500, bw1=140, bw2=180, dur=0.08, voice=0.6),
    "NG": PhoneSpec("NG", "nasal", f1=280, f2=1900, f3=2600, bw1=150, bw2=180, dur=0.09, voice=0.58),
    "L": PhoneSpec("L", "liquid", f1=400, f2=1050, f3=2600, bw1=80, dur=0.08, voice=0.85),
    "R": PhoneSpec("R", "liquid", f1=420, f2=1100, f3=1550, bw3=90, dur=0.08, voice=0.85),
    "W": PhoneSpec("W", "glide", f1=300, f2=700, f3=2200, dur=0.06, voice=0.9),
    "Y": PhoneSpec("Y", "glide", f1=300, f2=2100, f3=3000, dur=0.06, voice=0.9),
    "PA": PhoneSpec("PA", "pause", dur=0.18, voice=0, noise=0),
}


VOWEL_KINDS = {"vowel", "diphthong"}
VOWELS = {name for name, spec in PHONES.items() if spec.kind in VOWEL_KINDS}

# Published SAM manual spellings and a few ARPAbet extras, mapped onto our set.
ALIASES = {
    "OH": "AO",
    "UX": "UW",
    "IX": "IH",
    "NX": "NG",
    "WH": "W",
    "H": "HH",
    "J": "JH",
    "DX": "D",
    "Q": "PA",
}


def canonical(name: str) -> str:
    key = name.upper()
    key = ALIASES.get(key, key)
    if key not in PHONES:
        known = ", ".join(sorted(set(PHONES) | set(ALIASES)))
        raise ValueError(f"unknown phoneme {name!r}. Known symbols include {known}")
    return key


def is_vowel(name: str) -> bool:
    return canonical(name) in VOWELS


def shape_formants(
    f1: float, f2: float, f3: float, mouth: int, throat: int
) -> tuple[float, float, float]:
    """Apply the mouth and throat knobs. 128 / 128 leaves targets unchanged."""
    mouth_amount = (mouth - 128) / 128.0
    throat_amount = (throat - 128) / 128.0
    f1 = f1 * (1.0 + 0.48 * throat_amount) + 50.0 * throat_amount
    f2 = f2 * (1.0 + 0.58 * mouth_amount)
    f3 = f3 * (1.0 + 0.36 * mouth_amount) + 70.0 * mouth_amount
    f1 = min(1100.0, max(150.0, f1))
    f2 = min(3400.0, max(450.0, f2))
    f3 = min(4500.0, max(1400.0, f3))
    if f2 < f1 + 150:
        f2 = f1 + 150
    if f3 < f2 + 200:
        f3 = f2 + 200
    return f1, f2, f3
