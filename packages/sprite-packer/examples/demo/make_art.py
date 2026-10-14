"""Synthetic demo frames for Kit Sprite Packer.

A 14×12 cow turns through four poses, and a 256×224 singer opens her mouth.
Every color is on the PC Engine lattice (0, 36, 72, 109, 145, 182, 218, 255).
Sprite alpha is 0 or 255. The mouth patch is the open-frame crop of the pixels
that differ, which is what Pixel Studio exports and what the intro kit checks.

Run from the repo root:

    python examples/demo/make_art.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from spritepack.mouth import diff_box

W, H = 256, 224

# Lattice colors.
SKY = (0, 0, 36)
SKY2 = (0, 0, 72)
CAP = (145, 0, 72)
SKIN = (218, 182, 145)
HAIR = (72, 36, 0)
EYE = (0, 0, 0)
WHITE = (255, 255, 255)
SHIRT = (0, 109, 145)
COLLAR = (145, 145, 182)
MOUTH = (145, 36, 72)
OPEN = (72, 0, 36)
LIP = (218, 109, 145)
RIDGE = (0, 72, 36)
GRASS = (36, 109, 36)
FAR = (0, 109, 36)
STONE = (72, 72, 72)

# The open mouth replaces this whole rectangle, so the diff box is stable.
PATCH = (116, 124, 24, 12)

COW = {
    ".": None,
    "H": (218, 218, 145),
    "W": (255, 255, 255),
    "B": (0, 0, 0),
    "E": (0, 0, 36),
    "P": (218, 109, 145),
    "F": (72, 36, 0),
    "O": (36, 36, 72),
}

# Side, facing right. Hooves sit on the last rows so bottom-center is the ground.
COW_RIGHT = [
    "........HH....",
    "......WWWW....",
    ".....WBBWW....",
    "...WWWWEWP....",
    "...WWWWWWW....",
    "...BWWWWWW....",
    "...WWWWWWW....",
    "...WWWWW......",
    "...WWWW.......",
    "...F.F..F.....",
    "...F.F..F.....",
    "...O.O..O.....",
]
COW_FRONT = [
    "....HH..HH....",
    "...WWWWWWWW...",
    "...WWWWWWWW...",
    "...WE.WW.EW...",
    "...WWWWWWWW...",
    "...WWPPPPWW...",
    "..WWWWWWWWWW..",
    "..WWWBWWBWWW..",
    "..WWWWWWWWWW..",
    "...F.F..F.F...",
    "...F.F..F.F...",
    "...O.O..O.O...",
]
COW_BACK = [
    "....HH..HH....",
    "...WWWWWWWW...",
    "...WWWWWWWW...",
    "...WWWWWWWW...",
    "..WWWWWWWWWW..",
    "..WBBWWWWBBW..",
    "..WWWWWWWWWW..",
    "...WWWWWWWW...",
    "...WWWWWWWW...",
    "...F.F..F.F...",
    "...F.F..F.F...",
    "...O.O..O.O...",
]


def _fill(img: np.ndarray, x: int, y: int, w: int, h: int, color) -> None:
    img[y : y + h, x : x + w] = color


def _cow(rows: list[str]) -> np.ndarray:
    if len(rows) != 12 or any(len(row) != 14 for row in rows):
        raise SystemExit("cow frames must be 14×12")
    img = np.zeros((12, 14, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            color = COW[pixel]
            if color is None:
                continue
            img[y, x] = (*color, 255)
    return img


def _mirror(rows: list[str]) -> list[str]:
    return [row[::-1] for row in rows]


def singer(mouth_open: bool) -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = SKY
    _fill(img, 0, 0, W, 6, SKY2)
    _fill(img, 0, H - 6, W, 6, SKY2)
    _fill(img, 70, 150, 116, 68, SHIRT)
    _fill(img, 108, 156, 40, 8, COLLAR)
    _fill(img, 78, 28, 100, 24, CAP)
    _fill(img, 74, 48, 108, 78, HAIR)
    _fill(img, 90, 58, 76, 86, SKIN)
    _fill(img, 102, 78, 16, 18, EYE)
    _fill(img, 138, 78, 16, 18, EYE)
    _fill(img, 106, 82, 4, 6, WHITE)
    _fill(img, 142, 82, 4, 6, WHITE)
    px, py, pw, ph = PATCH
    if mouth_open:
        _fill(img, px, py, pw, ph, LIP)
        _fill(img, px + 2, py + 2, pw - 4, ph - 4, OPEN)
    else:
        _fill(img, 120, 128, 16, 3, MOUTH)
    return img


def hill() -> np.ndarray:
    """256×224 plate. The cow's feet land on y=176."""
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = SKY
    _fill(img, 0, 0, W, 8, SKY2)
    _fill(img, 0, 148, W, 28, RIDGE)
    _fill(img, 0, 176, W, H - 176, GRASS)
    _fill(img, 20, 176, 36, 3, STONE)
    _fill(img, 180, 176, 28, 2, STONE)
    rng = np.random.default_rng(4)
    for _ in range(28):
        img[int(rng.integers(12, 130)), int(rng.integers(4, 252))] = WHITE
    return img


def pasture() -> np.ndarray:
    """Small preview plate. The cow anchor sits at (48, 52)."""
    img = np.zeros((64, 96, 3), dtype=np.uint8)
    img[:, :] = SKY2
    _fill(img, 0, 40, 96, 12, FAR)
    _fill(img, 0, 52, 96, 12, GRASS)
    return img


def _save_rgb(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, "RGB").save(path)


def _save_rgba(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, "RGBA").save(path)


def _sidecar() -> dict:
    return {
        "format": "kit-sprite-packer-sidecar",
        "version": 1,
        "fps": 30,
        "hold": 4,
        "anchor": "bottom-center",
        "animations": {
            "cow": {
                "background": "../bg/pasture.png",
                "place": [48, 52],
                "place_space": "anchor",
                "scale": 8,
                "kit_place": [160, 176],
                "cycle": {"mode": "loop", "skip_last": 0},
                "frames": {"cow_3.png": {"duration_ms": 400}},
            },
            "singer": {
                "background": "#000024",
                "scale": 2,
                "cycle": {"mode": "loop"},
            },
        },
    }


def generate(root: Path) -> None:
    frames = root / "frames"
    bg = root / "bg"
    frames.mkdir(parents=True, exist_ok=True)
    bg.mkdir(parents=True, exist_ok=True)

    poses = [
        _cow(COW_RIGHT),
        _cow(COW_FRONT),
        _cow(_mirror(COW_RIGHT)),
        _cow(COW_BACK),
    ]
    for index, pose in enumerate(poses):
        _save_rgba(frames / f"cow_{index}.png", pose)

    closed = singer(False)
    opened = singer(True)
    box = diff_box(closed, opened)
    if box != PATCH:
        raise SystemExit(f"mouth diff box is {box}, expected {PATCH}")
    x, y, w, h = box
    _save_rgb(frames / "singer_256.png", closed)
    _save_rgb(frames / "singer_open_256.png", opened)
    _save_rgb(frames / "singer_open_patch.png", opened[y : y + h, x : x + w])
    _save_rgb(bg / "hill_256.png", hill())
    _save_rgb(bg / "pasture.png", pasture())
    (frames / "sprites.json").write_text(json.dumps(_sidecar(), indent=2) + "\n")


def main() -> None:
    generate(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
