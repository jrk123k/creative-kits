"""Tempo-locked singing. Notes stay on the beat grid; lyrics only choose timbre."""

from __future__ import annotations

import numpy as np

from retro_voice.controls import VoiceControls
from retro_voice.g2p import Phone
from retro_voice.lyrics import LyricAlignError, Syllable, alignment_preview, parse_lyrics, phones_for_syllables
from retro_voice.notes import Note, beats_to_samples, midi_hz
from retro_voice.phonemes import PHONES, VOWEL_KINDS
from retro_voice.synth import SR_DEFAULT, blank_curves, expand_phone, next_vowel_targets, paint, synthesize


def allocate_samples(phones: list[Phone], total: int, speed_scale: float, sample_rate: int) -> list[int]:
    """Give consonants a SAM-like slice and pour the rest of the note into vowels."""
    if total < 1:
        raise ValueError("note has no samples")
    if not phones:
        raise ValueError("syllable has no phonemes")
    vowel = [PHONES[phone.name].kind in VOWEL_KINDS for phone in phones]
    base = []
    for phone, is_vowel in zip(phones, vowel):
        if is_vowel:
            base.append(0)
        else:
            base.append(max(1, int(round(PHONES[phone.name].dur * speed_scale * sample_rate))))
    if not any(vowel):
        weights = base or [1] * len(phones)
        weight_sum = sum(weights)
        counts = [max(1, int(round(total * weight / weight_sum))) for weight in weights]
        counts[-1] += total - sum(counts)
        return _repair(counts, total)

    consonant_cap = max(0, int(total * 0.58))
    consonant_total = sum(base)
    if consonant_total > consonant_cap:
        if consonant_cap == 0:
            base = [0 if not is_vowel else 0 for is_vowel in vowel]
        else:
            scale = consonant_cap / consonant_total
            base = [max(1, int(round(value * scale))) if not is_vowel else 0 for value, is_vowel in zip(base, vowel)]
            while sum(base) > consonant_cap:
                for index in range(len(base) - 1, -1, -1):
                    if not vowel[index] and base[index] > 1 and sum(base) > consonant_cap:
                        base[index] -= 1
    vowel_budget = total - sum(base)
    vowel_count = sum(vowel)
    if vowel_budget < vowel_count:
        # Steal samples back from consonants so every vowel is audible.
        need = vowel_count - vowel_budget
        for index in range(len(base) - 1, -1, -1):
            if need <= 0:
                break
            if not vowel[index] and base[index] > 1:
                take = min(base[index] - 1, need)
                base[index] -= take
                need -= take
        vowel_budget = total - sum(base)
    each, extra = divmod(max(vowel_budget, vowel_count), vowel_count)
    counts: list[int] = []
    seen = 0
    for value, is_vowel in zip(base, vowel):
        if is_vowel:
            counts.append(each + (1 if seen < extra else 0))
            seen += 1
        else:
            counts.append(value)
    return _repair(counts, total)


def _repair(counts: list[int], total: int) -> list[int]:
    if not counts:
        return [total]
    counts = [max(0, count) for count in counts]
    # Keep a sample on every phone that already had one; zeros are empty slices.
    counts[-1] += total - sum(counts)
    if counts[-1] < 1:
        deficit = 1 - counts[-1]
        counts[-1] = 1
        for index in range(len(counts) - 2, -1, -1):
            if deficit <= 0:
                break
            spare = counts[index] - (1 if counts[index] > 0 else 0)
            take = min(max(spare, 0), deficit)
            counts[index] -= take
            deficit -= take
    # Drop accidental overflow by trimming the tail.
    while sum(counts) > total:
        for index in range(len(counts) - 1, -1, -1):
            if counts[index] > 1 and sum(counts) > total:
                counts[index] -= 1
                break
        else:
            break
    if sum(counts) != total:
        counts[-1] += total - sum(counts)
    return counts


def render_melody(
    notes: list[Note],
    lyrics: str,
    controls: VoiceControls,
    bpm: float,
    sample_rate: int = SR_DEFAULT,
    seed: int = 0,
) -> np.ndarray:
    controls = controls.validated()
    if bpm <= 0:
        raise ValueError("tempo must be positive")
    sounding = [note for note in notes if note.midi is not None and note.dur_beats > 0]
    if not sounding:
        raise ValueError("the melody has no sounding notes")
    syllables = parse_lyrics(lyrics)
    if len(syllables) != len(sounding):
        preview_notes = [note.name for note in sounding]
        preview = alignment_preview(preview_notes[: len(syllables)], syllables)
        raise LyricAlignError(
            f"lyrics have {len(syllables)} syllables but the melody has {len(sounding)} notes.\n"
            f"Matched prefix:\n{preview}"
        )
    phone_lists = phones_for_syllables(syllables)
    end_beat = max(note.end_beat for note in notes)
    total = beats_to_samples(end_beat, bpm, sample_rate)
    curves = blank_curves(total, 112.0 * controls.pitch_scale())
    scale = controls.speed_scale()
    for note, phones in zip(sounding, phone_lists):
        start = beats_to_samples(note.start_beat, bpm, sample_rate)
        end = beats_to_samples(note.end_beat, bpm, sample_rate)
        end = min(total, max(end, start + 1))
        start = min(start, end - 1)
        length = end - start
        counts = allocate_samples(phones, length, scale, sample_rate)
        hz = midi_hz(note.midi) * controls.pitch_scale()
        amplitude = 0.55 + 0.45 * (max(1, min(127, note.velocity)) / 127.0)
        lookahead = next_vowel_targets(phones)
        cursor = start
        for phone, count, nxt in zip(phones, counts, lookahead):
            if count <= 0:
                continue
            micros = expand_phone(
                phone, count, hz, controls.mouth, controls.throat, amplitude, nxt
            )
            paint(micros, cursor, curves)
            cursor += count
    return synthesize(curves, sample_rate, seed)


def format_alignment(notes: list[Note], lyrics: str) -> str:
    sounding = [note for note in notes if note.midi is not None and note.dur_beats > 0]
    syllables: list[Syllable] = parse_lyrics(lyrics)
    if len(syllables) != len(sounding):
        raise LyricAlignError(
            f"lyrics have {len(syllables)} syllables but the melody has {len(sounding)} notes"
        )
    lines = [f"{note.name:<6} {note.dur_beats:g}  {syl.display}" for note, syl in zip(sounding, syllables)]
    return "\n".join(lines)
