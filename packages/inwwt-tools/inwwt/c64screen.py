"""Render the C64 text screen and upscale it to 1080p with integer pixels.

The text matrix is 320×200 (40×25 cells of 8×8). It is centered in a
low-resolution framebuffer whose width and height divide the output, then
the whole framebuffer — border included — is repeated by an integer factor
with nearest-neighbor. The default is a 384×216 frame scaled ×5 to
1920×1080, which is an exact integer fit (320×200 does not divide 1080).
"""

from __future__ import annotations

import numpy as np

from inwwt.c64font import CELL, glyph
from inwwt.c64script import COLS, ROWS, Program, compile_script
from inwwt.palette import BACKGROUND_INDEX, BORDER_INDEX, get_palette
from inwwt.video import FrameWriter

# The KERNAL blinks the cursor every 20 frames.
NTSC_BLINK = 20 / 60.0
PAL_BLINK = 20 / 50.0


def blink_period(rate: str | float) -> float:
    if isinstance(rate, (int, float)) and not isinstance(rate, bool):
        period = float(rate)
        if period <= 0:
            raise ValueError("blink period must be positive")
        return period
    key = str(rate).strip().lower()
    if key == "ntsc":
        return NTSC_BLINK
    if key == "pal":
        return PAL_BLINK
    return float(key)


def framebuffer_size(out_width: int, out_height: int, scale: int) -> tuple[int, int, int, int]:
    if scale < 1:
        raise ValueError("scale must be a positive integer")
    if out_width % scale or out_height % scale:
        raise ValueError(f"{out_width}x{out_height} is not divisible by scale {scale}")
    fb_w, fb_h = out_width // scale, out_height // scale
    if fb_w < COLS * CELL or fb_h < ROWS * CELL:
        raise ValueError("scale is too large for a 40×25 text matrix")
    border_x = (fb_w - COLS * CELL) // 2
    border_y = (fb_h - ROWS * CELL) // 2
    return fb_w, fb_h, border_x, border_y


def render_lowres(
    cells: np.ndarray,
    colors: np.ndarray,
    cursor: tuple[int, int] | None,
    palette: np.ndarray,
    *,
    out_width: int = 1920,
    out_height: int = 1080,
    scale: int = 5,
    charset: str = "upper",
    border: int = BORDER_INDEX,
    background: int = BACKGROUND_INDEX,
) -> np.ndarray:
    fb_w, fb_h, border_x, border_y = framebuffer_size(out_width, out_height, scale)
    image = np.empty((fb_h, fb_w, 3), dtype=np.uint8)
    image[:] = palette[border]
    text = image[border_y : border_y + ROWS * CELL, border_x : border_x + COLS * CELL]
    text[:] = palette[background]
    cursor_row, cursor_col = cursor if cursor is not None else (-1, -1)
    for row in range(ROWS):
        for col in range(COLS):
            code = int(cells[row, col])
            bits = glyph(code & 0x7F, charset)
            if code & 0x80:
                bits = 1 - bits
            if row == cursor_row and col == cursor_col:
                bits = 1 - bits
            ink = palette[int(colors[row, col]) & 0x0F]
            paper = palette[background]
            cell = np.where(bits[:, :, None] != 0, ink, paper)
            y0, x0 = row * CELL, col * CELL
            text[y0 : y0 + CELL, x0 : x0 + CELL] = cell
    return image


def upscale_nearest(image: np.ndarray, scale: int) -> np.ndarray:
    if scale == 1:
        return image
    return np.repeat(np.repeat(image, scale, axis=0), scale, axis=1)


def cursor_visible(t: float, period: float, enabled: bool = True) -> bool:
    if not enabled:
        return False
    # The machine powers on with the cursor lit, then toggles every `period`.
    return int(t / period) % 2 == 0


def render_program_frame(
    program: Program,
    t: float,
    *,
    palette_name: str = "pepto",
    blink: str | float = "ntsc",
    out_width: int = 1920,
    out_height: int = 1080,
    scale: int = 5,
    show_cursor: bool = True,
) -> np.ndarray:
    palette = get_palette(palette_name)
    cells, colors, row, col, charset = program.state_at(t)
    cursor = (row, col) if cursor_visible(t, blink_period(blink), show_cursor) else None
    low = render_lowres(
        cells,
        colors,
        cursor,
        palette,
        out_width=out_width,
        out_height=out_height,
        scale=scale,
        charset=charset,
    )
    return upscale_nearest(low, scale)


def render_c64_video(
    script_path: str,
    output: str,
    *,
    palette_name: str = "pepto",
    fps: float = 30.0,
    blink: str | float = "ntsc",
    tail: float = 1.5,
    out_width: int = 1920,
    out_height: int = 1080,
    scale: int = 5,
    crf: int = 20,
    preset: str = "medium",
    cps: float = 8.0,
) -> None:
    source = open(script_path, encoding="utf-8").read()
    program = compile_script(source, cps=cps)
    duration = program.duration + tail
    count = max(1, int(round(duration * fps)))
    writer = FrameWriter(output, out_width, out_height, fps, crf=crf, preset=preset, audio=False)
    try:
        for i in range(count):
            t = i / fps
            writer.write(
                render_program_frame(
                    program,
                    t,
                    palette_name=palette_name,
                    blink=blink,
                    out_width=out_width,
                    out_height=out_height,
                    scale=scale,
                )
            )
            if i % max(1, int(fps)) == 0:
                print(f"c64 {i + 1}/{count}", flush=True)
    finally:
        writer.close()
