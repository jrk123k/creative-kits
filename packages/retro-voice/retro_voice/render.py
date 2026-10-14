"""High-level speech, melody, duet, and demo rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from retro_voice.audio import mix_tracks, peak_normalize, write_wav
from retro_voice.beat import render_beat
from retro_voice.controls import (
    EffectChain,
    VoiceControls,
    effect_preset,
    voice_preset,
)
from retro_voice.demo_data import (
    BARS,
    BPM,
    HARMONY_LYRICS,
    HARMONY_NOTES,
    LEAD_LYRICS,
    LEAD_NOTES,
    SPOKEN,
)
from retro_voice.effects import apply_chain
from retro_voice.midi_io import read_midi_notes, write_midi
from retro_voice.notes import Note, parse_pitch
from retro_voice.score import dump_score, load_score, notes_from_pairs
from retro_voice.sing import render_melody
from retro_voice.speak import render_speech
from retro_voice.synth import SR_DEFAULT


def _silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros(max(0, int(round(seconds * sample_rate))))


def render_spoken_demo(sample_rate: int = SR_DEFAULT) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for preset_name, line in SPOKEN:
        chunks.append(
            render_speech(
                line,
                controls=voice_preset(preset_name),
                effects=effect_preset("sam"),
                sample_rate=sample_rate,
                seed=3,
            )
        )
        chunks.append(_silence(0.22, sample_rate))
    return peak_normalize(np.concatenate(chunks), 0.9)


def _notes_from_names(pairs: list[tuple[str, float]]) -> list[Note]:
    return notes_from_pairs([(parse_pitch(name), beats) for name, beats in pairs])


@dataclass
class Stem:
    name: str
    audio: np.ndarray
    gain: float


@dataclass
class DuetResult:
    stems: list[Stem]
    beat: np.ndarray | None
    mix: np.ndarray
    sample_rate: int
    bpm: float


def _resolve(path: str, root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate


def render_voice_notes(
    notes: list[Note],
    lyrics: str,
    controls: VoiceControls,
    effects: EffectChain,
    bpm: float,
    sample_rate: int,
    seed: int,
) -> np.ndarray:
    dry = render_melody(notes, lyrics, controls, bpm, sample_rate, seed)
    wet = apply_chain(dry, sample_rate, effects)
    return peak_normalize(wet, 0.85)


def render_duet_voices(
    voices: list[dict],
    bpm: float,
    sample_rate: int = SR_DEFAULT,
    effects: EffectChain | None = None,
    bars: int = 8,
    with_beat: bool = True,
    beat_gain: float = 0.48,
    root: Path | None = None,
) -> DuetResult:
    effects = effects if effects is not None else effect_preset("c64")
    root = root or Path(".")
    stems: list[Stem] = []
    for index, voice in enumerate(voices):
        controls = voice_preset(voice.get("preset", "sam"))
        overrides = {
            key: int(voice[key])
            for key in ("pitch", "speed", "mouth", "throat")
            if voice.get(key) is not None
        }
        if overrides:
            controls = VoiceControls(
                pitch=overrides.get("pitch", controls.pitch),
                speed=overrides.get("speed", controls.speed),
                mouth=overrides.get("mouth", controls.mouth),
                throat=overrides.get("throat", controls.throat),
            )
        if voice.get("midi"):
            notes, _file_bpm = read_midi_notes(
                str(_resolve(voice["midi"], root)),
                track=voice.get("track"),
                tempo_bpm=bpm,
            )
        elif voice.get("score"):
            notes, score_lyrics, score_tempo, score_controls = load_score(str(_resolve(voice["score"], root)))
            if voice.get("lyrics") is None and score_lyrics:
                voice = dict(voice)
                voice["lyrics"] = score_lyrics
            if not overrides and voice.get("preset") is None:
                controls = score_controls
            del score_tempo
        elif voice.get("notes"):
            notes = voice["notes"]
        else:
            raise ValueError(f"voice {voice.get('name', index)} needs midi, score, or notes")
        lyrics = voice.get("lyrics")
        if voice.get("lyrics_file") and not lyrics:
            lyrics = _resolve(voice["lyrics_file"], root).read_text(encoding="utf-8")
        if not lyrics:
            raise ValueError(f"voice {voice.get('name', index)} needs lyrics")
        audio = render_voice_notes(
            notes,
            lyrics,
            controls,
            effects,
            bpm,
            sample_rate,
            seed=int(voice.get("seed", index)),
        )
        stems.append(Stem(voice.get("name", f"voice{index+1}"), audio, float(voice.get("gain", 0.75))))
    beat_audio = None
    tracks = [stem.audio for stem in stems]
    gains = [stem.gain for stem in stems]
    if with_beat:
        raw = render_beat(bpm, sample_rate, bars=bars, seed=11)
        crunch = apply_chain(
            raw,
            sample_rate,
            EffectChain(bitcrush=10, downsample=2),
        )
        beat_audio = peak_normalize(crunch, 0.8)
        longest = max(len(track) for track in tracks) if tracks else len(beat_audio)
        if len(beat_audio) < longest:
            reps = int(np.ceil(longest / len(beat_audio)))
            beat_audio = np.tile(beat_audio, reps)[:longest]
        tracks.append(beat_audio)
        gains.append(beat_gain)
    mixed = peak_normalize(mix_tracks(tracks, gains), 0.95)
    return DuetResult(stems, beat_audio, mixed, sample_rate, bpm)


def write_duet(result: DuetResult, mix_path: str, stems_dir: str | None = None) -> None:
    write_wav(mix_path, result.mix, result.sample_rate)
    if stems_dir:
        folder = Path(stems_dir)
        folder.mkdir(parents=True, exist_ok=True)
        for stem in result.stems:
            write_wav(str(folder / f"{stem.name}.wav"), stem.audio, result.sample_rate)
        if result.beat is not None:
            write_wav(str(folder / "beat.wav"), result.beat, result.sample_rate)


def build_song_demo(out_dir: str, sample_rate: int = SR_DEFAULT) -> DuetResult:
    """Write MIDI, scores, and a duet mixed from those MIDI files."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    lead_notes = _notes_from_names(LEAD_NOTES)
    harmony_notes = _notes_from_names(HARMONY_NOTES)
    write_midi(str(folder / "lead.mid"), lead_notes, BPM, "lead")
    write_midi(str(folder / "harmony.mid"), harmony_notes, BPM, "harmony")
    (folder / "lead.txt").write_text(LEAD_LYRICS + "\n", encoding="utf-8")
    (folder / "harmony.txt").write_text(HARMONY_LYRICS + "\n", encoding="utf-8")
    dump_score(str(folder / "lead.rvscore"), lead_notes, LEAD_LYRICS, BPM, voice_preset("lead"), "lead")
    dump_score(
        str(folder / "harmony.rvscore"),
        harmony_notes,
        HARMONY_LYRICS,
        BPM,
        voice_preset("harmony"),
        "harmony",
    )
    spec = {
        "tempo": BPM,
        "bars": BARS,
        "beat": True,
        "beat_gain": 0.48,
        "effects": "c64",
        "voices": [
            {
                "name": "lead",
                "midi": "lead.mid",
                "lyrics_file": "lead.txt",
                "preset": "lead",
                "gain": 0.82,
                "seed": 0,
            },
            {
                "name": "harmony",
                "midi": "harmony.mid",
                "lyrics_file": "harmony.txt",
                "preset": "harmony",
                "gain": 0.7,
                "seed": 1,
            },
        ],
    }
    (folder / "duet.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    result = render_duet_voices(
        spec["voices"],
        bpm=BPM,
        sample_rate=sample_rate,
        effects=effect_preset("c64"),
        bars=BARS,
        with_beat=True,
        beat_gain=0.48,
        root=folder,
    )
    write_duet(result, str(folder / "demo_song.wav"), str(folder / "stems"))
    return result


def build_spoken_demo(path: str, sample_rate: int = SR_DEFAULT) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_wav(path, render_spoken_demo(sample_rate), sample_rate)


def build_all_demos(out_dir: str, sample_rate: int = SR_DEFAULT) -> None:
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    build_spoken_demo(str(folder / "demo_spoken.wav"), sample_rate)
    build_song_demo(folder, sample_rate)
