"""Build the studio sample plates, walker, hill, and the TG16 palette files.

Colors come from palette_snap.palette (the intro kit list), so every swatch
is already on the PC Engine lattice. Run from the repo root:

    python3 scripts/make_samples.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

from palette_snap.palette import NAME, PAL
SAMPLES = ROOT / "studio" / "samples"
PALETTES = ROOT / "studio" / "palettes"

W, H = 256, 224


def C(name: str) -> tuple[int, int, int]:
    rgb = tuple(int(v) for v in PAL[NAME[name]])
    return rgb


def new_image(w: int, h: int, color: tuple[int, int, int] | None = None) -> np.ndarray:
    img = np.zeros((h, w, 4), dtype=np.uint8)
    if color is not None:
        img[..., 0] = color[0]
        img[..., 1] = color[1]
        img[..., 2] = color[2]
        img[..., 3] = 255
    return img


def rect(img: np.ndarray, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1, 0] = color[0]
    img[y0:y1, x0:x1, 1] = color[1]
    img[y0:y1, x0:x1, 2] = color[2]
    img[y0:y1, x0:x1, 3] = 255


def disc(img: np.ndarray, cx: int, cy: int, r: int, color: tuple[int, int, int]) -> None:
    y0, y1 = max(0, cy - r), min(img.shape[0], cy + r + 1)
    x0, x1 = max(0, cx - r), min(img.shape[1], cx + r + 1)
    yy, xx = np.ogrid[y0 - cy : y1 - cy, x0 - cx : x1 - cx]
    mask = xx * xx + yy * yy <= r * r
    img[y0:y1, x0:x1][mask, 0] = color[0]
    img[y0:y1, x0:x1][mask, 1] = color[1]
    img[y0:y1, x0:x1][mask, 2] = color[2]
    img[y0:y1, x0:x1][mask, 3] = 255


def night_hill() -> np.ndarray:
    sky0, sky1, sky2, sky3 = C("sky0"), C("sky1"), C("sky2"), C("sky3")
    land, grass = C("land0"), C("grass2")
    star, star2, steel = C("star"), C("star2"), C("steel0")
    img = new_image(W, H, sky0)
    rect(img, 0, 36, W, 40, sky1)
    rect(img, 0, 76, W, 44, sky2)
    rect(img, 0, 120, W, 48, sky3)
    disc(img, 46, 40, 16, star2)
    disc(img, 40, 36, 4, steel)
    disc(img, 52, 46, 3, steel)
    rng = np.random.default_rng(4)
    for _ in range(48):
        x = int(rng.integers(0, W))
        y = int(rng.integers(4, 148))
        if y > 150:
            continue
        img[y, x, :3] = star if rng.random() > 0.75 else star2
        img[y, x, 3] = 255
    for x in range(W):
        ridge = 160 + int(round(5 * np.sin(x / 17.0) + 2 * np.sin(x / 7.0)))
        img[ridge:H, x, :3] = land
        img[ridge:H, x, 3] = 255
        img[ridge : ridge + 3, x, :3] = grass
        img[ridge : ridge + 3, x, 3] = 255
    # A static contact shadow where the walker stands.
    rect(img, 112, 186, 32, 3, C("grass0"))
    return img


def draw_singer(mouth_open: bool) -> np.ndarray:
    img = night_hill()
    outline = C("navy")
    jacket = C("jean2")
    shade = C("jean")
    shirt = C("star2")
    skin = C("warm")
    shadow = C("hskin2")
    hair = C("hhair")
    hair_hi = C("steel3")
    lip = C("lip")
    cavity = C("mouth")
    eye = C("black")
    catch = C("white")
    pin = C("cyan")
    mic = C("steel1")

    rect(img, 64, 148, 128, 76, outline)
    rect(img, 68, 152, 120, 72, jacket)
    rect(img, 68, 152, 22, 72, shade)
    rect(img, 166, 152, 22, 72, shade)
    rect(img, 104, 152, 48, 34, shirt)
    rect(img, 116, 128, 24, 36, shadow)
    rect(img, 120, 128, 16, 30, skin)

    rect(img, 86, 46, 84, 90, hair)
    rect(img, 96, 58, 64, 70, skin)
    rect(img, 96, 46, 64, 22, hair)
    rect(img, 108, 40, 40, 14, hair)
    rect(img, 112, 42, 8, 18, hair_hi)
    rect(img, 100, 78, 16, 28, hair)
    rect(img, 140, 78, 16, 28, hair)

    rect(img, 112, 74, 14, 16, eye)
    rect(img, 134, 74, 14, 16, eye)
    rect(img, 114, 76, 4, 4, catch)
    rect(img, 136, 76, 4, 4, catch)
    rect(img, 110, 70, 16, 3, hair)
    rect(img, 132, 70, 16, 3, hair)
    rect(img, 126, 96, 4, 8, shadow)

    rect(img, 154, 96, 6, 40, C("black"))
    rect(img, 148, 88, 18, 12, mic)
    rect(img, 152, 92, 10, 4, pin)
    rect(img, 78, 168, 8, 8, pin)

    if mouth_open:
        rect(img, 112, 108, 32, 16, lip)
        rect(img, 116, 112, 24, 10, cavity)
        rect(img, 120, 112, 10, 3, catch)
    else:
        rect(img, 114, 114, 28, 4, lip)
    return img


def diff_patch(closed: np.ndarray, opened: np.ndarray) -> tuple[np.ndarray, int, int]:
    if closed.shape != opened.shape:
        raise SystemExit("closed and open plates differ in size")
    h, w, _ = closed.shape
    changed = np.any(closed != opened, axis=-1)
    if not np.any(changed):
        raise SystemExit("mouth frames are identical")
    ys, xs = np.nonzero(changed)
    x, y = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
    patch = opened[y:y1, x:x1].copy()
    pasted = closed.copy()
    pasted[y:y1, x:x1] = patch
    if not np.array_equal(pasted, opened):
        raise SystemExit("patch does not reproduce the open plate")
    return patch, x, y


WALK_COLORS = {
    ".": None,
    "o": "black",
    "h": "hhair",
    "s": "warm",
    "e": "white",
    "j": "jean2",
    "d": "jean",
    "b": "boot",
    "c": "cyan",
}

# 16×16. Rows 0–10 stay put. Legs swap so the body does not slide.
_BODY = [
    "......oooo......",
    "....oohhhhho....",
    "....ohseehho....",
    "....ohssshho....",
    "....ooosssso....",
    "......osso......",
    ".....ojddjjo....",
    "....ojjddjjjo...",
    "....ojjddjjjo...",
    ".....ojjjjjo....",
    "......occc......",
]
_LEGS = [
    [
        ".....jj..jj.....",
        ".....jj..jj.....",
        ".....bb..bb.....",
        "....bbb..bbb....",
        "....bb....bb....",
    ],
    [
        "...jj......jj...",
        "...jj.......jj..",
        "...bb........b..",
        "..bbb........b..",
        "..bb............",
    ],
    [
        "......jjjj......",
        "......jjjj......",
        "......bbbb......",
        ".....bbbbbb.....",
        ".....bb..bb.....",
    ],
    [
        "...jj......jj...",
        "..jj.......jj...",
        "..b........bb...",
        "..b........bbb..",
        "............bb..",
    ],
]


def draw_walk_frame(legs: list[str]) -> np.ndarray:
    rows = _BODY + legs
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise SystemExit("walker frame is not rectangular")
    img = new_image(width, len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            name = WALK_COLORS[ch]
            if name is None:
                continue
            rgb = C(name)
            img[y, x, :3] = rgb
            img[y, x, 3] = 255
    return img.repeat(2, axis=0).repeat(2, axis=1)


def kit_colors() -> list[dict]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for name, idx in NAME.items():
        grouped[idx].append(name)
    colors = []
    seen: set[tuple[int, int, int]] = set()
    for idx in sorted(grouped):
        rgb = tuple(int(v) for v in PAL[idx])
        if rgb in seen:
            continue
        seen.add(rgb)
        names = grouped[idx]
        colors.append({"name": names[0], "names": names, "rgb": list(rgb)})
    return colors


def save_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.shape[-1] == 4 and bool(np.all(img[..., 3] == 255)):
        Image.fromarray(img[..., :3], "RGB").save(path)
    else:
        Image.fromarray(img, "RGBA").save(path)


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    PALETTES.mkdir(parents=True, exist_ok=True)
    hill = night_hill()
    closed = draw_singer(False)
    opened = draw_singer(True)
    patch, px, py = diff_patch(closed, opened)
    save_image(SAMPLES / "hill_bg_256.png", hill)
    save_image(SAMPLES / "singer_256.png", closed)
    save_image(SAMPLES / "singer_open_256.png", opened)
    save_image(SAMPLES / "singer_open_patch.png", patch)

    frames = []
    walker = None
    for i, legs in enumerate(_LEGS):
        frame = draw_walk_frame(legs)
        walker = frame
        save_image(SAMPLES / f"walker_{i}.png", frame)
        frames.append(f"walker_{i}.png")

    assert walker is not None
    ox = (W - walker.shape[1]) // 2
    # Feet sit on the first ground row of the hill (y=168 is inside the ridge band).
    oy = 168 - walker.shape[0]

    colors = kit_colors()
    palette = {
        "name": "tg16",
        "locked": True,
        "source": "intro kit palette.py",
        "colors": colors,
    }
    (PALETTES / "tg16.json").write_text(json.dumps(palette, indent=2) + "\n", encoding="utf-8")
    cell = 8
    strip = new_image(cell * len(colors), cell)
    for i, entry in enumerate(colors):
        rect(strip, i * cell, 0, cell, cell, tuple(entry["rgb"]))
    save_image(PALETTES / "tg16.png", strip)

    manifest = {
        "mouth": {
            "shot": "singer",
            "naming": "plate",
            "frames": ["singer_256.png", "singer_open_256.png"],
            "mouth": [0, 1],
            "hold": 4,
            "fps": 12,
            "scale": 1,
            "editorZoom": 2,
            "background": None,
            "offset": [0, 0],
            "patch": {
                "file": "singer_open_patch.png",
                "x": px,
                "y": py,
                "w": int(patch.shape[1]),
                "h": int(patch.shape[0]),
            },
            "note": "Singer plates, 256×224. Mouth flaps at a 4-frame hold.",
        },
        "walk": {
            "shot": "walker",
            "naming": "sprite",
            "frames": frames,
            "mouth": None,
            "hold": 4,
            "fps": 8,
            "scale": 1,
            "editorZoom": 8,
            "background": "hill_bg_256.png",
            "offset": [ox, oy],
            "note": "Walker on the hill. Alpha is 0 or 255.",
        },
    }
    (SAMPLES / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"patch {patch.shape[1]}x{patch.shape[0]} at {px},{py}")
    print(f"walker {walker.shape[1]}x{walker.shape[0]} offset {ox},{oy}")
    print(f"palette {len(colors)} colors")


if __name__ == "__main__":
    main()
