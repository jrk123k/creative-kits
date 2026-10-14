"""Command line. ``python -m spritepack pack frames -o out``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spritepack import __version__
from spritepack.adapt import adapt_file
from spritepack.anchors import parse_anchor_token
from spritepack.build import pack_folder, preview_file, unpack_folder
from spritepack.colors import parse_color
from spritepack.errors import SpritePackError
from spritepack.meta import read


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spritepack",
        description="Pack pixel frames into one atlas, a JSON file, and GIF/MP4 previews.",
    )
    parser.add_argument("--version", action="version", version=f"kit-sprite-packer {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pack = sub.add_parser("pack", help="pack a folder of PNG frames")
    pack.add_argument("folder", type=Path)
    pack.add_argument("-o", "--out", type=Path, required=True)
    pack.add_argument("--name", help="atlas file stem (default: the folder name)")
    pack.add_argument("--padding", type=int, default=0, help="empty pixels between frames and at the edge")
    pack.add_argument("--max-width", type=int, default=4096, help="row width before the shelf wraps (default 4096)")
    pack.add_argument("--fps", type=int, default=30, help="film fps used to turn hold into milliseconds (default 30)")
    pack.add_argument("--hold", type=int, default=4, help="default frames per pose, matching the intro kit (default 4)")
    pack.add_argument("--duration-ms", type=float, default=None, help="default pose length in milliseconds")
    pack.add_argument("--anchor", default="bottom-center", help="preset or x,y (default bottom-center)")
    pack.add_argument("--background", help="#rrggbb, r,g,b, or an image path")
    pack.add_argument("--scale", type=int, default=4, help="integer preview scale (default 4)")
    pack.add_argument("--place", action="append", default=[], help="preview point x,y or name:x,y")
    pack.add_argument("--place-space", choices=("anchor", "top-left"), default="anchor")
    pack.add_argument("--kit-place", help="where the anchor sits on the 256×224 kit plate, x,y")
    pack.add_argument("--sidecar", type=Path, help="sprites.json or a Pixel Studio manifest.json")
    pack.add_argument("--frame-duration", action="append", default=[], metavar="FILE=MS")
    pack.add_argument("--frame-anchor", action="append", default=[], metavar="FILE=X,Y")
    pack.add_argument("--no-preview", action="store_true")
    pack.add_argument("--no-gif", action="store_true")
    pack.add_argument("--no-mp4", action="store_true")

    unpack = sub.add_parser("unpack", help="crop the atlas back into frames")
    unpack.add_argument("json", type=Path)
    unpack.add_argument("-o", "--out", type=Path, required=True)

    preview = sub.add_parser("preview", help="write GIF and MP4 previews from an atlas JSON")
    preview.add_argument("json", type=Path)
    preview.add_argument("-o", "--out", type=Path, required=True)
    preview.add_argument("--scale", type=int, default=None)
    preview.add_argument("--background", default=None)
    preview.add_argument("--no-gif", action="store_true")
    preview.add_argument("--no-mp4", action="store_true")

    adapt = sub.add_parser("adapt", help="write an intro-kit project that loads the frames")
    adapt.add_argument("json", type=Path)
    adapt.add_argument("-o", "--out", type=Path, required=True)
    adapt.add_argument("--place", action="append", default=[], help="kit anchor point x,y or name:x,y")
    adapt.add_argument("--plate", type=Path, help="256×224 background for sprite scenes")
    adapt.add_argument("--plate-color", default="0,0,36")
    adapt.add_argument("--name", default="kit-sprites")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "pack":
            _cmd_pack(args)
        elif args.cmd == "unpack":
            _cmd_unpack(args)
        elif args.cmd == "preview":
            _cmd_preview(args)
        elif args.cmd == "adapt":
            _cmd_adapt(args)
        else:
            parser.error(f"unknown command {args.cmd}")
    except SpritePackError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _cmd_pack(args) -> None:
    default_place, named = _places(args.place)
    built = pack_folder(
        args.folder,
        args.out,
        name=args.name,
        padding=args.padding,
        max_width=args.max_width,
        fps=args.fps,
        hold=args.hold,
        duration_ms=args.duration_ms,
        anchor=parse_anchor_token(args.anchor) if "," in args.anchor else args.anchor,
        background=args.background,
        scale=args.scale,
        place=default_place,
        place_space=args.place_space,
        places=named,
        kit_place=_xy(args.kit_place) if args.kit_place else None,
        sidecar_path=args.sidecar,
        frame_durations=_pairs(args.frame_duration, float, "duration"),
        frame_anchors=_anchor_pairs(args.frame_anchor),
        gif=not args.no_preview and not args.no_gif,
        mp4=not args.no_preview and not args.no_mp4,
    )
    meta = built.meta
    print(
        f"{meta.image}: {len(meta.frames)} frames, {meta.size[0]}×{meta.size[1]}, "
        f"padding {meta.padding}, {meta.fps} fps"
    )
    for anim in meta.animations:
        frames = meta.playback(anim)
        holds = ", ".join(str(frame.hold_frames) for frame in frames)
        anchor = frames[0].anchor
        print(
            f"  {anim.name}: {anim.kind}, {len(frames)} frames, "
            f"hold [{holds}], anchor {anchor[0]},{anchor[1]}"
        )
    print(f"wrote {built.atlas_path}")
    print(f"wrote {built.json_path}")
    for path in built.previews:
        print(f"wrote {path}")
    for warning in built.warnings:
        print(warning, file=sys.stderr)


def _cmd_unpack(args) -> None:
    written = unpack_folder(args.json, args.out)
    print(f"unpacked {len(written)} frames into {args.out}")


def _cmd_preview(args) -> None:
    paths = preview_file(
        args.json,
        args.out,
        gif=not args.no_gif,
        mp4=not args.no_mp4,
        scale=args.scale,
        background=args.background,
    )
    for path in paths:
        print(f"wrote {path}")


def _cmd_adapt(args) -> None:
    default_place, named = _places(args.place)
    places = dict(named)
    if default_place is not None:
        # A bare x,y plants every animation. Named places still win.
        meta = read(args.json)
        for anim in meta.animations:
            places.setdefault(anim.name, default_place)
    intro = adapt_file(
        args.json,
        args.out,
        places=places or None,
        plate=args.plate,
        plate_color=parse_color(args.plate_color),
        name=args.name,
    )
    print(f"wrote {intro}")
    print(f"wrote {args.out / 'mapping.yaml'}")


def _places(tokens: list[str]) -> tuple[tuple[int, int] | None, dict[str, tuple[int, int]]]:
    default = None
    named: dict[str, tuple[int, int]] = {}
    for token in tokens:
        if ":" in token:
            name, rest = token.split(":", 1)
            if name and "," in rest:
                named[name] = _xy(rest)
                continue
        default = _xy(token)
    return default, named


def _xy(text: str) -> tuple[int, int]:
    parts = text.split(",")
    if len(parts) != 2:
        raise SpritePackError(f"expected x,y, got {text!r}")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise SpritePackError(f"expected integer x,y, got {text!r}") from exc


def _pairs(tokens: list[str], cast, label: str) -> dict[str, object]:
    out = {}
    for token in tokens:
        if "=" not in token:
            raise SpritePackError(f"--frame-{label} must be file={label}, got {token!r}")
        name, raw = token.split("=", 1)
        try:
            out[name] = cast(raw)
        except ValueError as exc:
            raise SpritePackError(f"bad {label} in {token!r}") from exc
    return out


def _anchor_pairs(tokens: list[str]) -> dict[str, object]:
    out = {}
    for token in tokens:
        if "=" not in token:
            raise SpritePackError(f"--frame-anchor must be file=x,y, got {token!r}")
        name, raw = token.split("=", 1)
        out[name] = parse_anchor_token(raw)
    return out
