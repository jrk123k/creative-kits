"""Atlas JSON. One document describes the PNG, the animations, and each frame."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from spritepack.errors import SpritePackError

FORMAT = "kit-sprite-packer"
VERSION = 1


@dataclass
class FrameMeta:
    id: str
    animation: str
    index: int
    file: str
    role: str | None
    naming: str
    mode: str
    rect: tuple[int, int, int, int]
    duration_ms: float
    hold_frames: int
    anchor: tuple[int, int]


@dataclass
class AnimMeta:
    name: str
    kind: str
    naming: str
    frames: list[str]
    cycle_mode: str
    skip_last: int
    mouth: dict | None = None
    patch: dict | None = None
    background: str | None = None
    place: tuple[int, int] | None = None
    place_space: str = "anchor"
    scale: int = 1
    kit_place: tuple[int, int] | None = None
    kit_top_left: tuple[int, int] | None = None


@dataclass
class AtlasMeta:
    image: str
    size: tuple[int, int]
    padding: int
    max_width: int
    fps: int
    default_hold: int
    default_duration_ms: float
    default_anchor: str
    default_scale: int
    default_background: str
    animations: list[AnimMeta] = field(default_factory=list)
    frames: list[FrameMeta] = field(default_factory=list)
    path: Path | None = None

    def frame(self, ident: str) -> FrameMeta:
        for item in self.frames:
            if item.id == ident:
                return item
        raise SpritePackError(f"atlas has no frame {ident}")

    def animation(self, name: str) -> AnimMeta:
        for item in self.animations:
            if item.name == name:
                return item
        raise SpritePackError(f"atlas has no animation {name}")

    def playback(self, anim: AnimMeta) -> list[FrameMeta]:
        return [self.frame(ident) for ident in anim.frames]


def dump(meta: AtlasMeta) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "image": meta.image,
        "size": {"w": meta.size[0], "h": meta.size[1]},
        "padding": meta.padding,
        "max_width": meta.max_width,
        "fps": meta.fps,
        "default_hold": meta.default_hold,
        "default_duration_ms": meta.default_duration_ms,
        "default_anchor": meta.default_anchor,
        "default_scale": meta.default_scale,
        "default_background": meta.default_background,
        "animations": [_anim_dict(anim) for anim in meta.animations],
        "frames": [_frame_dict(frame) for frame in meta.frames],
    }


def write(meta: AtlasMeta, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dump(meta), indent=2) + "\n")
    meta.path = path


def read(path: Path) -> AtlasMeta:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SpritePackError(f"could not parse {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise SpritePackError(f"{path} is not an {FORMAT} JSON")
    if data.get("version") != VERSION:
        raise SpritePackError(f"{path} is version {data.get('version')}, this packer reads {VERSION}")
    size = data["size"]
    meta = AtlasMeta(
        image=str(data["image"]),
        size=(int(size["w"]), int(size["h"])),
        padding=int(data["padding"]),
        max_width=int(data["max_width"]),
        fps=int(data["fps"]),
        default_hold=int(data["default_hold"]),
        default_duration_ms=float(data["default_duration_ms"]),
        default_anchor=str(data["default_anchor"]),
        default_scale=int(data["default_scale"]),
        default_background=str(data["default_background"]),
        path=path,
    )
    for raw in data["frames"]:
        rect = raw["rect"]
        anchor = raw["anchor"]
        meta.frames.append(
            FrameMeta(
                id=str(raw["id"]),
                animation=str(raw["animation"]),
                index=int(raw["index"]),
                file=str(raw["file"]),
                role=raw.get("role"),
                naming=str(raw["naming"]),
                mode=str(raw["mode"]),
                rect=(int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])),
                duration_ms=float(raw["duration_ms"]),
                hold_frames=int(raw["hold_frames"]),
                anchor=(int(anchor["x"]), int(anchor["y"])),
            )
        )
    for raw in data["animations"]:
        place = raw.get("place")
        kit_place = raw.get("kit_place")
        kit_top_left = raw.get("kit_top_left")
        meta.animations.append(
            AnimMeta(
                name=str(raw["name"]),
                kind=str(raw["kind"]),
                naming=str(raw["naming"]),
                frames=list(raw["frames"]),
                cycle_mode=str(raw["cycle"]["mode"]),
                skip_last=int(raw["cycle"].get("skip_last") or 0),
                mouth=raw.get("mouth"),
                patch=raw.get("patch"),
                background=raw.get("background"),
                place=(int(place["x"]), int(place["y"])) if place else None,
                place_space=str(raw.get("place_space") or "anchor"),
                scale=int(raw.get("scale") or meta.default_scale),
                kit_place=(int(kit_place["x"]), int(kit_place["y"])) if kit_place else None,
                kit_top_left=(int(kit_top_left["x"]), int(kit_top_left["y"])) if kit_top_left else None,
            )
        )
    return meta


def atlas_path(meta: AtlasMeta) -> Path:
    if meta.path is None:
        raise SpritePackError("atlas JSON has not been saved")
    return meta.path.parent / meta.image


def _frame_dict(frame: FrameMeta) -> dict:
    return {
        "id": frame.id,
        "animation": frame.animation,
        "index": frame.index,
        "file": frame.file,
        "role": frame.role,
        "naming": frame.naming,
        "mode": frame.mode,
        "rect": {"x": frame.rect[0], "y": frame.rect[1], "w": frame.rect[2], "h": frame.rect[3]},
        "duration_ms": frame.duration_ms,
        "hold_frames": frame.hold_frames,
        "anchor": {"x": frame.anchor[0], "y": frame.anchor[1]},
    }


def _anim_dict(anim: AnimMeta) -> dict:
    body = {
        "name": anim.name,
        "kind": anim.kind,
        "naming": anim.naming,
        "frames": list(anim.frames),
        "cycle": {"mode": anim.cycle_mode, "skip_last": anim.skip_last},
        "scale": anim.scale,
        "place_space": anim.place_space,
    }
    if anim.mouth:
        body["mouth"] = anim.mouth
    if anim.patch:
        body["patch"] = anim.patch
    if anim.background is not None:
        body["background"] = anim.background
    if anim.place is not None:
        body["place"] = {"x": anim.place[0], "y": anim.place[1]}
    if anim.kit_place is not None:
        body["kit_place"] = {"x": anim.kit_place[0], "y": anim.kit_place[1]}
    if anim.kit_top_left is not None:
        body["kit_top_left"] = {"x": anim.kit_top_left[0], "y": anim.kit_top_left[1]}
    return body
