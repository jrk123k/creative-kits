"""Command line for the It's Not What We Thought video tools."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from inwwt import __version__
from inwwt.crt import CRTParams
from inwwt.footage import ERA_CLIPS, write_synthetic_clip
from inwwt.looks import LookParams, apply_look
from inwwt.palette import get_palette
from inwwt.transition import TransitionConfig, render_transition
from inwwt.video import FrameReader, FrameWriter, duration_of, is_still


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inwwt",
        description="Era transitions, a C64 screen, and split-screen templates for It's Not What We Thought...",
    )
    parser.add_argument("--version", action="version", version=f"inwwt {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    transition = sub.add_parser("transition", help="animate clip A down to C64 and back up into clip B")
    transition.add_argument("--a", required=True, help="clip or still that degrades")
    transition.add_argument("--b", required=True, help="clip or still revealed on the way back")
    transition.add_argument("--out", required=True)
    transition.add_argument("--duration", type=float, default=8.0)
    transition.add_argument("--fps", type=float, default=24.0)
    transition.add_argument("--width", type=int, default=1280)
    transition.add_argument("--height", type=int, default=720)
    transition.add_argument("--curve", default="smoothstep")
    transition.add_argument("--dither", default="bayer", choices=["bayer", "floyd", "nearest"])
    transition.add_argument("--palette", default="pepto", choices=["pepto", "colodore"])
    transition.add_argument("--bayer-size", type=int, default=4)
    transition.add_argument("--spread", type=float, default=48.0)
    transition.add_argument("--c64-width", type=int, default=320)
    transition.add_argument(
        "--phases",
        default="",
        help="six increasing fractions: crt, pixel, dither, hold, undither, unpixel",
    )
    transition.add_argument("--curvature", type=float, default=0.22)
    transition.add_argument("--scanline", type=float, default=0.50)
    transition.add_argument("--bloom", type=float, default=0.40)
    transition.add_argument("--bloom-radius", type=float, default=8.0)
    transition.add_argument("--vignette", type=float, default=0.45)
    transition.add_argument("--chroma", type=float, default=1.5)
    transition.add_argument("--crf", type=int, default=20)
    transition.add_argument("--preset", default="medium")

    look = sub.add_parser("look", help="apply one stage (crt, pixelate, dither, c64, full) to a clip")
    look.add_argument("--input", required=True)
    look.add_argument("--out", required=True)
    look.add_argument("--look", required=True, choices=["crt", "pixelate", "dither", "c64", "full"])
    look.add_argument("--duration", type=float, default=0.0, help="required for stills; trims video")
    look.add_argument("--fps", type=float, default=24.0)
    look.add_argument("--width", type=int, default=0)
    look.add_argument("--height", type=int, default=0)
    look.add_argument("--dither", default="bayer", choices=["bayer", "floyd", "nearest"])
    look.add_argument("--palette", default="pepto", choices=["pepto", "colodore"])
    look.add_argument("--bayer-size", type=int, default=4)
    look.add_argument("--spread", type=float, default=48.0)
    look.add_argument("--pixel-scale", type=int, default=6)
    look.add_argument("--c64-width", type=int, default=320)
    look.add_argument("--crf", type=int, default=20)
    look.add_argument("--preset", default="medium")

    screen = sub.add_parser("c64", help="render a typed C64 BASIC screen from a script")
    screen.add_argument("--script", required=True)
    screen.add_argument("--out", required=True)
    screen.add_argument("--palette", default="pepto", choices=["pepto", "colodore"])
    screen.add_argument("--fps", type=float, default=30.0)
    screen.add_argument("--blink", default="ntsc", help="ntsc, pal, or a period in seconds")
    screen.add_argument("--tail", type=float, default=1.5, help="seconds of cursor after the last key")
    screen.add_argument("--width", type=int, default=1920)
    screen.add_argument("--height", type=int, default=1080)
    screen.add_argument("--scale", type=int, default=5, help="integer nearest-neighbor scale of the text matrix")
    screen.add_argument("--cps", type=float, default=8.0)
    screen.add_argument("--crf", type=int, default=18)
    screen.add_argument("--preset", default="medium")

    comp = sub.add_parser("composite", help="render a YAML split-screen or three-way layout")
    comp.add_argument("--config", required=True)
    comp.add_argument("--out", required=True)

    demos = sub.add_parser("demos", help="render the four sample mp4s from generated footage")
    demos.add_argument("--out", default="demos")
    demos.add_argument("--transition-dither", default="bayer", choices=["bayer", "floyd"])
    return parser


def _phases(text: str) -> dict[str, float]:
    if not text.strip():
        return {}
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 6:
        raise SystemExit("--phases needs six comma-separated fractions")
    keys = ("crt_in_end", "pixel_end", "dither_end", "hold_end", "undither_end", "unpixel_end")
    return dict(zip(keys, parts))


def _cmd_transition(args: argparse.Namespace) -> None:
    cfg = TransitionConfig(
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        curve=args.curve,
        look=LookParams(
            palette=args.palette,
            dither=args.dither,
            bayer_size=args.bayer_size,
            spread=args.spread,
            c64_width=args.c64_width,
        ),
        crt=CRTParams(
            curvature=args.curvature,
            scanline=args.scanline,
            bloom=args.bloom,
            bloom_radius=args.bloom_radius,
            vignette=args.vignette,
            chroma=args.chroma,
        ),
        crf=args.crf,
        preset=args.preset,
        **_phases(args.phases),
    )
    render_transition(args.a, args.b, args.out, cfg)


def _cmd_look(args: argparse.Namespace) -> None:
    from inwwt.video import video_size

    if args.width and args.height:
        width, height = args.width, args.height
    elif is_still(args.input):
        width, height = 1280, 720
    else:
        width, height = video_size(args.input)
    if args.duration > 0:
        duration = args.duration
    elif is_still(args.input):
        raise SystemExit("--duration is required when --input is a still")
    else:
        duration = duration_of(args.input) or 5.0
    count = max(1, int(round(duration * args.fps)))
    params = LookParams(
        palette=args.palette,
        dither=args.dither,
        bayer_size=args.bayer_size,
        spread=args.spread,
        pixel_scale=args.pixel_scale,
        c64_width=args.c64_width,
    )
    reader = FrameReader(args.input, width, height, args.fps, count)
    writer = FrameWriter(args.out, width, height, args.fps, crf=args.crf, preset=args.preset)
    cache = None
    try:
        for _ in range(count):
            frame, cache = apply_look(reader.read(), args.look, params, cache)
            writer.write(frame)
    finally:
        reader.close()
        writer.close()


def _cmd_c64(args: argparse.Namespace) -> None:
    from inwwt.c64screen import render_c64_video

    render_c64_video(
        args.script,
        args.out,
        palette_name=args.palette,
        fps=args.fps,
        blink=args.blink,
        tail=args.tail,
        out_width=args.width,
        out_height=args.height,
        scale=args.scale,
        crf=args.crf,
        preset=args.preset,
        cps=args.cps,
    )


def _cmd_composite(args: argparse.Namespace) -> None:
    from inwwt.compositor import load_config, render_composite

    cfg = load_config(args.config)
    render_composite(cfg, args.out)


def _cmd_demos(args: argparse.Namespace) -> None:
    from inwwt.c64screen import render_c64_video
    from inwwt.compositor import load_config, render_composite

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent.parent
    script = root / "examples" / "c64_boot.script"
    width, height, fps = 1920, 1080, 24.0
    with tempfile.TemporaryDirectory(prefix="inwwt-src-") as tmp:
        clips = {}
        for name, spec in ERA_CLIPS.items():
            path = str(Path(tmp) / f"{name}.mp4")
            print(f"generating {name}", flush=True)
            write_synthetic_clip(
                path,
                title=spec["title"],
                top=spec["top"],
                bottom=spec["bottom"],
                accent=spec["accent"],
                duration=6.5,
                width=width,
                height=height,
                fps=fps,
                tone=spec["tone"],
            )
            clips[name] = path
        print("transition", flush=True)
        render_transition(
            clips["future"],
            clips["now"],
            str(out / "transition_demo.mp4"),
            TransitionConfig(
                duration=6.0,
                fps=fps,
                width=width,
                height=height,
                curve="smoothstep",
                look=LookParams(palette="pepto", dither=args.transition_dither, c64_width=320),
                crf=22,
                preset="veryfast",
            ),
        )
        print("c64 screen", flush=True)
        render_c64_video(
            str(script),
            str(out / "c64_screen_demo.mp4"),
            palette_name="pepto",
            fps=30,
            blink="ntsc",
            tail=1.2,
            crf=20,
            preset="veryfast",
            cps=12,
        )
        split_yaml = _demo_yaml(
            tmp,
            layout="split-vertical",
            panels=[
                (clips["then"], "1984", "c64"),
                (clips["now"], "2026", "none"),
            ],
            audio_index=0,
            width=width,
            height=height,
            fps=fps,
            duration=5.0,
        )
        three_yaml = _demo_yaml(
            tmp,
            layout="triptych",
            panels=[
                (clips["then"], "1984", "c64"),
                (clips["now"], "2026", "none"),
                (clips["future"], "FUTURE", "crt"),
            ],
            audio_index=1,
            width=width,
            height=height,
            fps=fps,
            duration=5.0,
        )
        print("splitscreen", flush=True)
        render_composite(load_config(split_yaml), str(out / "splitscreen_demo.mp4"))
        print("threeway", flush=True)
        render_composite(load_config(three_yaml), str(out / "threeway_demo.mp4"))
    print(f"demos written to {out.resolve()}", flush=True)


def _demo_yaml(tmp: str, *, layout, panels, audio_index, width, height, fps, duration) -> str:
    lines = [
        "output:",
        f"  width: {width}",
        f"  height: {height}",
        f"  fps: {fps}",
        f"  duration: {duration}",
        "  crf: 22",
        "  preset: veryfast",
        f"layout: {layout}",
        "divider:",
        "  px: 8",
        '  color: "101820"',
        "labels:",
        "  show: true",
        "  size: 42",
        "  position: bottom",
        "audio:",
        "  from: panel",
        f"  index: {audio_index}",
        "panels:",
    ]
    for src, label, look in panels:
        lines += [
            f"  - src: {src}",
            f"    label: {label!r}",
            f"    look: {look}",
            "    dither: bayer",
            "    palette: pepto",
        ]
    # !r on a label uses Python quotes. YAML accepts single quotes. A label
    # like 1984 is fine. FUTURE is fine. Avoid labels with quotes.
    path = Path(tmp) / f"{layout}.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def main(argv: list[str] | None = None) -> None:
    # Touch the palette table so a bad install fails before ffmpeg starts.
    get_palette("pepto")
    args = _parser().parse_args(argv)
    commands = {
        "transition": _cmd_transition,
        "look": _cmd_look,
        "c64": _cmd_c64,
        "composite": _cmd_composite,
        "demos": _cmd_demos,
    }
    try:
        commands[args.cmd](args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
