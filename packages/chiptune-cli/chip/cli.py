"""Command line. ``chip render``, ``chip preset``, ``chip presets``, ``chip wavetables``."""

from __future__ import annotations

import argparse
import sys

from chip.psg import SR
from chip.render import list_presets, render_preset, render_score, write_audio
from chip.score import ScoreError
from chip.tables import STOCK, STOCK_NAMES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chip",
        description="Render a HuC6280 / PC Engine chiptune score to WAV or OGG.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="render an MML score file")
    render.add_argument("score", help="path to a .mml score")
    render.add_argument("-o", "--output", required=True, help="output .wav or .ogg")
    _common(render)

    preset = sub.add_parser("preset", help="render a built-in preset")
    preset.add_argument("name", help="preset name, for example beam_hum")
    preset.add_argument("-o", "--output", required=True, help="output .wav or .ogg")
    _common(preset)

    sub.add_parser("presets", help="list preset names")
    sub.add_parser("wavetables", help="print the stock 32-sample wavetables")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "presets":
            for name in list_presets():
                print(name)
            return 0
        if args.cmd == "wavetables":
            _print_tables()
            return 0
        seamless = None
        if args.seamless:
            seamless = True
        elif args.no_seamless:
            seamless = False
        kwargs = {
            "loops": args.loops,
            "loop_length": args.loop_length,
            "seamless": seamless,
            "tempo": args.tempo,
            "sr": args.sr,
        }
        if args.cmd == "render":
            audio = render_score(args.score, **kwargs)
        else:
            audio = render_preset(args.name, **kwargs)
        write_audio(args.output, audio, args.sr)
    except ScoreError as exc:
        print(f"chip: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"chip: {exc}", file=sys.stderr)
        return 1
    return 0


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--loops", type=int, default=1, help="how many times to play the loop region (default 1)")
    parser.add_argument(
        "--loop-length",
        type=float,
        default=None,
        metavar="SEC",
        help="repeat the loop until this many seconds, then trim to it",
    )
    parser.add_argument("--tempo", type=float, default=None, help="override the score BPM")
    parser.add_argument("--sr", type=int, default=SR, help="sample rate (default 44100)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seamless", action="store_true", help="crossfade the loop wrap")
    group.add_argument("--no-seamless", action="store_true", help="do not crossfade, even if the score asks")


def _print_tables() -> None:
    by_id = {i: name for name, i in STOCK_NAMES.items()}
    for wid in sorted(STOCK):
        samples = ",".join(str(int(v)) for v in STOCK[wid])
        print(f"{wid} {by_id[wid]}")
        print(samples)


if __name__ == "__main__":
    raise SystemExit(main())
