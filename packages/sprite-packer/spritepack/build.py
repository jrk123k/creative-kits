"""Pack a folder into an atlas, JSON, and previews."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from spritepack.anchors import resolve_anchor
from spritepack.colors import color_hex, is_color, parse_color
from spritepack.discover import (
    AnimSpec,
    Found,
    FrameOverride,
    Sidecar,
    apply_sidecar,
    discover,
    find_sidecar,
    load_sidecar,
    pngs_in,
)
from spritepack.errors import SpritePackError
from spritepack.images import load_png, save_png
from spritepack.meta import AnimMeta, AtlasMeta, FrameMeta, read, write
from spritepack.mouth import diff_box, locate_patch, paste_rgb, rgb_equal
from spritepack.pack import blit, crop, shelf_pack
from spritepack.preview import ffmpeg_bin, load_atlas, render_animation, write_gif, write_mp4
from spritepack.timing import duration_from_hold, hold_from_duration

DEFAULT_BACKGROUND = "#000000"


@dataclass
class Loaded:
    found: Found
    pixels: np.ndarray
    mode: str
    duration_ms: float = 0
    hold_frames: int = 1
    anchor: tuple[int, int] = (0, 0)
    ident: str = ""


@dataclass
class Built:
    meta: AtlasMeta
    json_path: Path
    atlas_path: Path
    previews: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def pack_folder(
    folder: Path,
    out_dir: Path,
    *,
    name: str | None = None,
    padding: int = 0,
    max_width: int = 4096,
    fps: int = 30,
    hold: int = 4,
    duration_ms: float | None = None,
    anchor: object = "bottom-center",
    background: str | None = None,
    scale: int = 4,
    place: tuple[int, int] | None = None,
    place_space: str = "anchor",
    places: dict[str, tuple[int, int]] | None = None,
    kit_place: tuple[int, int] | None = None,
    sidecar_path: Path | None = None,
    frame_durations: dict[str, float] | None = None,
    frame_anchors: dict[str, tuple[int, int]] | None = None,
    gif: bool = True,
    mp4: bool = True,
) -> Built:
    folder = folder.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if scale < 1:
        raise SpritePackError("scale must be an integer >= 1")
    if hold < 1:
        raise SpritePackError("hold must be >= 1")
    if fps < 1:
        raise SpritePackError("fps must be >= 1")

    sidecar = _sidecar(folder, sidecar_path)
    project_fps = sidecar.fps if sidecar and sidecar.fps else fps
    paths = pngs_in(folder)
    if sidecar and sidecar.manifest_groups is not None:
        found = apply_sidecar([], sidecar, folder)
    else:
        found = discover(paths)
        if sidecar:
            found = apply_sidecar(found, sidecar, folder)
    if not found:
        raise SpritePackError(f"no PNG frames in {folder}")

    groups = _group(found)
    loaded_groups: list[tuple[str, list[Loaded], list[Loaded]]] = []
    for anim_name, items in groups:
        spec = sidecar.animations.get(anim_name) if sidecar else None
        playback, patches = _split(items)
        if not playback:
            raise SpritePackError(f"animation {anim_name} has no frames")
        loaded_play = [
            _load_one(
                item,
                spec,
                sidecar,
                project_fps,
                hold,
                duration_ms,
                anchor,
                frame_durations or {},
                frame_anchors or {},
            )
            for item in playback
        ]
        loaded_patches = [
            _load_one(
                item,
                spec,
                sidecar,
                project_fps,
                hold,
                duration_ms,
                anchor,
                frame_durations or {},
                frame_anchors or {},
            )
            for item in patches
        ]
        loaded_groups.append((anim_name, loaded_play, loaded_patches))

    animations, frames = _describe(
        loaded_groups,
        sidecar,
        folder,
        out_dir,
        background,
        scale,
        place,
        place_space,
        places or {},
        kit_place,
    )
    _mouths(animations, frames, loaded_groups, sidecar)

    pack_items = [(frame.ident, frame.pixels.shape[1], frame.pixels.shape[0]) for _name, play, patches in loaded_groups for frame in play + patches]
    # Stable shelf order: tallest first, then widest, then id.
    by_id = {frame.ident: frame for _n, play, patches in loaded_groups for frame in play + patches}
    pack_items.sort(key=lambda item: (-item[2], -item[1], item[0]))
    placed, atlas_w, atlas_h = shelf_pack(pack_items, padding, max_width)
    atlas = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
    rect_of = {}
    for ident, x, y, w, h in placed:
        blit(atlas, by_id[ident].pixels, x, y)
        rect_of[ident] = (x, y, w, h)

    stem = name or folder.name
    image_name = f"{stem}.png"
    default_hold_value, default_ms = _defaults(
        sidecar, project_fps, hold, duration_ms
    )
    meta = AtlasMeta(
        image=image_name,
        size=(atlas_w, atlas_h),
        padding=padding,
        max_width=max_width,
        fps=project_fps,
        default_hold=default_hold_value,
        default_duration_ms=default_ms,
        default_anchor=anchor if isinstance(anchor, str) else "custom",
        default_scale=scale,
        default_background=_color_or_none(background) or DEFAULT_BACKGROUND,
        animations=animations,
        frames=[],
    )
    for frame in frames:
        rect = rect_of[frame.ident]
        meta.frames.append(
            FrameMeta(
                id=frame.ident,
                animation=frame.found.animation,
                index=frame.found.index,
                file=frame.found.file,
                role=frame.found.role,
                naming=frame.found.naming,
                mode=_save_mode(frame.mode),
                rect=rect,
                duration_ms=frame.duration_ms,
                hold_frames=frame.hold_frames,
                anchor=frame.anchor,
            )
        )

    atlas_file = out_dir / image_name
    json_file = out_dir / f"{stem}.json"
    save_png(atlas_file, atlas, "RGBA")
    # Reload so the JSON we hand to preview matches the file on disk.
    reloaded, _mode = load_png(atlas_file)
    if not np.array_equal(reloaded, atlas):
        raise SpritePackError(f"{image_name} did not round-trip through PNG")
    meta.path = json_file
    write(meta, json_file)

    built = Built(meta=meta, json_path=json_file, atlas_path=atlas_file)
    if gif or mp4:
        _write_previews(meta, reloaded, out_dir, gif, mp4, built)
    return built


def unpack_folder(json_path: Path, out_dir: Path) -> list[Path]:
    meta = read(json_path)
    atlas = load_atlas(meta)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for frame in meta.frames:
        dest = out_dir / frame.file
        save_png(dest, crop(atlas, *frame.rect), frame.mode)
        written.append(dest)
    return written


def _sidecar(folder: Path, path: Path | None) -> Sidecar | None:
    if path is None:
        path = find_sidecar(folder)
    if path is None:
        return None
    if not path.is_file():
        raise SpritePackError(f"sidecar {path} was not found")
    return load_sidecar(path)


def _group(found: list[Found]) -> list[tuple[str, list[Found]]]:
    order: list[str] = []
    groups: dict[str, list[Found]] = {}
    for item in found:
        if item.animation not in groups:
            order.append(item.animation)
            groups[item.animation] = []
        groups[item.animation].append(item)
    return [(name, groups[name]) for name in order]


def _split(items: list[Found]) -> tuple[list[Found], list[Found]]:
    patches = [item for item in items if item.role == "patch"]
    play = [item for item in items if item.role != "patch"]
    play.sort(key=lambda item: (item.index, item.file))
    return play, patches


def _load_one(
    item: Found,
    spec: AnimSpec | None,
    sidecar: Sidecar | None,
    project_fps: int,
    cli_hold: int,
    cli_duration: float | None,
    cli_anchor,
    frame_durations: dict[str, float],
    frame_anchors: dict[str, tuple[int, int]],
) -> Loaded:
    pixels, mode = load_png(item.path)
    duration, hold_frames = _timing(
        item, spec, sidecar, project_fps, cli_hold, cli_duration, frame_durations
    )
    anchor = _anchor(item, pixels.shape, spec, sidecar, cli_anchor, frame_anchors)
    return Loaded(
        found=item,
        pixels=pixels,
        mode=mode,
        duration_ms=duration,
        hold_frames=hold_frames,
        anchor=anchor,
        ident=item.path.stem,
    )


def _timing(
    item: Found,
    spec: AnimSpec | None,
    sidecar: Sidecar | None,
    project_fps: int,
    cli_hold: int,
    cli_duration: float | None,
    frame_durations: dict[str, float],
) -> tuple[float, int]:
    override = _override(item, spec)
    cli_ms = _lookup(frame_durations, item)
    if cli_ms is not None:
        return float(cli_ms), hold_from_duration(float(cli_ms), project_fps)
    if override and override.duration_ms is not None:
        return override.duration_ms, hold_from_duration(override.duration_ms, project_fps)
    if override and override.hold is not None:
        return _from_hold(override.hold, _local_fps(spec, sidecar, project_fps), project_fps)
    if spec and spec.duration_ms is not None:
        return spec.duration_ms, hold_from_duration(spec.duration_ms, project_fps)
    if spec and spec.hold is not None:
        return _from_hold(spec.hold, spec.fps or _local_fps(spec, sidecar, project_fps), project_fps)
    if sidecar and sidecar.duration_ms is not None:
        return sidecar.duration_ms, hold_from_duration(sidecar.duration_ms, project_fps)
    if sidecar and sidecar.hold is not None:
        return _from_hold(sidecar.hold, sidecar.fps or project_fps, project_fps)
    if cli_duration is not None:
        return float(cli_duration), hold_from_duration(float(cli_duration), project_fps)
    return _from_hold(cli_hold, project_fps, project_fps)


def _from_hold(hold: int, base_fps: int, project_fps: int) -> tuple[float, int]:
    if base_fps == project_fps:
        return duration_from_hold(hold, project_fps), hold
    duration = duration_from_hold(hold, base_fps)
    return duration, hold_from_duration(duration, project_fps)


def _local_fps(spec: AnimSpec | None, sidecar: Sidecar | None, project_fps: int) -> int:
    if spec and spec.fps:
        return spec.fps
    if sidecar and sidecar.fps:
        return sidecar.fps
    return project_fps


def _override(item: Found, spec: AnimSpec | None) -> FrameOverride | None:
    if spec is None:
        return None
    for key in (item.file, item.path.stem, str(item.index)):
        if key in spec.frames:
            return spec.frames[key]
    return None


def _lookup(table: dict, item: Found):
    for key in (item.file, item.path.stem, str(item.index)):
        if key in table:
            return table[key]
    return None


def _anchor(item, shape, spec, sidecar, cli_anchor, frame_anchors) -> tuple[int, int]:
    height, width = shape[:2]
    explicit = _lookup(frame_anchors, item)
    if explicit is not None:
        return resolve_anchor(explicit, width, height)
    override = _override(item, spec)
    if override and override.anchor is not None:
        return resolve_anchor(override.anchor, width, height)
    if spec and spec.anchor is not None:
        return resolve_anchor(spec.anchor, width, height)
    if sidecar and sidecar.anchor is not None:
        return resolve_anchor(sidecar.anchor, width, height)
    return resolve_anchor(cli_anchor, width, height)


def _describe(
    groups,
    sidecar: Sidecar | None,
    folder: Path,
    out_dir: Path,
    cli_background: str | None,
    cli_scale: int,
    cli_place,
    cli_space: str,
    cli_places: dict[str, tuple[int, int]],
    cli_kit_place,
) -> tuple[list[AnimMeta], list[Loaded]]:
    animations = []
    frames: list[Loaded] = []
    sidecar_dir = sidecar.path.parent if sidecar else folder
    for name, play, patches in groups:
        spec = sidecar.animations.get(name) if sidecar else None
        kind = "mouth" if any(item.found.role == "closed" for item in play) and any(
            item.found.role == "open" for item in play
        ) else ("plate" if play[0].found.naming == "plate" else "sprite")
        mode = (spec.cycle_mode if spec and spec.cycle_mode else "loop")
        if mode not in ("loop", "once"):
            raise SpritePackError(f"{name} cycle mode must be once or loop")
        skip = spec.skip_last if spec and spec.skip_last is not None else 0
        if skip < 0:
            raise SpritePackError(f"{name} skip_last must be >= 0")
        background = _first(
            spec.background if spec else None,
            sidecar.background if sidecar else None,
            cli_background,
            DEFAULT_BACKGROUND,
        )
        scale = _first(spec.scale if spec else None, sidecar.scale if sidecar else None, cli_scale)
        if scale < 1:
            raise SpritePackError(f"{name} scale must be >= 1")
        place = cli_places.get(name)
        if place is None:
            place = _first(spec.place if spec else None, sidecar.place if sidecar else None, cli_place)
        space = _first(
            spec.place_space if spec else None,
            sidecar.place_space if sidecar else None,
            cli_space,
        )
        kit_place = spec.kit_place if spec and spec.kit_place else cli_kit_place
        kit_top_left = spec.kit_top_left if spec else None
        mouth = None
        if kind == "mouth":
            closed = next(item.ident for item in play if item.found.role == "closed")
            opened = next(item.ident for item in play if item.found.role == "open")
            mouth = {"closed": closed, "open": opened}
        animations.append(
            AnimMeta(
                name=name,
                kind=kind,
                naming=play[0].found.naming,
                frames=[item.ident for item in play],
                cycle_mode=mode,
                skip_last=skip,
                mouth=mouth,
                background=_store_background(background, out_dir, sidecar_dir),
                place=place,
                place_space=space or "anchor",
                scale=int(scale),
                kit_place=kit_place,
                kit_top_left=kit_top_left,
            )
        )
        frames.extend(play)
        frames.extend(patches)
    return animations, frames


def _mouths(animations: list[AnimMeta], frames: list[Loaded], groups, sidecar: Sidecar | None) -> None:
    by_id = {frame.ident: frame for frame in frames}
    group_patches = {name: patches for name, _play, patches in groups}
    for anim in animations:
        if anim.kind != "mouth" or not anim.mouth:
            continue
        closed = by_id[anim.mouth["closed"]]
        opened = by_id[anim.mouth["open"]]
        box = diff_box(closed.pixels, opened.pixels)
        patches = group_patches.get(anim.name, [])
        spec = sidecar.animations.get(anim.name) if sidecar else None
        if patches:
            patch = patches[0]
            origin = spec.patch_origin if spec else None
            if origin is not None:
                pasted = paste_rgb(closed.pixels, patch.pixels, origin[0], origin[1])
                if not rgb_equal(pasted, opened.pixels):
                    raise SpritePackError(
                        f"{anim.name} patch at {origin[0]},{origin[1]} does not reproduce the open frame"
                    )
                x, y = origin
            else:
                x, y = locate_patch(closed.pixels, opened.pixels, patch.pixels)
            anim.patch = {
                "frame": patch.ident,
                "file": patch.found.file,
                "x": x,
                "y": y,
                "w": int(patch.pixels.shape[1]),
                "h": int(patch.pixels.shape[0]),
            }
        elif box is not None:
            x, y, w, h = box
            anim.patch = {"frame": None, "file": None, "x": x, "y": y, "w": w, "h": h}


def _write_previews(meta, atlas, out_dir: Path, gif: bool, mp4: bool, built: Built) -> None:
    for anim in meta.animations:
        if anim.kind == "plate" and len(anim.frames) == 1 and anim.mouth is None:
            # A lone plate still gets a preview. Patches are not their own animation.
            pass
        frames, durations = render_animation(meta, atlas, anim)
        if gif:
            dest = out_dir / f"{anim.name}.gif"
            write_gif(frames, durations, dest)
            built.previews.append(dest)
        if mp4:
            if ffmpeg_bin() is None:
                built.warnings.append(
                    f"ffmpeg is not on PATH, so {anim.name}.mp4 was not written"
                )
                mp4 = False
                continue
            dest = out_dir / f"{anim.name}.mp4"
            holds = [meta.frame(ident).hold_frames for ident in anim.frames]
            write_mp4(frames, holds, meta.fps, dest)
            built.previews.append(dest)


def _store_background(value: str, out_dir: Path, sidecar_dir: Path) -> str:
    if is_color(value):
        return color_hex(parse_color(value))
    path = Path(value)
    if not path.is_file():
        candidate = sidecar_dir / value
        if candidate.is_file():
            path = candidate
    if not path.is_file():
        raise SpritePackError(f"background {value} was not found")
    relative = os.path.relpath(path.resolve(), out_dir.resolve())
    return Path(relative).as_posix()


def _color_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    if is_color(value):
        return color_hex(parse_color(value))
    return value


def _save_mode(mode: str) -> str:
    if mode == "RGB":
        return "RGB"
    return "RGBA"


def _defaults(sidecar, project_fps: int, hold: int, duration_ms: float | None):
    if duration_ms is not None and not (sidecar and (sidecar.duration_ms is not None or sidecar.hold is not None)):
        return hold_from_duration(duration_ms, project_fps), float(duration_ms)
    if sidecar and sidecar.duration_ms is not None:
        return hold_from_duration(sidecar.duration_ms, project_fps), sidecar.duration_ms
    if sidecar and sidecar.hold is not None:
        base = sidecar.fps or project_fps
        return (
            sidecar.hold if base == project_fps else hold_from_duration(duration_from_hold(sidecar.hold, base), project_fps),
            duration_from_hold(sidecar.hold, base),
        )
    if duration_ms is not None:
        return hold_from_duration(duration_ms, project_fps), float(duration_ms)
    return hold, duration_from_hold(hold, project_fps)


def _first(*values):
    for value in values:
        if value is not None:
            return value
    return None


def preview_file(json_path: Path, out_dir: Path, *, gif: bool = True, mp4: bool = True,
                 scale: int | None = None, background: str | None = None) -> list[Path]:
    meta = read(json_path)
    if scale is not None:
        if scale < 1:
            raise SpritePackError("scale must be an integer >= 1")
        for anim in meta.animations:
            anim.scale = scale
    if background is not None:
        stored = background if not is_color(background) else color_hex(parse_color(background))
        for anim in meta.animations:
            anim.background = stored
    atlas = load_atlas(meta)
    built = Built(meta=meta, json_path=json_path, atlas_path=json_path.parent / meta.image)
    _write_previews(meta, atlas, out_dir, gif, mp4, built)
    for warning in built.warnings:
        print(warning)
    return built.previews
