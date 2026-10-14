"""Pixel fonts. The LOGO logo is a beveled CD-ROM word. Prompts are a 4x6 font."""

from __future__ import annotations

import numpy as np

# 4x6 uppercase. The reference prompt glyphs match the v6 font exactly.
_SMALL = {
    "A": [".##.", "#..#", "####", "#..#", "#..#", "#..#"],
    "B": ["###.", "#..#", "###.", "#..#", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", "#...", ".###"],
    "D": ["###.", "#..#", "#..#", "#..#", "#..#", "###."],
    "E": ["####", "#...", "###.", "#...", "#...", "####"],
    "F": ["####", "#...", "###.", "#...", "#...", "#..."],
    "G": [".###", "#...", "#.##", "#..#", "#..#", ".###"],
    "H": ["#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    "I": ["###.", ".#..", ".#..", ".#..", ".#..", "###."],
    "J": ["..##", "...#", "...#", "#..#", "#..#", ".##."],
    "K": ["#..#", "#.#.", "##..", "##..", "#.#.", "#..#"],
    "L": ["#...", "#...", "#...", "#...", "#...", "####"],
    "M": ["#..#", "####", "#..#", "#..#", "#..#", "#..#"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", "#..#", ".##."],
    "P": ["###.", "#..#", "###.", "#...", "#...", "#..."],
    "Q": [".##.", "#..#", "#..#", "#.#.", ".##.", "..#."],
    "R": ["###.", "#..#", "###.", "#.#.", "#..#", "#..#"],
    "S": [".###", "#...", ".##.", "...#", "...#", "###."],
    "T": ["####", ".#..", ".#..", ".#..", ".#..", ".#.."],
    "U": ["#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "V": ["#..#", "#..#", "#..#", "#..#", ".##.", ".#.."],
    "W": ["#..#", "#..#", "#..#", "#..#", "####", "#..#"],
    "X": ["#..#", ".##.", ".##.", ".##.", ".##.", "#..#"],
    "Y": ["#..#", "#..#", ".##.", ".#..", ".#..", ".#.."],
    "Z": ["####", "...#", "..#.", ".#..", "#...", "####"],
    "0": [".##.", "#..#", "#..#", "#..#", "#..#", ".##."],
    "1": [".#..", "##..", ".#..", ".#..", ".#..", "###."],
    "2": ["###.", "...#", ".##.", "#...", "#...", "####"],
    "3": ["###.", "...#", ".##.", "...#", "...#", "###."],
    "4": ["#..#", "#..#", "####", "...#", "...#", "...#"],
    "5": ["####", "#...", "###.", "...#", "...#", "###."],
    "6": [".##.", "#...", "###.", "#..#", "#..#", ".##."],
    "7": ["####", "...#", "..#.", ".#..", ".#..", ".#.."],
    "8": [".##.", "#..#", ".##.", "#..#", "#..#", ".##."],
    "9": [".##.", "#..#", ".###", "...#", "...#", ".##."],
    " ": ["....", "....", "....", "....", "....", "...."],
    ".": ["....", "....", "....", "....", ".#..", ".#.."],
    ",": ["....", "....", "....", ".#..", ".#..", "#..."],
    "'": [".#..", ".#..", "....", "....", "....", "...."],
    "!": [".#..", ".#..", ".#..", "....", "....", ".#.."],
    "?": [".##.", "#..#", "..#.", ".#..", "....", ".#.."],
    "-": ["....", "....", "####", "....", "....", "...."],
}

_LOGO = {
    "G": [
        "..######....",
        ".##.....##..",
        "##.......#..",
        "#...........",
        "#...........",
        "#....#####..",
        "#....#...#..",
        "#....#...#..",
        "##...#...#..",
        ".##..#...#..",
        "..######.#..",
        ".........#..",
        "......###...",
        "............",
        "............",
        "............",
    ],
    "R": [
        ".#######....",
        ".##....##...",
        ".##.....##..",
        ".##.....##..",
        ".##....##...",
        ".#######....",
        ".##...##....",
        ".##....##...",
        ".##.....##..",
        ".##.....##..",
        ".##.....##..",
        "............",
        "............",
        "............",
        "............",
        "............",
    ],
    "A": [
        "....###.....",
        "...##.##....",
        "..##...##...",
        ".##.....##..",
        ".##.....##..",
        ".#########..",
        ".##.....##..",
        ".##.....##..",
        ".##.....##..",
        ".##.....##..",
        ".##.....##..",
        "............",
        "............",
        "............",
        "............",
        "............",
    ],
    "Y": [
        "##......##..",
        ".##....##...",
        "..##..##....",
        "...####.....",
        "....##......",
        "....##......",
        "....##......",
        "....##......",
        "....##......",
        "....##......",
        "...####.....",
        "............",
        "............",
        "............",
        "............",
        "............",
    ],
    "C": [
        "..######....",
        ".##....##...",
        "##......#...",
        "#...........",
        "#...........",
        "#...........",
        "#...........",
        "#...........",
        "##......#...",
        ".##....##...",
        "..######....",
        "............",
        "............",
        "............",
        "............",
        "............",
    ],
    "E": [
        ".########...",
        ".##.........",
        ".##.........",
        ".##.........",
        ".######.....",
        ".##.........",
        ".##.........",
        ".##.........",
        ".##.........",
        ".##.........",
        ".########...",
        "............",
        "............",
        "............",
        "............",
        "............",
    ],
}

# Bevel colors, on the 9-bit lattice. Same indices the v6 card paints.
FILL = (182, 182, 218, 255)
HI = (255, 255, 255, 255)
SHADE = (109, 109, 145, 255)
EDGE = (72, 72, 109, 255)
FILL_RGB = (182, 182, 218)


def small_width(text: str, scale: int = 2, gap: int = 1) -> int:
    w = 0
    for i, ch in enumerate(text):
        w += 4 * scale
        if i != len(text) - 1 and ch != " " and text[i + 1] != " ":
            w += gap
    return w


def logo_width(text: str, scale: int = 3, gap: int = 4) -> int:
    total = 0
    for i, ch in enumerate(text):
        total += len(_LOGO[ch][0]) * scale
        if i != len(text) - 1:
            total += gap
    return total


def check_small(text: str) -> str:
    out = []
    for ch in text:
        glyph = ch.upper() if ch.isalpha() else ch
        if glyph not in _SMALL:
            known = "".join(sorted(c for c in _SMALL if c != " "))
            raise ValueError(f"small font has no glyph for {ch!r}. It can draw: {known} and space")
        out.append(glyph)
    return "".join(out)


def check_logo(text: str) -> str:
    out = []
    for ch in text:
        glyph = ch.upper()
        if glyph not in _LOGO:
            raise ValueError(
                f"logo font has no glyph for {ch!r}. It only draws G, R, A, Y, C, E. "
                "Use font: small for any other word."
            )
        out.append(glyph)
    return "".join(out)


def _glyph_mask(rows: list[str], scale: int):
    h = len(rows) * scale
    w = len(rows[0]) * scale
    mask = []
    for row in rows:
        for _sy in range(scale):
            line = []
            for bit in row:
                line.extend([bit == "#"] * scale)
            mask.append(line)
    return w, h, mask


class Overlay:
    """RGBA layer. Alpha 0 is untouched; drawn pixels are opaque."""

    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        self.px = np.zeros((h, w, 4), dtype=np.uint8)

    def setp(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y, x] = color

    def rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
        if w <= 0 or h <= 0:
            return
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.w, int(x) + int(w))
        y1 = min(self.h, int(y) + int(h))
        if x0 < x1 and y0 < y1:
            self.px[y0:y1, x0:x1] = color


def draw_small(dst: Overlay, text: str, x: int, y: int, color: tuple, scale: int = 2, gap: int = 1) -> None:
    rgba = (color[0], color[1], color[2], 255 if len(color) == 3 else color[3])
    cx = x
    for i, ch in enumerate(text):
        rows = _SMALL[ch]
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "#":
                    dst.rect(cx + rx * scale, y + ry * scale, scale, scale, rgba)
        cx += 4 * scale
        if i != len(text) - 1 and ch != " " and text[i + 1] != " ":
            cx += gap


def draw_logo(dst: Overlay, text: str, x: int, y: int, scale: int, gap: int) -> np.ndarray:
    """Paint the beveled word. Returns the fill mask used by the sheen."""
    mask = np.zeros((dst.h, dst.w), dtype=bool)
    cx = x
    for i, ch in enumerate(text):
        rows = _LOGO[ch]
        w, h, gmask = _glyph_mask(rows, scale)
        for ry, row in enumerate(gmask):
            for rx, on in enumerate(row):
                if not on:
                    continue
                for oy in (-1, 0, 1):
                    for ox in (-1, 0, 1):
                        dst.setp(cx + rx + ox, y + ry + oy, EDGE)
        for ry, row in enumerate(gmask):
            for rx, on in enumerate(row):
                if not on:
                    continue
                px = cx + rx
                py = y + ry
                dst.setp(px, py, FILL)
                if 0 <= px < dst.w and 0 <= py < dst.h:
                    mask[py, px] = True
        for ry, row in enumerate(gmask):
            for rx, on in enumerate(row):
                if not on:
                    continue
                up = ry == 0 or not gmask[ry - 1][rx]
                left = rx == 0 or not row[rx - 1]
                down = ry == h - 1 or not gmask[ry + 1][rx]
                right = rx == w - 1 or not row[rx + 1]
                if up or left:
                    dst.setp(cx + rx, y + ry, HI)
                elif down or right:
                    dst.setp(cx + rx, y + ry, SHADE)
        cx += w + gap
    return mask


def apply_sheen(rgba: np.ndarray, mask: np.ndarray, frame: int, speed: int) -> None:
    """A 5px band walks across the logo and turns leftover fill pixels white."""
    if speed <= 0 or not mask.any():
        return
    width = rgba.shape[1]
    band = (frame * speed) % (width + 36) - 18
    xs = np.arange(width)
    band_m = np.abs(xs - band) <= 2
    sel = mask & band_m[None, :]
    fill = (
        (rgba[:, :, 0] == FILL_RGB[0])
        & (rgba[:, :, 1] == FILL_RGB[1])
        & (rgba[:, :, 2] == FILL_RGB[2])
    )
    hit = sel & fill
    rgba[hit, 0] = 255
    rgba[hit, 1] = 255
    rgba[hit, 2] = 255
    rgba[hit, 3] = 255
