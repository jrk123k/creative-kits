"""Command line for palette_snap."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from palette_snap.snap import extract_palette, snap_rgba


def load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        rgba = ImageOps.exif_transpose(im).convert("RGBA")
        return np.asarray(rgba, dtype=np.uint8)


def save_rgba(path: Path, rgba: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path)


def palette_payload(colors: np.ndarray, *, tg16: bool) -> dict:
    entries = []
    for row in colors:
        r, g, b = (int(row[0]), int(row[1]), int(row[2]))
        entries.append({"rgb": [r, g, b], "hex": f"#{r:02x}{g:02x}{b:02x}"})
    return {"space": "oklab", "tg16": tg16, "colors": entries}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="palette_snap",
        description=(
            "Snap an image to N colors taken from a reference frame. "
            "Distance is OKLab. Alpha is preserved. "
            "Optional 8x8 Bayer dither and PC Engine 9-bit clamp."
        ),
    )
    p.add_argument("image", type=Path, help="PNG (or any image Pillow reads) to snap")
    p.add_argument("-o", "--output", type=Path, required=True, help="output PNG (RGBA)")
    p.add_argument(
        "-r",
        "--reference",
        type=Path,
        help="frame whose opaque pixels supply the palette (default: the input)",
    )
    p.add_argument(
        "-n",
        "--colors",
        type=int,
        default=16,
        help="how many reference colors to keep, most frequent first (default: 16)",
    )
    p.add_argument(
        "--dither",
        action="store_true",
        help="ordered Bayer dither on OKLab lightness",
    )
    p.add_argument(
        "--dither-strength",
        type=float,
        default=1.0,
        help="dither amount, 0..8 (default: 1, exact palette colors stay put)",
    )
    p.add_argument(
        "--tg16",
        action="store_true",
        help="clamp palette and output to the PC Engine 9-bit lattice (3 bits per channel)",
    )
    p.add_argument(
        "--palette-out",
        type=Path,
        help="also write the chosen palette as JSON",
    )
    p.add_argument(
        "--space",
        choices=("oklab",),
        default="oklab",
        help="perceptual space (default: oklab)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.colors < 1:
            raise ValueError("colors must be >= 1")
        if not (0.0 <= args.dither_strength <= 8.0):
            raise ValueError("dither strength must be between 0 and 8")
        image = load_rgba(args.image)
        reference = image if args.reference is None else load_rgba(args.reference)
        palette = extract_palette(reference, args.colors, tg16=args.tg16)
        out = snap_rgba(
            image,
            palette,
            dither=args.dither,
            dither_strength=args.dither_strength,
            tg16=args.tg16,
        )
        save_rgba(args.output, out)
        if args.palette_out is not None:
            args.palette_out.parent.mkdir(parents=True, exist_ok=True)
            args.palette_out.write_text(
                json.dumps(palette_payload(palette, tg16=args.tg16), indent=2) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError) as exc:
        print(f"palette_snap: {exc}", file=sys.stderr)
        return 1
    print(
        f"wrote {args.output} ({out.shape[1]}x{out.shape[0]}, {len(palette)} colors, {args.space})",
        file=sys.stderr,
    )
    return 0
