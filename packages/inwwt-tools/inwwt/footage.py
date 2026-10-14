"""Synthetic test clips so the demos do not depend on a camera roll.

Each clip is a slow gradient, a moving shape, and a title, plus a sine tone
so a compositor can prove which panel's audio it took.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from inwwt.compositor import default_label_font
from inwwt.video import FrameWriter


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(default_label_font(), size)


def synthetic_frame(
    index: int,
    count: int,
    width: int,
    height: int,
    *,
    title: str,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> np.ndarray:
    t = 0.0 if count <= 1 else index / (count - 1)
    ys = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    # A slow vertical drift so the frame is obviously moving.
    drift = 0.08 * math.sin(t * math.tau)
    mix = np.clip(ys + drift, 0.0, 1.0)
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    for channel in range(3):
        rgb[:, :, channel] = top[channel] * (1.0 - mix) + bottom[channel] * mix
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)
    cx = int(width * (0.5 + 0.22 * math.sin(t * math.tau)))
    cy = int(height * (0.42 + 0.12 * math.cos(t * math.tau)))
    radius = int(min(width, height) * 0.16)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=accent)
    font = _font(max(32, width // 12))
    box = draw.textbbox((0, 0), title, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    tx = (width - tw) // 2
    ty = int(height * 0.72)
    draw.rectangle((tx - 16, ty - 8, tx + tw + 16, ty + th + 12), fill=(0, 0, 0))
    draw.text((tx, ty), title, font=font, fill=(255, 255, 255))
    return np.asarray(image)


def write_synthetic_clip(
    path: str,
    *,
    title: str,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    accent: tuple[int, int, int],
    duration: float = 6.0,
    width: int = 1280,
    height: int = 720,
    fps: float = 24.0,
    tone: float = 220.0,
    crf: int = 20,
) -> None:
    count = max(1, int(round(duration * fps)))
    extra = ["-f", "lavfi", "-i", f"sine=frequency={tone}:sample_rate=48000:duration={duration}"]
    writer = FrameWriter(
        path,
        width,
        height,
        fps,
        crf=crf,
        preset="veryfast",
        extra_inputs=extra,
        filter_complex="[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[aout]",
        maps=["0:v", "[aout]"],
        audio=True,
    )
    try:
        for i in range(count):
            writer.write(
                synthetic_frame(
                    i,
                    count,
                    width,
                    height,
                    title=title,
                    top=top,
                    bottom=bottom,
                    accent=accent,
                )
            )
    finally:
        writer.close()


# Era colors from the concept: wood and CRT amber, a warm kitchen, luminous teal.
ERA_CLIPS = {
    "then": {
        "title": "THEN",
        "top": (92, 58, 36),
        "bottom": (28, 18, 16),
        "accent": (196, 168, 96),
        "tone": 196.0,
    },
    "now": {
        "title": "NOW",
        "top": (214, 168, 120),
        "bottom": (92, 78, 64),
        "accent": (40, 44, 48),
        "tone": 330.0,
    },
    "future": {
        "title": "FUTURE",
        "top": (232, 244, 246),
        "bottom": (18, 92, 112),
        "accent": (120, 230, 220),
        "tone": 523.0,
    },
}
