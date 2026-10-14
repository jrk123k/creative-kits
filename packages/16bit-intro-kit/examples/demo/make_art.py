"""Draw the placeholder art and a 6 second song so the demo runs with no outside assets.

Every color is already on the PC Engine lattice, so palette: tg16 does not move a pixel.
Run from anywhere: python examples/demo/make_art.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
ART = ROOT / "art"
AUDIO = ROOT / "audio"

W, H = 256, 224
SKY = (0, 0, 36)
SKY2 = (0, 0, 72)
HAIR = (218, 218, 255)
FACE = (182, 182, 218)
EYE = (0, 0, 0)
SUIT = (72, 109, 109)
BELT = (145, 145, 182)
MOUTH = (36, 0, 36)
OPEN = (218, 0, 0)
FLOOR = (36, 72, 109)
PANEL = (72, 72, 109)
STAR = (255, 255, 255)
HULL = (109, 109, 145)
LAMP = (0, 182, 72)
CRITTER = (218, 145, 0)

# Open-mouth patch pasted at this origin on the closed plate.
PATCH_XY = (120, 108)
PATCH_SIZE = (16, 8)


def _fill(img, x, y, w, h, color):
    img[y : y + h, x : x + w] = color


def bust(mouth_open: bool) -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = SKY
    _fill(img, 0, 0, W, 8, SKY2)
    _fill(img, 0, H - 8, W, 8, SKY2)
    # Hair, face, suit. Blocky on purpose.
    _fill(img, 78, 18, 100, 36, HAIR)
    _fill(img, 70, 36, 116, 90, HAIR)
    _fill(img, 86, 48, 84, 78, FACE)
    _fill(img, 96, 62, 22, 28, EYE)
    _fill(img, 138, 62, 22, 28, EYE)
    _fill(img, 100, 66, 6, 8, STAR)
    _fill(img, 142, 66, 6, 8, STAR)
    _fill(img, 92, 128, 72, 70, SUIT)
    _fill(img, 108, 150, 40, 8, BELT)
    _fill(img, 124, 146, 8, 8, (218, 218, 255))
    if not mouth_open:
        _fill(img, 122, 110, 12, 2, MOUTH)
    return img


def open_patch() -> np.ndarray:
    patch = np.zeros((PATCH_SIZE[1], PATCH_SIZE[0], 3), dtype=np.uint8)
    patch[:, :] = FACE
    patch[2:6, 3:13] = OPEN
    return patch


def corridor() -> np.ndarray:
    tile_w = 96
    img = np.zeros((H, tile_w, 3), dtype=np.uint8)
    img[:, :] = SKY
    _fill(img, 0, 0, tile_w, 28, SKY2)
    _fill(img, 0, 168, tile_w, H - 168, FLOOR)
    # Panels sit inside the tile so the repeat has no seam.
    for x in (8, 40, 72):
        _fill(img, x, 40, 20, 36, PANEL)
        _fill(img, x + 4, 48, 12, 8, STAR)
    for x in range(0, tile_w, 8):
        img[168, x : x + 3] = (109, 145, 182)
    return img


def walker() -> np.ndarray:
    h, w = 72, 36
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[0:16, 8:28] = (*HAIR, 255)
    img[10:32, 10:26] = (*FACE, 255)
    img[16:22, 12:16] = (*EYE, 255)
    img[16:22, 20:24] = (*EYE, 255)
    img[28:68, 8:28] = (*SUIT, 255)
    img[44:48, 10:26] = (*BELT, 255)
    return img


def sky() -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = SKY
    _fill(img, 0, 160, W, H - 160, (0, 36, 0))
    _fill(img, 0, 150, W, 12, (0, 72, 36))
    rng = np.random.default_rng(7)
    for _ in range(40):
        x = int(rng.integers(0, W))
        y = int(rng.integers(0, 140))
        img[y, x] = STAR
    return img


def ship() -> np.ndarray:
    h, w = 14, 40
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[4:10, 4:36] = (*HULL, 255)
    img[6:9, 0:40] = (*HULL, 255)
    img[2:6, 14:26] = (*BELT, 255)
    img[7:9, 18:22] = (*LAMP, 255)
    return img


def critter(step: int) -> np.ndarray:
    h, w = 12, 14
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[2:8, 2:12] = (*CRITTER, 255)
    img[0:3, 3:6] = (*CRITTER, 255)
    img[0:3, 8:11] = (*CRITTER, 255)
    img[1:2, 4:5] = (*EYE, 255)
    img[1:2, 9:10] = (*EYE, 255)
    leg = 2 if step else 0
    img[8:12, 3:5] = (*CRITTER, 255)
    img[8:12, 9 + leg : 11 + leg] = (*CRITTER, 255)
    return img


def title_bg() -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = (0, 0, 72)
    _fill(img, 0, 0, W, 40, SKY)
    # A planet, bottom right. No prompt cyan in this plate.
    for y in range(120, 200):
        for x in range(150, 230):
            if (x - 190) ** 2 + (y - 160) ** 2 <= 38 ** 2:
                img[y, x] = (0, 109, 218) if y < 160 else (36, 145, 72)
    rng = np.random.default_rng(3)
    for _ in range(30):
        img[int(rng.integers(4, 100)), int(rng.integers(4, 140))] = STAR
    return img


def save_rgb(arr: np.ndarray, name: str) -> None:
    Image.fromarray(arr, "RGB").save(ART / name)


def save_rgba(arr: np.ndarray, name: str) -> None:
    Image.fromarray(arr, "RGBA").save(ART / name)


def song() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    dest = AUDIO / "song.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=6,aformat=channel_layouts=stereo",
            "-c:a",
            "libmp3lame",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-b:a",
            "192k",
            str(dest),
        ],
        check=True,
    )


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    closed = bust(False)
    patch = open_patch()
    opened = closed.copy()
    y, x = PATCH_XY[1], PATCH_XY[0]
    opened[y : y + patch.shape[0], x : x + patch.shape[1]] = patch
    save_rgb(closed, "bust_closed.png")
    save_rgb(opened, "bust_open.png")
    save_rgb(patch, "mouth_open_patch.png")
    save_rgb(corridor(), "corridor.png")
    save_rgba(walker(), "walker.png")
    save_rgb(sky(), "sky.png")
    save_rgba(ship(), "ship.png")
    save_rgba(critter(0), "critter_0.png")
    save_rgba(critter(1), "critter_1.png")
    save_rgb(title_bg(), "title_bg.png")
    song()
    print(f"wrote art in {ART} and {AUDIO / 'song.mp3'}")
    print(f"mouth patch at x={PATCH_XY[0]} y={PATCH_XY[1]} size={PATCH_SIZE[0]}x{PATCH_SIZE[1]}")


if __name__ == "__main__":
    main()
