"""Command line for It's Not What We Thought... robot vocals."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from retro_voice import __version__
from retro_voice.audio import write_wav
from retro_voice.controls import EffectChain, VoiceControls, effect_preset, voice_preset
from retro_voice.lyrics import LyricAlignError
from retro_voice.midi_io import MidiError, read_midi_notes
from retro_voice.render import (
    build_all_demos,
    build_song_demo,
    build_spoken_demo,
    render_duet_voices,
    render_voice_notes,
    write_duet,
)
from retro_voice.score import load_score
from retro_voice.sing import format_alignment
from retro_voice.speak import render_speech
from retro_voice.synth import SR_DEFAULT


def _voice_from_args(
    args: argparse.Namespace,
    fallback: VoiceControls | None = None,
    default_name: str = "sam",
) -> VoiceControls:
    if getattr(args, "preset", None):
        controls = voice_preset(args.preset)
    elif fallback is not None:
        controls = fallback
    else:
        controls = voice_preset(default_name)
    updates = {}
    for key in ("pitch", "speed", "mouth", "throat"):
        value = getattr(args, key, None)
        if value is not None:
            updates[key] = value
    if not updates:
        return controls.validated()
    return VoiceControls(
        pitch=updates.get("pitch", controls.pitch),
        speed=updates.get("speed", controls.speed),
        mouth=updates.get("mouth", controls.mouth),
        throat=updates.get("throat", controls.throat),
    ).validated()


def _effects_touched(args: argparse.Namespace) -> bool:
    if getattr(args, "effects", None):
        return True
    names = ("bitcrush", "downsample", "filter", "cutoff", "resonance", "ring", "ring_mix", "chorus")
    return any(getattr(args, name, None) is not None for name in names)


def _effects_from_args(args: argparse.Namespace) -> EffectChain:
    chain = effect_preset(getattr(args, "effects", None) or "off")
    updates: dict = {}
    mapping = {
        "bitcrush": "bitcrush",
        "downsample": "downsample",
        "filter": "filter_mode",
        "cutoff": "cutoff",
        "resonance": "resonance",
        "ring": "ring_hz",
        "ring_mix": "ring_mix",
        "chorus": "chorus_mix",
    }
    for arg_name, field in mapping.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            updates[field] = value
    if not updates:
        return chain
    data = chain.__dict__.copy()
    data.update(updates)
    return EffectChain(**data).validated()


def _add_voice_flags(parser: argparse.ArgumentParser, default_preset: str | None) -> None:
    parser.add_argument("--preset", default=default_preset, help="sam, lead, harmony, deep, or bright")
    parser.add_argument("--pitch", type=int, help="0–255, 64 is the written pitch")
    parser.add_argument("--speed", type=int, help="0–255, 72 is normal, higher is slower")
    parser.add_argument("--mouth", type=int, help="0–255, 128 is neutral, higher is brighter")
    parser.add_argument("--throat", type=int, help="0–255, 128 is neutral, higher raises the first formant")


def _add_effect_flags(parser: argparse.ArgumentParser, default: str | None) -> None:
    parser.add_argument("--effects", default=default, help="off, sam, or c64")
    parser.add_argument("--bitcrush", type=int, help="bit depth, 0 or 16 leaves the signal alone")
    parser.add_argument("--downsample", type=int, help="sample-and-hold factor, 1 is off")
    parser.add_argument("--filter", choices=["off", "lp", "bp", "hp"])
    parser.add_argument("--cutoff", type=float, help="filter cutoff in Hz")
    parser.add_argument("--resonance", type=float, help="0 to 0.98")
    parser.add_argument("--ring", type=float, help="ring-mod carrier in Hz, 0 is off")
    parser.add_argument("--ring-mix", type=float, dest="ring_mix")
    parser.add_argument("--chorus", type=float, help="chorus wet mix, 0 to 1")


def _cmd_say(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip()
    if not text:
        raise ValueError("say needs text or a phoneme string")
    audio = render_speech(
        text,
        controls=_voice_from_args(args),
        effects=_effects_from_args(args),
        sample_rate=args.sample_rate,
        seed=args.seed,
        phonemes=args.phonemes,
    )
    write_wav(args.output, audio, args.sample_rate)
    _report(args.output, len(audio), args.sample_rate)
    return 0


def _load_melody(args: argparse.Namespace) -> tuple[list, str, float, VoiceControls]:
    lyrics = args.lyrics
    if args.lyrics_file:
        lyrics = Path(args.lyrics_file).read_text(encoding="utf-8")
    if args.midi:
        notes, file_bpm = read_midi_notes(args.midi, track=args.track, tempo_bpm=args.tempo)
        bpm = args.tempo or file_bpm
        controls = _voice_from_args(args, default_name="lead")
        if not lyrics:
            raise ValueError("singing from MIDI needs --lyrics or --lyrics-file")
        return notes, lyrics, bpm, controls
    if args.score:
        notes, score_lyrics, score_tempo, score_controls = load_score(args.score)
        if lyrics and score_lyrics:
            raise ValueError("lyrics were passed on the command line and also written in the score")
        lyrics = lyrics or score_lyrics
        if not lyrics:
            raise ValueError("the score has no lyrics; pass --lyrics")
        bpm = args.tempo or score_tempo or 120.0
        controls = _voice_from_args(args, fallback=score_controls)
        return notes, lyrics, bpm, controls
    raise ValueError("sing needs --midi or --score")


def _cmd_sing(args: argparse.Namespace) -> int:
    notes, lyrics, bpm, controls = _load_melody(args)
    if args.align:
        print(format_alignment(notes, lyrics))
    audio = render_voice_notes(
        notes,
        lyrics,
        controls,
        _effects_from_args(args),
        bpm,
        args.sample_rate,
        seed=args.seed,
    )
    write_wav(args.output, audio, args.sample_rate)
    _report(args.output, len(audio), args.sample_rate)
    return 0


def _cmd_duet(args: argparse.Namespace) -> int:
    import json

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    bpm = args.tempo or float(spec.get("tempo") or 120)
    effects = effect_preset(spec.get("effects", "c64"))
    if _effects_touched(args):
        effects = _effects_from_args(args)
    result = render_duet_voices(
        spec["voices"],
        bpm=bpm,
        sample_rate=args.sample_rate,
        effects=effects,
        bars=int(spec.get("bars", args.bars)),
        with_beat=bool(spec.get("beat", args.beat)),
        beat_gain=float(spec.get("beat_gain", 0.48)),
        root=spec_path.parent,
    )
    write_duet(result, args.output, args.stems_dir)
    _report(args.output, len(result.mix), args.sample_rate)
    if args.stems_dir:
        print(f"stems in {args.stems_dir}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    if args.which == "spoken":
        dest = args.output or str(Path(args.out_dir) / "demo_spoken.wav")
        build_spoken_demo(dest, args.sample_rate)
        print(f"wrote {dest}")
        return 0
    if args.which == "song":
        out_dir = Path(args.out_dir)
        result = build_song_demo(out_dir, args.sample_rate)
        if args.output and Path(args.output) != out_dir / "demo_song.wav":
            write_wav(args.output, result.mix, args.sample_rate)
            print(f"wrote {args.output}")
        print(f"wrote {out_dir / 'demo_song.wav'}")
        print(f"MIDI lead {out_dir / 'lead.mid'}, harmony {out_dir / 'harmony.mid'}")
        return 0
    build_all_demos(args.out_dir, args.sample_rate)
    print(f"wrote {args.out_dir}/demo_spoken.wav")
    print(f"wrote {args.out_dir}/demo_song.wav")
    print(f"stems in {args.out_dir}/stems")
    return 0


def _report(path: str, samples: int, sample_rate: int) -> None:
    seconds = samples / sample_rate if sample_rate else 0
    print(f"wrote {path} ({seconds:.2f}s, {sample_rate} Hz)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retro-voice",
        description="SAM-style robot vocals for It's Not What We Thought...",
    )
    parser.add_argument("--version", action="version", version=f"retro-voice {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    say = sub.add_parser("say", help="speak a line, or a phoneme string")
    say.add_argument("text", nargs="+")
    say.add_argument("-o", "--output", required=True)
    say.add_argument("--phonemes", action="store_true", help="treat the text as ARPAbet or SAM phonemes")
    say.add_argument("--sample-rate", type=int, default=SR_DEFAULT)
    say.add_argument("--seed", type=int, default=0)
    _add_voice_flags(say, "sam")
    _add_effect_flags(say, "sam")
    say.set_defaults(func=_cmd_say)

    sing = sub.add_parser("sing", help="sing a MIDI file or a note score")
    sing.add_argument("-o", "--output", required=True)
    sing.add_argument("--midi", help="melody MIDI file")
    sing.add_argument("--score", help="rvscore or JSON note score")
    sing.add_argument("--lyrics", help="syllable line, with hyphens and melisma -")
    sing.add_argument("--lyrics-file")
    sing.add_argument("--tempo", type=float, help="BPM lock; overrides the MIDI or score tempo")
    sing.add_argument("--track", type=int, default=None, help="MIDI track index")
    sing.add_argument("--align", action="store_true", help="print syllable-to-note mapping")
    sing.add_argument("--sample-rate", type=int, default=SR_DEFAULT)
    sing.add_argument("--seed", type=int, default=0)
    _add_voice_flags(sing, None)
    _add_effect_flags(sing, "c64")
    sing.set_defaults(func=_cmd_sing)

    duet = sub.add_parser("duet", help="render two or more voices, stems, and a mix")
    duet.add_argument("--spec", required=True, help="JSON file describing the voices")
    duet.add_argument("-o", "--output", required=True, help="mix WAV")
    duet.add_argument("--stems-dir", help="where to write one WAV per voice plus beat.wav")
    duet.add_argument("--tempo", type=float)
    duet.add_argument("--bars", type=int, default=8)
    duet.add_argument("--beat", action="store_true", default=False)
    duet.add_argument("--sample-rate", type=int, default=SR_DEFAULT)
    _add_effect_flags(duet, None)
    duet.set_defaults(func=_cmd_duet)

    demo = sub.add_parser("demo", help="render the spoken line and the 8-bar MIDI duet")
    demo.add_argument("which", choices=["spoken", "song", "all"])
    demo.add_argument("-o", "--output")
    demo.add_argument("--out-dir", default="demos")
    demo.add_argument("--sample-rate", type=int, default=SR_DEFAULT)
    demo.set_defaults(func=_cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (LyricAlignError, MidiError, OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
