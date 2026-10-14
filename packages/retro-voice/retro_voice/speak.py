"""Text and phoneme strings to a spoken robot buffer."""

from __future__ import annotations

import re

import numpy as np

from retro_voice.controls import EffectChain, VoiceControls, effect_preset
from retro_voice.effects import apply_chain
from retro_voice.g2p import Phone, parse_phoneme_string, pronounce
from retro_voice.phonemes import PHONES, VOWEL_KINDS
from retro_voice.synth import SR_DEFAULT, blank_curves, expand_phone, next_vowel_targets, paint, synthesize


_TOKEN = re.compile(r"[A-Za-z']+|[0-9]+|[,.;!?]")
_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def _pause_seconds(mark: str, speed_scale: float) -> float:
    if mark == ",":
        return 0.15 * speed_scale
    if mark == "?":
        return 0.30 * speed_scale
    if mark in ";:":
        return 0.18 * speed_scale
    return 0.26 * speed_scale


def text_to_phones(text: str, speed_scale: float) -> list[tuple[Phone, float]]:
    """Return (phone, duration_seconds) for a spoken line."""
    events: list[tuple[Phone, float]] = []
    for token in _TOKEN.findall(text):
        if token in ",.;!?:":
            events.append((Phone("PA", 0), _pause_seconds(token, speed_scale)))
            continue
        if token.isdigit():
            words = [_DIGITS[int(ch)] for ch in token]
        else:
            words = [token]
        for word in words:
            for phone in pronounce(word):
                spec = PHONES[phone.name]
                dur = spec.dur * speed_scale
                if spec.kind in VOWEL_KINDS:
                    if phone.stress >= 1:
                        dur *= 1.3
                    else:
                        dur *= 0.84
                events.append((phone, dur))
    if not events:
        raise ValueError("nothing to say")
    return events


def render_phones(
    phones: list[Phone],
    durations: list[float],
    controls: VoiceControls,
    sample_rate: int = SR_DEFAULT,
    seed: int = 0,
    question: bool = False,
) -> np.ndarray:
    controls = controls.validated()
    if len(phones) != len(durations):
        raise ValueError("each phoneme needs a duration")
    counts = [max(1, int(round(dur * sample_rate))) for dur in durations]
    total = sum(counts)
    curves = blank_curves(total, 112.0 * controls.pitch_scale())
    lookahead = next_vowel_targets(phones)
    cursor = 0
    base = 112.0 * controls.pitch_scale()
    for phone, count, nxt in zip(phones, counts, lookahead):
        mult = 1.0
        if PHONES[phone.name].kind in VOWEL_KINDS:
            if phone.stress >= 1:
                mult = 1.09
            elif phone.stress == 0:
                mult = 0.96
        micros = expand_phone(phone, count, base * mult, controls.mouth, controls.throat, 1.0, nxt)
        paint(micros, cursor, curves)
        cursor += count
    declination = np.linspace(1.06, 0.92, total)
    if question:
        rise_at = int(total * 0.72)
        declination[rise_at:] *= np.linspace(1.0, 1.22, total - rise_at)
    curves["f0"] *= declination
    return synthesize(curves, sample_rate, seed)


def render_speech(
    text: str,
    controls: VoiceControls | None = None,
    effects: EffectChain | None = None,
    sample_rate: int = SR_DEFAULT,
    seed: int = 0,
    phonemes: bool = False,
) -> np.ndarray:
    controls = (controls or VoiceControls()).validated()
    effects = effects if effects is not None else effect_preset("sam")
    question = (not phonemes) and text.strip().endswith("?")
    if phonemes:
        phones = parse_phoneme_string(text)
        scale = controls.speed_scale()
        durations = []
        for phone in phones:
            spec = PHONES[phone.name]
            dur = spec.dur * scale
            if spec.kind in VOWEL_KINDS and phone.stress >= 1:
                dur *= 1.25
            durations.append(dur)
    else:
        pairs = text_to_phones(text, controls.speed_scale())
        phones = [phone for phone, _dur in pairs]
        durations = [dur for _phone, dur in pairs]
    audio = render_phones(phones, durations, controls, sample_rate, seed, question=question)
    return apply_chain(audio, sample_rate, effects)
