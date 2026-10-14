"""Group a folder of PNGs the way Pixel Studio and the intro kit name them.

Checked in this order, on the filename only:

- ``{shot}_open_patch.png`` — mouth patch, not a playback frame
- ``{shot}_open_256.png`` — open plate
- ``{shot}_256.png`` — closed plate
- ``{shot}_sprite_{n}.png`` — sprite cycle
- ``{shot}_sprite.png`` — a one-frame sprite
- ``{shot}_{n}.png`` — ``cow_beam_0.png``, ``name_0.png``, ``{shot}_00.png``
- anything else — its own one-frame animation, unless it is ``{shot}_{label}.png``
  for a plate shot already in the folder (Pixel Studio's extra plate frames)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from spritepack.errors import SpritePackError

_OPEN_PATCH = re.compile(r"^(.+)_open_patch\.png$", re.IGNORECASE)
_OPEN_PLATE = re.compile(r"^(.+)_open_256\.png$", re.IGNORECASE)
_CLOSED_PLATE = re.compile(r"^(.+)_256\.png$", re.IGNORECASE)
_SPRITE_N = re.compile(r"^(.+)_sprite_(\d+)\.png$", re.IGNORECASE)
_SPRITE = re.compile(r"^(.+)_sprite\.png$", re.IGNORECASE)
_NUMBERED = re.compile(r"^(.+)_(\d+)\.png$", re.IGNORECASE)


@dataclass
class Found:
    path: Path
    animation: str
    index: int
    role: str | None
    naming: str

    @property
    def file(self) -> str:
        return self.path.name


@dataclass
class FrameOverride:
    duration_ms: float | None = None
    hold: int | None = None
    anchor: object | None = None


@dataclass
class AnimSpec:
    files: list[str] | None = None
    duration_ms: float | None = None
    hold: int | None = None
    fps: int | None = None
    anchor: object | None = None
    frames: dict[str, FrameOverride] = field(default_factory=dict)
    cycle_mode: str | None = None
    skip_last: int | None = None
    background: str | None = None
    place: tuple[int, int] | None = None
    place_space: str | None = None
    scale: int | None = None
    kit_place: tuple[int, int] | None = None
    kit_top_left: tuple[int, int] | None = None
    mouth_closed: str | None = None
    mouth_open: str | None = None
    patch_origin: tuple[int, int] | None = None


@dataclass
class Sidecar:
    kind: str
    path: Path
    fps: int | None = None
    hold: int | None = None
    duration_ms: float | None = None
    anchor: object | None = None
    background: str | None = None
    place: tuple[int, int] | None = None
    place_space: str | None = None
    scale: int | None = None
    animations: dict[str, AnimSpec] = field(default_factory=dict)
    # Pixel Studio manifests list the frames. None means "discover the folder".
    manifest_groups: dict[str, list[Found]] | None = None


def pngs_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise SpritePackError(f"{folder} is not a folder")
    found = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".png"
    ]
    return sorted(found, key=lambda path: path.name)


def classify(filename: str) -> tuple[str, int, str | None, str]:
    """Return ``(animation, index, role, naming)`` for one filename."""
    match = _OPEN_PATCH.match(filename)
    if match:
        return match.group(1), 0, "patch", "plate"
    match = _OPEN_PLATE.match(filename)
    if match:
        return match.group(1), 1, "open", "plate"
    match = _CLOSED_PLATE.match(filename)
    if match:
        return match.group(1), 0, "closed", "plate"
    match = _SPRITE_N.match(filename)
    if match:
        return match.group(1), int(match.group(2)), None, "sprite"
    match = _SPRITE.match(filename)
    if match:
        return match.group(1), 0, None, "sprite"
    match = _NUMBERED.match(filename)
    if match:
        return match.group(1), int(match.group(2)), None, "numbered"
    return Path(filename).stem, 0, None, "single"


def discover(paths: list[Path]) -> list[Found]:
    found = [
        Found(path, *classify(path.name))
        for path in paths
    ]
    _attach_plate_extras(found)
    _reject_mixed_naming(found)
    _reject_duplicate_indexes(found)
    return found


def find_sidecar(folder: Path) -> Path | None:
    for name in ("sprites.json", "manifest.json"):
        path = folder / name
        if path.is_file():
            return path
    return None


def load_sidecar(path: Path) -> Sidecar:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SpritePackError(f"could not parse {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise SpritePackError(f"{path.name} must be a JSON object")
    if "animations" in data or str(data.get("format", "")).startswith("kit"):
        return _load_packer_sidecar(path, data)
    if data and all(_is_studio_entry(value) for value in data.values()):
        return _load_studio_manifest(path, data)
    raise SpritePackError(
        f"{path.name} is not a sprites.json sidecar or a Pixel Studio manifest.json"
    )


def apply_sidecar(found: list[Found], sidecar: Sidecar, folder: Path) -> list[Found]:
    """Drop background plates and honor an explicit file list."""
    if sidecar.manifest_groups is not None:
        return _flatten_manifest(sidecar.manifest_groups)
    backgrounds = _background_names(sidecar)
    kept = [item for item in found if item.path.name not in backgrounds]
    if not sidecar.animations:
        return kept
    by_anim: dict[str, list[Found]] = {}
    for item in kept:
        by_anim.setdefault(item.animation, []).append(item)
    for name, spec in sidecar.animations.items():
        if spec.files is None:
            _apply_mouth_roles(by_anim.get(name, []), spec)
            continue
        groups = {item.file: item for item in by_anim.get(name, [])}
        ordered: list[Found] = []
        for filename in spec.files:
            item = groups.get(filename)
            if item is None:
                direct = folder / filename
                if not direct.is_file():
                    raise SpritePackError(
                        f"{sidecar.path.name}: {name} lists {filename}, which is not in the folder"
                    )
                item = Found(direct, *classify(direct.name))
                item.animation = name
            ordered.append(item)
        listed = {item.file for item in ordered}
        extras = [item for item in by_anim.get(name, []) if item.file not in listed and item.role != "patch"]
        if extras:
            names = ", ".join(item.file for item in extras)
            raise SpritePackError(
                f"{sidecar.path.name}: {name} has frames that are not in files: {names}"
            )
        patches = [item for item in by_anim.get(name, []) if item.role == "patch" and item.file not in listed]
        for index, item in enumerate(ordered):
            if item.role != "patch":
                item.index = index
        by_anim[name] = ordered + patches
        _apply_mouth_roles(by_anim[name], spec)
    # Animations the sidecar didn't mention stay discovered.
    ordered_names = list(sidecar.animations) + [
        name for name in by_anim if name not in sidecar.animations
    ]
    out: list[Found] = []
    for name in ordered_names:
        out.extend(by_anim.get(name, []))
    _reject_duplicate_indexes(out)
    return out


def _attach_plate_extras(found: list[Found]) -> None:
    plate_shots = sorted(
        {item.animation for item in found if item.naming == "plate" and item.role != "patch"},
        key=len,
        reverse=True,
    )
    if not plate_shots:
        return
    extras: dict[str, list[Found]] = {shot: [] for shot in plate_shots}
    for item in found:
        if item.naming != "single":
            continue
        stem = item.path.stem
        for shot in plate_shots:
            prefix = shot + "_"
            if stem.startswith(prefix) and stem[len(prefix) :]:
                item.animation = shot
                item.naming = "plate"
                item.role = stem[len(prefix) :]
                extras[shot].append(item)
                break
    for shot, items in extras.items():
        items.sort(key=lambda item: item.role or "")
        for offset, item in enumerate(items):
            item.index = 2 + offset


def _reject_mixed_naming(found: list[Found]) -> None:
    groups: dict[str, set[str]] = {}
    for item in found:
        if item.role == "patch":
            continue
        groups.setdefault(item.animation, set()).add(item.naming)
    for name, namings in groups.items():
        if len(namings) > 1:
            styles = ", ".join(sorted(namings))
            raise SpritePackError(
                f"animation {name} mixes file styles ({styles}). "
                "Use one of numbered, sprite, or plate names."
            )


def _reject_duplicate_indexes(found: list[Found]) -> None:
    seen: dict[tuple[str, int], str] = {}
    for item in found:
        if item.role == "patch":
            continue
        key = (item.animation, item.index)
        if key in seen:
            raise SpritePackError(
                f"animation {item.animation} has two frames at index {item.index}: "
                f"{seen[key]} and {item.file}"
            )
        seen[key] = item.file


def _is_studio_entry(value) -> bool:
    return isinstance(value, dict) and isinstance(value.get("frames"), list)


def _load_packer_sidecar(path: Path, data: dict) -> Sidecar:
    animations = data.get("animations") or {}
    if not isinstance(animations, dict):
        raise SpritePackError(f"{path.name}: animations must be an object")
    sidecar = Sidecar(
        kind="packer",
        path=path,
        fps=_optional_int(data.get("fps"), f"{path.name} fps"),
        hold=_optional_int(data.get("hold"), f"{path.name} hold"),
        duration_ms=_optional_float(data.get("duration_ms"), f"{path.name} duration_ms"),
        anchor=data.get("anchor"),
        background=data.get("background"),
        place=_optional_point(data.get("place"), f"{path.name} place"),
        place_space=_optional_space(data.get("place_space"), path.name),
        scale=_optional_int(data.get("scale"), f"{path.name} scale"),
    )
    for name, raw in animations.items():
        if not isinstance(raw, dict):
            raise SpritePackError(f"{path.name}: animation {name} must be an object")
        cycle = raw.get("cycle") or {}
        if cycle and not isinstance(cycle, dict):
            raise SpritePackError(f"{path.name}: {name}.cycle must be an object")
        mouth = raw.get("mouth") or {}
        if mouth and not isinstance(mouth, dict):
            raise SpritePackError(f"{path.name}: {name}.mouth must be an object")
        sidecar.animations[str(name)] = AnimSpec(
            files=_file_list(raw.get("files"), path, name),
            duration_ms=_optional_float(raw.get("duration_ms"), f"{name} duration_ms"),
            hold=_optional_int(raw.get("hold"), f"{name} hold"),
            fps=_optional_int(raw.get("fps"), f"{name} fps"),
            anchor=raw.get("anchor"),
            frames=_frame_overrides(raw.get("frames"), path, name),
            cycle_mode=cycle.get("mode"),
            skip_last=_optional_int(cycle.get("skip_last"), f"{name} skip_last"),
            background=raw.get("background"),
            place=_optional_point(raw.get("place"), f"{name} place"),
            place_space=_optional_space(raw.get("place_space"), name),
            scale=_optional_int(raw.get("scale"), f"{name} scale"),
            kit_place=_optional_point(raw.get("kit_place"), f"{name} kit_place"),
            kit_top_left=_optional_point(raw.get("kit_top_left"), f"{name} kit_top_left"),
            mouth_closed=mouth.get("closed"),
            mouth_open=mouth.get("open"),
        )
    return sidecar


def _load_studio_manifest(path: Path, data: dict) -> Sidecar:
    """Pixel Studio ``studio/samples/manifest.json``."""
    sidecar = Sidecar(kind="pixel-studio", path=path, manifest_groups={})
    folder = path.parent
    assert sidecar.manifest_groups is not None
    for key, raw in data.items():
        shot = str(raw.get("shot") or key)
        spec = AnimSpec(
            hold=_optional_int(raw.get("hold"), f"{shot} hold"),
            fps=_optional_int(raw.get("fps"), f"{shot} fps"),
            scale=_optional_int(raw.get("scale"), f"{shot} scale"),
            background=raw.get("background"),
            place=_optional_point(raw.get("offset"), f"{shot} offset"),
            place_space="top-left" if raw.get("offset") is not None else None,
            kit_top_left=_optional_point(raw.get("offset"), f"{shot} offset"),
        )
        naming = raw.get("naming") or "numbered"
        if naming not in ("sprite", "plate", "numbered"):
            naming = "numbered"
        mouth = raw.get("mouth")
        closed_i = open_i = None
        if isinstance(mouth, list) and len(mouth) == 2:
            closed_i, open_i = int(mouth[0]), int(mouth[1])
        group: list[Found] = []
        for index, filename in enumerate(raw["frames"]):
            if not isinstance(filename, str):
                raise SpritePackError(f"{path.name}: {shot} frame {index} is not a filename")
            file_path = folder / filename
            if not file_path.is_file():
                raise SpritePackError(f"{path.name}: missing {filename}")
            role = None
            if closed_i is not None and index == closed_i:
                role = "closed"
            elif open_i is not None and index == open_i:
                role = "open"
            group.append(Found(file_path, shot, index, role, "plate" if role else naming))
        patch = raw.get("patch")
        if isinstance(patch, dict) and patch.get("file"):
            file_path = folder / str(patch["file"])
            if not file_path.is_file():
                raise SpritePackError(f"{path.name}: missing {patch['file']}")
            group.append(Found(file_path, shot, 0, "patch", "plate"))
            origin = _optional_point([patch.get("x"), patch.get("y")], f"{shot} patch")
            spec.patch_origin = origin
        sidecar.animations[shot] = spec
        sidecar.manifest_groups[shot] = group
    return sidecar


def _flatten_manifest(groups: dict[str, list[Found]]) -> list[Found]:
    out: list[Found] = []
    for group in groups.values():
        out.extend(group)
    return out


def _apply_mouth_roles(items: list[Found], spec: AnimSpec) -> None:
    if not spec.mouth_closed and not spec.mouth_open:
        return
    by_file = {item.file: item for item in items}
    for filename, role in ((spec.mouth_closed, "closed"), (spec.mouth_open, "open")):
        if not filename:
            continue
        item = by_file.get(filename) or by_file.get(Path(filename).name)
        if item is None:
            raise SpritePackError(f"mouth {role} file {filename} is not in the animation")
        item.role = role
        item.index = 0 if role == "closed" else 1


def _background_names(sidecar: Sidecar) -> set[str]:
    names: set[str] = set()
    if sidecar.background:
        names.add(Path(sidecar.background).name)
    for spec in sidecar.animations.values():
        if spec.background:
            names.add(Path(spec.background).name)
    return names


def _frame_overrides(raw, path: Path, name: str) -> dict[str, FrameOverride]:
    if raw is None:
        return {}
    if isinstance(raw, list):
        # A list of filenames is file order, accepted as `files` instead.
        if all(isinstance(item, str) for item in raw):
            raise SpritePackError(
                f"{path.name}: {name}.frames is a file list. Use \"files\" for order "
                "and \"frames\" as an object of per-frame overrides."
            )
        overrides: dict[str, FrameOverride] = {}
        for item in raw:
            if not isinstance(item, dict) or "file" not in item:
                raise SpritePackError(
                    f"{path.name}: {name}.frames entries need a file name"
                )
            overrides[str(item["file"])] = _one_override(item, path, name)
        return overrides
    if isinstance(raw, dict):
        return {str(key): _one_override(value, path, name) for key, value in raw.items()}
    raise SpritePackError(f"{path.name}: {name}.frames must be an object")


def _one_override(raw, path: Path, name: str) -> FrameOverride:
    if not isinstance(raw, dict):
        raise SpritePackError(f"{path.name}: {name} frame override must be an object")
    return FrameOverride(
        duration_ms=_optional_float(raw.get("duration_ms"), f"{name} duration_ms"),
        hold=_optional_int(raw.get("hold"), f"{name} hold"),
        anchor=raw.get("anchor"),
    )


def _file_list(raw, path: Path, name: str) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise SpritePackError(f"{path.name}: {name}.files must be a list of filenames")
    return list(raw)


def _optional_int(value, where: str) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SpritePackError(f"{where} must be an integer") from exc
    return number


def _optional_float(value, where: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SpritePackError(f"{where} must be a number") from exc
    return number


def _optional_point(value, where: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y")]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise SpritePackError(f"{where} must be [x, y]")
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError) as exc:
        raise SpritePackError(f"{where} must be integer x, y") from exc


def _optional_space(value, where: str) -> str | None:
    if value is None:
        return None
    if value not in ("anchor", "top-left"):
        raise SpritePackError(f"{where} place_space must be anchor or top-left")
    return value
