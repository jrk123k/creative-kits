"""Write files the 16-bit intro kit can load.

The kit does not read atlases. It reads a YAML project and one PNG per frame.
``x`` and ``y`` on a sprite are the top-left of the frame on the 256×224 plate.
This adapter turns an anchor planted at ``kit_place`` into that top-left:

    x = kit_place_x - anchor_x
    y = kit_place_y - anchor_y

``cycle.hold`` is one number. When frames have different ``hold_frames``, the
frame is listed more than once. See ``timing.kit_cycle``.

Mouth plates have to be 256×224. A smaller A/B pair is still described in
``mapping.yaml``, and the loadable ``intro.yaml`` treats it as a sprite.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import yaml

from spritepack.errors import SpritePackError
from spritepack.images import load_png, save_png
from spritepack.meta import AnimMeta, AtlasMeta, FrameMeta, atlas_path, read
from spritepack.mouth import crop as crop_box
from spritepack.pack import crop
from spritepack.timing import kit_cycle

PLATE_W = 256
PLATE_H = 224
DEFAULT_KIT_PLACE = (128, 200)


def write_kit(
    meta: AtlasMeta,
    out_dir: Path,
    *,
    places: dict[str, tuple[int, int]] | None = None,
    plate: Path | None = None,
    plate_color: tuple[int, int, int] = (0, 0, 36),
    name: str = "kit-sprites",
) -> Path:
    """Unpack frames and write ``intro.yaml`` plus ``mapping.yaml``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    art = out_dir / "art"
    art.mkdir(parents=True, exist_ok=True)
    atlas = _load(meta)
    _unpack_art(meta, atlas, art)

    mouths = [anim for anim in meta.animations if anim.kind == "mouth"]
    sprites = [anim for anim in meta.animations if anim.kind != "mouth"]
    mapping = {
        "mouths": {},
        "sprites": {},
    }
    kit_mouths = {}
    kit_sprites = []
    notes = []
    for anim in mouths:
        entry, note = _mouth_entry(meta, anim, art, atlas)
        mapping["mouths"][anim.name] = entry
        if note:
            notes.append(note)
        closed = meta.frame(anim.mouth["closed"])
        if (closed.rect[2], closed.rect[3]) == (PLATE_W, PLATE_H):
            kit_mouths[anim.name] = entry
        else:
            sprites.append(anim)
            notes.append(
                f"{anim.name} is a mouth pair but not 256×224, so intro.yaml uses it as a sprite."
            )

    if sprites:
        _write_plate(art / "plate_256.png", plate, plate_color)

    for anim in sprites:
        mapping["sprites"][anim.name] = _sprite_entry(meta, anim, places)
        kit_sprites.append(anim)

    _write_mapping(out_dir / "mapping.yaml", mapping, meta, notes)
    intro_path = out_dir / "intro.yaml"
    _write_intro(intro_path, meta, kit_mouths, kit_sprites, places, name)
    return intro_path


def sprite_top_left(
    anchor: tuple[int, int], place: tuple[int, int]
) -> tuple[int, int]:
    return place[0] - anchor[0], place[1] - anchor[1]


def expanded_files(meta: AtlasMeta, anim: AnimMeta) -> tuple[int, list[str]]:
    frames = meta.playback(anim)
    hold, repeats = kit_cycle([frame.hold_frames for frame in frames])
    files: list[str] = []
    for frame, count in zip(frames, repeats):
        files.extend([f"art/{frame.file}"] * count)
    return hold, files


def _mouth_entry(meta, anim: AnimMeta, art: Path, atlas: np.ndarray) -> tuple[dict, str | None]:
    if not anim.mouth or "closed" not in anim.mouth or "open" not in anim.mouth:
        raise SpritePackError(f"mouth animation {anim.name} is missing closed and open frames")
    closed = meta.frame(anim.mouth["closed"])
    opened = meta.frame(anim.mouth["open"])
    entry = {
        "closed": f"art/{closed.file}",
        "open": f"art/{opened.file}",
    }
    note = None
    patch = anim.patch
    if patch is None:
        return entry, note
    filename = patch.get("file") or f"{anim.name}_open_patch.png"
    dest = art / Path(filename).name
    if patch.get("frame"):
        # Already unpacked with the other frames.
        packed = meta.frame(patch["frame"])
        if not dest.is_file():
            save_png(dest, crop(atlas, *packed.rect), "RGB")
    else:
        opened_px = crop(atlas, *opened.rect)
        box = (int(patch["x"]), int(patch["y"]), int(patch["w"]), int(patch["h"]))
        save_png(dest, crop_box(opened_px, box), "RGB")
    entry["patch"] = {"image": f"art/{dest.name}", "x": int(patch["x"]), "y": int(patch["y"])}
    return entry, note


def _sprite_entry(meta: AtlasMeta, anim: AnimMeta, places: dict[str, tuple[int, int]] | None) -> dict:
    frames = meta.playback(anim)
    anchor = _anchor_for_kit(frames)
    place, space = _kit_place(anim, places)
    if space == "top-left":
        x, y = place
    else:
        x, y = sprite_top_left(anchor, place)
    hold, files = expanded_files(meta, anim)
    mode = anim.cycle_mode if anim.cycle_mode in ("loop", "once") else "loop"
    entry = {
        "id": anim.name,
        "frames": files,
        "x": x,
        "y": y,
        "anchor": {"x": anchor[0], "y": anchor[1]},
        "kit_place": {"x": place[0], "y": place[1], "space": space},
        "cycle": {"mode": mode, "hold": hold, "skip_last": anim.skip_last},
    }
    if len(files) == 1:
        entry["image"] = files[0]
    return entry


def _anchor_for_kit(frames: list[FrameMeta]) -> tuple[int, int]:
    anchor = frames[0].anchor
    if any(frame.anchor != anchor for frame in frames[1:]):
        # The kit has one top-left for the whole cycle. The first frame wins.
        return anchor
    return anchor


def _kit_place(
    anim: AnimMeta, places: dict[str, tuple[int, int]] | None
) -> tuple[tuple[int, int], str]:
    if places and anim.name in places:
        return places[anim.name], "anchor"
    if anim.kit_top_left is not None:
        return anim.kit_top_left, "top-left"
    if anim.kit_place is not None:
        return anim.kit_place, "anchor"
    return DEFAULT_KIT_PLACE, "anchor"


def _write_mapping(path: Path, mapping: dict, meta: AtlasMeta, notes: list[str]) -> None:
    header = [
        "# Kit sprite packer → 16-bit intro kit.",
        "#",
        "# The kit pastes a sprite by its top-left. The packer stores an anchor.",
        "#   x = kit_place.x - anchor.x",
        "#   y = kit_place.y - anchor.y",
        "# Default anchor is bottom-center: x = width // 2, y = height.",
        "# A 14×12 cow anchored at (7, 12) and planted at (160, 176) is x=153, y=164.",
        "#",
        "# cycle.hold is one integer. hold_frames that differ share their greatest",
        "# common divisor, and the longer frame is listed more than once.",
        f"# Packed at {meta.fps} fps. default hold {meta.default_hold} "
        f"({meta.default_duration_ms} ms), which is the kit's cycle.hold default of 4 at 30 fps.",
        "# Mouth flip rate is vocals.hold_frames, also 4 unless the line below says otherwise.",
        "#",
    ]
    for note in notes:
        header.append(f"# {note}")
    body = yaml.safe_dump(mapping, sort_keys=False)
    path.write_text("\n".join(header) + "\n" + body)


def _write_intro(
    path: Path,
    meta: AtlasMeta,
    mouths: dict,
    sprites: list[AnimMeta],
    places: dict[str, tuple[int, int]] | None,
    name: str,
) -> None:
    seconds = max(1, len(mouths) + (1 if sprites else 0))
    audio = path.parent / "audio" / "silence.wav"
    _write_silence(audio, seconds)
    scenes = []
    cursor = 0.0
    for mouth_name in mouths:
        scenes.append(
            {
                "id": mouth_name,
                "type": "still",
                "start": cursor,
                "end": cursor + 1.0,
                "cut": "hard",
                "mouth": mouth_name,
            }
        )
        cursor += 1.0
    if sprites:
        layers = [{"type": "image", "image": "art/plate_256.png"}]
        for anim in sprites:
            entry = _sprite_entry(meta, anim, places)
            layer = {
                "type": "sprite",
                "id": anim.name,
                "frames": entry["frames"],
                "x": entry["x"],
                "y": entry["y"],
                "cycle": {
                    "mode": entry["cycle"]["mode"],
                    "hold": entry["cycle"]["hold"],
                    "skip_last": entry["cycle"]["skip_last"],
                },
            }
            if len(entry["frames"]) == 1:
                layer = {
                    "type": "sprite",
                    "id": anim.name,
                    "image": entry["frames"][0],
                    "x": entry["x"],
                    "y": entry["y"],
                }
            elif entry["cycle"]["mode"] == "once":
                # A once cycle needs the show window. The sprite scene is one second.
                start = int(round(cursor * meta.fps))
                layer["show_frames"] = [start, start + meta.fps]
            layers.append(layer)
        scenes.append(
            {
                "id": "sprites",
                "type": "stack",
                "start": cursor,
                "end": cursor + 1.0,
                "cut": "hard",
                "layers": layers,
            }
        )
    if not scenes:
        raise SpritePackError("nothing to adapt")
    if not 1 <= meta.fps <= 60:
        raise SpritePackError(
            f"intro kit fps must be 1..60, the atlas is {meta.fps}. Repack with --fps in that range."
        )
    mouth_hold = meta.default_hold
    if mouths:
        first = meta.animation(next(iter(mouths)))
        closed_id = first.mouth["closed"] if first.mouth else None
        if closed_id:
            mouth_hold = meta.frame(closed_id).hold_frames
    doc = {
        "version": 1,
        "name": name,
        "description": "Generated by Kit Sprite Packer from an atlas JSON.",
        "fps": meta.fps,
        "width": PLATE_W,
        "height": PLATE_H,
        "palette": "off",
        "audio": {
            "file": "audio/silence.wav",
            "duration": float(seconds),
            "tail": {"duration": 0, "source": "none"},
        },
        "scenes": scenes,
    }
    if mouths:
        doc["mouths"] = mouths
        lines = []
        for index, _mouth_name in enumerate(mouths):
            # Each line sits inside that mouth's still scene. The kit uses the
            # scene's mouth, and the last frame of the line stays closed.
            lines.append({"start": float(index), "end": float(index) + 0.8, "text": "HELLO"})
        doc["vocals"] = {"hold_frames": mouth_hold, "lines": lines}
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _write_plate(dest: Path, plate: Path | None, plate_color: tuple[int, int, int]) -> None:
    if plate is not None:
        rgba, _mode = load_png(plate)
        if (rgba.shape[1], rgba.shape[0]) != (PLATE_W, PLATE_H):
            raise SpritePackError(
                f"kit plate {plate.name} is {rgba.shape[1]}×{rgba.shape[0]}, the kit frame is 256×224"
            )
        save_png(dest, rgba, "RGB")
        return
    solid = np.empty((PLATE_H, PLATE_W, 4), dtype=np.uint8)
    solid[..., 0] = plate_color[0]
    solid[..., 1] = plate_color[1]
    solid[..., 2] = plate_color[2]
    solid[..., 3] = 255
    save_png(dest, solid, "RGB")


def _unpack_art(meta: AtlasMeta, atlas: np.ndarray, art: Path) -> None:
    seen: set[str] = set()
    for frame in meta.frames:
        if frame.file in seen:
            continue
        seen.add(frame.file)
        save_png(art / frame.file, crop(atlas, *frame.rect), frame.mode)


def _load(meta: AtlasMeta) -> np.ndarray:
    path = atlas_path(meta)
    rgba, _mode = load_png(path)
    return rgba


def _write_silence(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(round(44100 * seconds))
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * count)


def adapt_file(
    json_path: Path,
    out_dir: Path,
    *,
    places: dict[str, tuple[int, int]] | None = None,
    plate: Path | None = None,
    plate_color: tuple[int, int, int] = (0, 0, 36),
    name: str = "kit-sprites",
) -> Path:
    meta = read(json_path)
    return write_kit(
        meta,
        out_dir,
        places=places,
        plate=plate,
        plate_color=plate_color,
        name=name,
    )

