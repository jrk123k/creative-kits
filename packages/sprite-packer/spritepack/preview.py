"""GIF and MP4 previews. The scale is an integer nearest-neighbor blow-up.

GIF frames use Pillow. MP4 uses ffmpeg when it is on PATH. The atlas itself
is never scaled. yuv420p is not used: ``libx264rgb`` at CRF 0 keeps the
scaled pixels, and falls back to ``libx264`` if that encoder is missing.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from spritepack.colors import is_color, parse_color
from spritepack.errors import SpritePackError
from spritepack.images import blit_rgb, composite_over, load_png, scale_nearest
from spritepack.meta import AnimMeta, AtlasMeta, FrameMeta, atlas_path
from spritepack.pack import crop


def ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def render_animation(
    meta: AtlasMeta, atlas: np.ndarray, anim: AnimMeta
) -> tuple[list[np.ndarray], list[int]]:
    """Return RGB canvases and per-frame GIF durations in milliseconds."""
    frames = meta.playback(anim)
    if not frames:
        raise SpritePackError(f"animation {anim.name} has no frames")
    sprites = [crop(atlas, *frame.rect) for frame in frames]
    canvases = _composite(meta, anim, frames, sprites)
    scale = anim.scale
    scaled = [scale_nearest(canvas, scale) for canvas in canvases]
    durations = [max(1, int(round(frame.duration_ms))) for frame in frames]
    return scaled, durations


def write_gif(frames: list[np.ndarray], durations_ms: list[int], dest: Path) -> None:
    images = _gif_images(frames)
    dest.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        dest,
        save_all=True,
        append_images=images[1:],
        duration=durations_ms,
        loop=0,
        disposal=2,
        optimize=False,
    )


def write_mp4(
    frames: list[np.ndarray], holds: list[int], fps: int, dest: Path
) -> None:
    """Repeat each pose for ``hold`` film frames at ``fps``.

    That is the intro kit's clock. The concat demuxer would snap those
    lengths onto a 25 fps grid, so the frames are written out one by one.
    """
    ffmpeg = ffmpeg_bin()
    if ffmpeg is None:
        raise SpritePackError("ffmpeg is not on PATH, so the MP4 was not written")
    if fps < 1:
        raise SpritePackError("fps must be >= 1")
    dest.parent.mkdir(parents=True, exist_ok=True)
    sequence: list[np.ndarray] = []
    for frame, hold in zip(frames, holds):
        if hold < 1:
            raise SpritePackError("hold_frames must be >= 1")
        sequence.extend([frame] * hold)
    with tempfile.TemporaryDirectory(prefix="spritepack-") as tmp:
        folder = Path(tmp)
        for index, frame in enumerate(sequence):
            Image.fromarray(_even_size(frame), "RGB").save(folder / f"f_{index:04d}.png")
        encoder = _encoder(ffmpeg)
        cmd = [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-framerate",
            str(fps),
            "-start_number",
            "0",
            "-i",
            str(folder / "f_%04d.png"),
            "-frames:v",
            str(len(sequence)),
            "-an",
            "-c:v",
            encoder,
            "-pix_fmt",
            "rgb24" if encoder == "libx264rgb" else "yuv420p",
            "-crf",
            "0" if encoder == "libx264rgb" else "18",
            "-preset",
            "veryfast",
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise SpritePackError(f"ffmpeg failed to write {dest.name}: {detail}") from exc


def load_atlas(meta: AtlasMeta) -> np.ndarray:
    path = atlas_path(meta)
    if not path.is_file():
        raise SpritePackError(f"atlas image {path} is missing")
    rgba, _mode = load_png(path)
    if (rgba.shape[1], rgba.shape[0]) != meta.size:
        raise SpritePackError(
            f"{path.name} is {rgba.shape[1]}×{rgba.shape[0]}, JSON says {meta.size[0]}×{meta.size[1]}"
        )
    return rgba


def _composite(
    meta: AtlasMeta,
    anim: AnimMeta,
    frames: list[FrameMeta],
    sprites: list[np.ndarray],
) -> list[np.ndarray]:
    background = anim.background or meta.default_background
    if is_color(background):
        return _on_color(sprites, frames, parse_color(background))
    path = _resolve_background(meta, background)
    bg, _mode = load_png(path)
    return _on_image(sprites, frames, anim, bg[..., :3])


def _on_color(
    sprites: list[np.ndarray], frames: list[FrameMeta], color: tuple[int, int, int]
) -> list[np.ndarray]:
    """Pin every frame's anchor to the same point and crop the union."""
    boxes = []
    for sprite, frame in zip(sprites, frames):
        ax, ay = frame.anchor
        boxes.append((-ax, -ay, sprite.shape[1], sprite.shape[0]))
    min_x = min(x for x, _y, _w, _h in boxes)
    min_y = min(y for _x, y, _w, _h in boxes)
    max_x = max(x + w for x, _y, w, _h in boxes)
    max_y = max(y + h for _x, y, _w, h in boxes)
    width = max_x - min_x
    height = max_y - min_y
    anchor_at = (-min_x, -min_y)
    out = []
    for sprite, frame in zip(sprites, frames):
        canvas = np.empty((height, width, 3), dtype=np.uint8)
        canvas[...] = color
        left = anchor_at[0] - frame.anchor[0]
        top = anchor_at[1] - frame.anchor[1]
        composite_over(canvas, sprite, left, top)
        out.append(canvas)
    return out


def _on_image(
    sprites: list[np.ndarray],
    frames: list[FrameMeta],
    anim: AnimMeta,
    background: np.ndarray,
) -> list[np.ndarray]:
    place = anim.place
    if place is None:
        place = (background.shape[1] // 2, background.shape[0] // 2)
    boxes = [(0, 0, background.shape[1], background.shape[0])]
    tops: list[tuple[int, int]] = []
    for sprite, frame in zip(sprites, frames):
        if anim.place_space == "top-left":
            left, top = place
        else:
            left = place[0] - frame.anchor[0]
            top = place[1] - frame.anchor[1]
        tops.append((left, top))
        boxes.append((left, top, sprite.shape[1], sprite.shape[0]))
    min_x = min(x for x, _y, _w, _h in boxes)
    min_y = min(y for _x, y, _w, _h in boxes)
    max_x = max(x + w for x, _y, w, _h in boxes)
    max_y = max(y + h for _x, y, _w, h in boxes)
    width = max_x - min_x
    height = max_y - min_y
    out = []
    for sprite, (left, top) in zip(sprites, tops):
        canvas = np.empty((height, width, 3), dtype=np.uint8)
        canvas[...] = background[0, 0]
        blit_rgb(canvas, background, -min_x, -min_y)
        composite_over(canvas, sprite, left - min_x, top - min_y)
        out.append(canvas)
    return out


def _resolve_background(meta: AtlasMeta, background: str) -> Path:
    path = Path(background)
    if path.is_file():
        return path
    if meta.path is not None:
        candidate = meta.path.parent / background
        if candidate.is_file():
            return candidate
    raise SpritePackError(f"background image {background} was not found")


def _gif_images(frames: list[np.ndarray]) -> list[Image.Image]:
    stacked = np.vstack([frame.reshape(-1, 3) for frame in frames])
    unique = np.unique(stacked, axis=0)
    if len(unique) <= 256:
        palette = Image.new("P", (1, 1))
        data = [int(channel) for rgb in unique for channel in rgb]
        data.extend([0] * (768 - len(data)))
        palette.putpalette(data)
        return [
            Image.fromarray(frame, "RGB").quantize(palette=palette, dither=Image.Dither.NONE)
            for frame in frames
        ]
    base = Image.fromarray(frames[0], "RGB").quantize(
        colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    out = [base]
    for frame in frames[1:]:
        out.append(
            Image.fromarray(frame, "RGB").quantize(palette=base, dither=Image.Dither.NONE)
        )
    return out


def _even_size(rgb: np.ndarray) -> np.ndarray:
    """yuv420p needs even sizes. libx264rgb does not, but a 1px pad is cheap."""
    height, width = rgb.shape[:2]
    pad_y = height % 2
    pad_x = width % 2
    if not pad_x and not pad_y:
        return rgb
    out = np.empty((height + pad_y, width + pad_x, 3), dtype=np.uint8)
    out[...] = rgb[0, 0]
    out[:height, :width] = rgb
    if pad_x:
        out[:height, width] = rgb[:, width - 1]
    if pad_y:
        out[height, :width] = rgb[height - 1]
    if pad_x and pad_y:
        out[height, width] = rgb[height - 1, width - 1]
    return out


def _encoder(ffmpeg: str) -> str:
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return "libx264"
    if "libx264rgb" in proc.stdout:
        return "libx264rgb"
    return "libx264"
