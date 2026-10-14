import numpy as np

from retro_voice.controls import VoiceControls, effect_preset, voice_preset
from retro_voice.lyrics import LyricAlignError
from retro_voice.notes import Note, beats_to_samples
from retro_voice.render import render_duet_voices, render_voice_notes
from retro_voice.score import dump_score, load_score
from retro_voice.pitch import estimate_f0
from retro_voice.sing import render_melody
from retro_voice.synth import SR_DEFAULT

import pytest


def test_demo_lead_fills_eight_bars():
    from retro_voice.demo_data import BPM, LEAD_LYRICS, LEAD_NOTES
    from retro_voice.render import _notes_from_names

    notes = _notes_from_names(LEAD_NOTES)
    audio = render_melody(notes, LEAD_LYRICS, voice_preset("lead"), bpm=BPM, sample_rate=SR_DEFAULT)
    assert len(audio) == beats_to_samples(32, BPM, SR_DEFAULT)
    # "thought" is the half-note A4 at beat 4, transposed by the lead preset.
    start = beats_to_samples(4.5, BPM, SR_DEFAULT)
    end = beats_to_samples(5.5, BPM, SR_DEFAULT)
    heard = estimate_f0(audio[start:end], SR_DEFAULT, fmax=1000)
    target = 440.0 * voice_preset("lead").pitch_scale()
    assert abs(heard - target) < 12


def test_sung_pitch_locks_to_the_note():
    notes = [Note(69, 0, 2)]
    audio = render_melody(notes, "la", VoiceControls(), bpm=120, sample_rate=SR_DEFAULT, seed=0)
    assert len(audio) == beats_to_samples(2, 120, SR_DEFAULT)
    middle = audio[len(audio) // 5 : len(audio) // 2]
    f0 = estimate_f0(middle, SR_DEFAULT, fmax=800)
    assert abs(f0 - 440.0) < 8

    shifted = render_melody(notes, "la", VoiceControls(pitch=88), bpm=120, sample_rate=SR_DEFAULT)
    # pitch 88 is six semitones above center: 440 * 2 ** 0.5.
    target = 440.0 * (2.0 ** (6 / 12))
    heard = estimate_f0(shifted[len(shifted) // 5 : len(shifted) // 2], SR_DEFAULT, fmax=1200)
    assert abs(heard - target) < 12


def test_melisma_changes_pitch_and_mismatch_errors():
    notes = [Note(69, 0, 1), Note(72, 1, 1)]
    audio = render_melody(notes, "la -", VoiceControls(), bpm=120, sample_rate=SR_DEFAULT)
    half = len(audio) // 2
    first = estimate_f0(audio[half // 4 : half // 2], SR_DEFAULT)
    second = estimate_f0(audio[half + half // 4 : half + half // 2], SR_DEFAULT, fmax=1000)
    assert abs(first - 440) < 10
    assert abs(second - 523.25) < 12
    with pytest.raises(LyricAlignError):
        render_melody(notes, "la", VoiceControls(), bpm=120)


def test_tempo_lock_and_two_voice_stems(tmp_path):
    notes = [Note(60, 0, 1), Note(64, 1, 1), Note(67, 2, 2)]
    quarter = beats_to_samples(4, 100, SR_DEFAULT)
    audio = render_melody(notes, "do re mi", VoiceControls(), bpm=100, sample_rate=SR_DEFAULT)
    assert len(audio) == quarter

    fast = render_melody(notes, "do re mi", VoiceControls(), bpm=200, sample_rate=SR_DEFAULT)
    assert len(fast) == beats_to_samples(4, 200, SR_DEFAULT)
    assert len(fast) < len(audio) * 0.6

    score = tmp_path / "line.rvscore"
    dump_score(score, notes, "do re mi", 100, voice_preset("lead"), preset_name="lead")
    loaded, lyrics, tempo, controls = load_score(score)
    assert tempo == 100
    assert controls.mouth == voice_preset("lead").mouth
    assert lyrics.split() == ["do", "re", "mi"]
    assert len(loaded) == 3


def test_dump_preserves_hyphen_words(tmp_path):
    notes = [Note(64, 0, 1), Note(65, 1, 1), Note(67, 2, 1), Note(64, 3, 1)]
    path = tmp_path / "lead.rvscore"
    dump_score(path, notes, "to-night la -", 90, VoiceControls())
    _notes, lyrics, tempo, _controls = load_score(path)
    assert tempo == 90
    from retro_voice.lyrics import parse_lyrics, phones_for_syllables

    syllables = parse_lyrics(lyrics)
    assert [syl.display for syl in syllables] == ["to", "night", "la", "-"]
    phones = phones_for_syllables(syllables)
    assert phones[0][0].name == "T" and phones[1][0].name == "N"
    assert phones[3][0].name == phones[2][-1].name or phones[3][0].name in {"AA", "AH"}


def test_duet_stems_are_distinct(tmp_path):
    from retro_voice.midi_io import write_midi

    lead_path = tmp_path / "lead.mid"
    harm_path = tmp_path / "harm.mid"
    write_midi(lead_path, [Note(72, 0, 2)], tempo_bpm=120)
    write_midi(harm_path, [Note(60, 0, 2)], tempo_bpm=120)
    result = render_duet_voices(
        [
            {"name": "lead", "midi": str(lead_path), "lyrics": "la", "preset": "lead", "gain": 0.8, "seed": 0},
            {"name": "harmony", "midi": str(harm_path), "lyrics": "lo", "preset": "harmony", "gain": 0.7, "seed": 1},
        ],
        bpm=120,
        effects=effect_preset("off"),
        with_beat=True,
        bars=1,
        beat_gain=0.4,
    )
    assert [stem.name for stem in result.stems] == ["lead", "harmony"]
    assert len(result.stems[0].audio) == len(result.stems[1].audio)
    assert result.beat is not None and len(result.beat) >= len(result.stems[0].audio)
    assert not np.allclose(result.stems[0].audio, result.stems[1].audio)
    assert len(result.mix) == max(len(result.beat), len(result.stems[0].audio))
    lead_f0 = estimate_f0(result.stems[0].audio[4000:12000], SR_DEFAULT, fmax=1200)
    harm_f0 = estimate_f0(result.stems[1].audio[4000:12000], SR_DEFAULT, fmax=800)
    # Lead preset is +2 semitones on C5 (523.25 -> ~587). Harmony is -3 semitones on C4.
    assert lead_f0 > harm_f0 * 1.4
    rendered = render_voice_notes(
        [Note(69, 0, 1)],
        "la",
        VoiceControls(),
        effect_preset("c64"),
        120,
        SR_DEFAULT,
        seed=0,
    )
    assert np.max(np.abs(rendered)) > 0.2
