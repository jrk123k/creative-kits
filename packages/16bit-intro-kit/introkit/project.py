"""Load an intro YAML file and check that the timeline can be filmed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import numpy as np
import yaml
from PIL import Image

from introkit.chiptune import note_pc, phrase_seconds
from introkit.errors import ConfigError
from introkit.font import check_logo, check_small, logo_width, small_width
from introkit.motion import Keyframe
from introkit.vocals import extract_words, load_alignment, merge_words

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "intro.schema.json"
W = 256
H = 224


def parse_time(value) -> float:
    """Seconds. Accepts a number or M:SS.s / H:MM:SS.s."""
    if isinstance(value, bool):
        raise ConfigError(f"not a time: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" not in text:
        return float(text)
    parts = text.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError as exc:
        raise ConfigError(f"bad time {value!r}") from exc
    raise ConfigError(f"bad time {value!r}")


def to_frame(seconds: float, fps: int) -> int:
    return int(round(float(seconds) * fps))


def format_time(frame: int, fps: int) -> str:
    ms = int(round(frame * 1000 / fps))
    minutes, rem = divmod(ms, 60000)
    return f"{minutes}:{rem / 1000:06.3f}"


@dataclass
class Patch:
    image: Path
    x: int
    y: int


@dataclass
class MouthPlate:
    id: str
    closed: Path
    open_path: Path | None
    patch: Patch | None


@dataclass
class Vocal:
    start: float
    end: float
    start_frame: int
    end_frame: int
    text: str
    mouth: bool


@dataclass
class Flash:
    x: int
    y: int
    w: int
    h: int
    color: tuple


@dataclass
class Pop:
    frames: int
    squash_h: int | None
    canvas_h: int | None
    paste_y: int
    y: int | None
    above: str | None
    flash: Flash | None
    image: Path | None


@dataclass
class Cycle:
    mode: str
    start_frame: int
    end_frame: int
    skip_last: int
    hold: int


@dataclass
class Sprite:
    id: str | None
    image: Path | None
    frames: list[Path]
    x: float
    y: float
    bob_px: float
    bob_hz: float
    parent: str | None
    ox: int
    oy: int
    keys: list[Keyframe]
    show: tuple[int, int] | None
    cycle: Cycle | None
    recolor: list[tuple[tuple, tuple]]
    pop: Pop | None


@dataclass
class ImageLayer:
    image: Path
    x: int
    y: int


@dataclass
class Layer:
    kind: str
    image: ImageLayer | None = None
    sprite: Sprite | None = None


@dataclass
class Scroll:
    tile: Path
    tile_w: int
    speed: float
    direction: str
    sprite: Sprite | None


@dataclass
class TextItem:
    text: str
    font: str
    x: int | None
    y: int
    align: str
    scale: int
    gap: int
    color: tuple
    outline: tuple | None
    sheen: int


@dataclass
class Prompt:
    text: str
    font: str
    x: int | None
    y: int
    align: str
    scale: int
    gap: int
    color: tuple
    outline: tuple | None
    on: float
    off: float


@dataclass
class Scene:
    id: str
    type: str
    start: float
    end: float
    start_frame: int
    end_frame: int
    cut: str
    mouth: str | None = None
    image: Path | None = None
    scroll: Scroll | None = None
    layers: list[Layer] = field(default_factory=list)
    background_image: Path | None = None
    background_color: tuple | None = None
    texts: list[TextItem] = field(default_factory=list)
    prompt: Prompt | None = None
    fade_in: int = 0


@dataclass
class Contact:
    frame: int
    label: str


@dataclass
class Chiptune:
    key: str
    mode: str
    bpm: float
    speed: float


@dataclass
class Project:
    name: str
    fps: int
    width: int
    height: int
    palette: str
    audio_file: Path
    song_seconds: float
    song_frames: int
    tail_seconds: float
    tail_source: str
    tail_file: Path | None
    chiptune: Chiptune | None
    hold_frames: int
    mouths: dict[str, MouthPlate]
    vocals: list[Vocal]
    scenes: list[Scene]
    contact: list[Contact]
    total_frames: int
    config_path: Path
    config_dir: Path

    @property
    def total_seconds(self) -> float:
        return self.total_frames / self.fps


def _rel(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path


def _exists(path: Path, where: str) -> Path:
    if not path.is_file():
        raise ConfigError(f"{where}: file not found: {path}")
    return path


def _color(value, where: str) -> tuple:
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        raise ConfigError(f"{where}: color must be [r, g, b] or [r, g, b, a]")
    nums = []
    for channel in value:
        n = int(channel)
        if n < 0 or n > 255:
            raise ConfigError(f"{where}: channel {n} is outside 0..255")
        nums.append(n)
    if len(nums) == 3:
        nums.append(255)
    return tuple(nums)


def _size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def _rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(arr)


def _unwrap_yaml11(doc: dict) -> None:
    """PyYAML 1.1 reads bare `off`/`on` as booleans. Accept that spelling."""
    if doc.get("palette") is False:
        doc["palette"] = "off"
    for scene in doc.get("scenes") or []:
        prompt = scene.get("prompt")
        if not isinstance(prompt, dict):
            continue
        if True in prompt and "on_seconds" not in prompt:
            prompt["on_seconds"] = prompt.pop(True)
        if False in prompt and "off_seconds" not in prompt:
            prompt["off_seconds"] = prompt.pop(False)
        if "on" in prompt and "on_seconds" not in prompt:
            prompt["on_seconds"] = prompt.pop("on")
        if "off" in prompt and "off_seconds" not in prompt:
            prompt["off_seconds"] = prompt.pop("off")


def validate_schema(doc: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    lines = []
    for err in errors[:12]:
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        lines.append(f"{loc}: {err.message}")
    extra = len(errors) - len(lines)
    if extra > 0:
        lines.append(f"... {extra} more")
    raise ConfigError("config does not match schema/intro.schema.json:\n" + "\n".join(lines))


def _probe_duration(path: Path) -> float:
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        )
    except FileNotFoundError as exc:
        raise ConfigError("ffprobe is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ConfigError(f"ffprobe failed on {path}") from exc
    try:
        return float(out.strip())
    except ValueError as exc:
        raise ConfigError(f"ffprobe returned no duration for {path}") from exc


def _parse_show(raw: dict, fps: int, where: str) -> tuple[int, int] | None:
    if "show" not in raw and "show_frames" not in raw:
        return None
    if "show" in raw and "show_frames" in raw:
        raise ConfigError(f"{where}: set show or show_frames, not both")
    if "show_frames" in raw:
        a, b = raw["show_frames"]
        start, end = int(a), int(b)
    else:
        pair = raw["show"]
        if not isinstance(pair, list) or len(pair) != 2:
            raise ConfigError(f"{where}: show must be [start, end]")
        start = to_frame(parse_time(pair[0]), fps)
        end = to_frame(parse_time(pair[1]), fps)
    if end <= start:
        raise ConfigError(f"{where}: show ends at or before it starts")
    return start, end


def _parse_keys(raw_keys, scene: Scene, fps: int, where: str) -> list[Keyframe]:
    keys = []
    for i, item in enumerate(raw_keys or []):
        has_t = "t" in item
        has_f = "frame" in item
        if has_t == has_f:
            raise ConfigError(f"{where} key {i}: set exactly one of t or frame")
        if has_f:
            frame = int(item["frame"])
        else:
            frame = scene.start_frame + to_frame(float(item["t"]), fps)
        keys.append(
            Keyframe(
                frame=frame,
                x=None if item.get("x") is None else float(item["x"]),
                y=None if item.get("y") is None else float(item["y"]),
                ease=str(item.get("ease") or "linear"),
            )
        )
    keys.sort(key=lambda k: k.frame)
    for a, b in zip(keys, keys[1:]):
        if a.frame == b.frame:
            raise ConfigError(f"{where}: two keys land on frame {a.frame}")
    return keys


def _parse_sprite(raw: dict, scene: Scene, fps: int, base: Path, where: str) -> Sprite:
    image = _exists(_rel(base, raw["image"]), where) if raw.get("image") else None
    frames = [_exists(_rel(base, p), where) for p in raw.get("frames") or []]
    if image is None and not frames:
        raise ConfigError(f"{where}: sprite needs image or frames")
    show = _parse_show(raw, fps, where)
    keys = _parse_keys(raw.get("keys"), scene, fps, where)
    parent = raw.get("parent")
    x = raw.get("x")
    y = raw.get("y")
    if parent is None:
        has_x = x is not None or any(k.x is not None for k in keys)
        has_y = y is not None or any(k.y is not None for k in keys)
        if not has_x or not has_y:
            raise ConfigError(f"{where}: sprite needs x and y, from the sprite or from every span of keys")
        if x is None and keys and any(k.x is None for k in keys):
            raise ConfigError(f"{where}: a key is missing x and the sprite has no x")
        if y is None and keys and any(k.y is None for k in keys):
            raise ConfigError(f"{where}: a key is missing y and the sprite has no y")
    recolor = []
    for pair in raw.get("recolor") or []:
        src = _color(pair["from"], where + " recolor from")
        dst = _color(pair["to"], where + " recolor to")
        recolor.append((src, dst))
    cycle = None
    if raw.get("cycle"):
        c = raw["cycle"]
        mode = c.get("mode") or "loop"
        if mode not in ("once", "loop"):
            raise ConfigError(f"{where}: cycle mode must be once or loop")
        span = _parse_show(c, fps, where + " cycle")
        if span is None:
            if show is None and mode == "once":
                raise ConfigError(f"{where}: a once cycle needs show or show_frames")
            span = show if show is not None else (scene.start_frame, scene.end_frame)
        skip = int(c.get("skip_last") or 0)
        hold = int(c.get("hold") or 4)
        if mode == "once" and (span[1] - span[0] - skip) <= 0:
            raise ConfigError(f"{where}: cycle skip_last leaves no frames")
        cycle = Cycle(mode, span[0], span[1], skip, hold)
    elif len(frames) > 1:
        cycle = Cycle("loop", scene.start_frame, scene.end_frame, 0, 4)
    pop = None
    if raw.get("pop"):
        p = raw["pop"]
        if show is None:
            raise ConfigError(f"{where}: pop needs the sprite's show window")
        flash = None
        if p.get("flash"):
            fl = p["flash"]
            flash = Flash(
                int(fl["x"]),
                int(fl["y"]),
                int(fl["w"]),
                int(fl["h"]),
                _color(fl["color"], where + " flash"),
            )
        pop = Pop(
            frames=int(p.get("frames") or 1),
            squash_h=None if p.get("squash_h") is None else int(p["squash_h"]),
            canvas_h=None if p.get("canvas_h") is None else int(p["canvas_h"]),
            paste_y=int(p.get("paste_y") or 0),
            y=None if p.get("y") is None else int(p["y"]),
            above=p.get("above"),
            flash=flash,
            image=_exists(_rel(base, p["image"]), where) if p.get("image") else None,
        )
        if pop.image is None and (pop.squash_h is None or pop.canvas_h is None):
            raise ConfigError(f"{where}: pop needs image, or squash_h and canvas_h")
        if pop.frames <= 0:
            raise ConfigError(f"{where}: pop.frames must be positive")
        if pop.squash_h is not None and pop.canvas_h is not None:
            if pop.paste_y + pop.squash_h > pop.canvas_h:
                raise ConfigError(f"{where}: pop squash does not fit in the canvas")
    return Sprite(
        id=raw.get("id"),
        image=image,
        frames=frames,
        x=0.0 if x is None else float(x),
        y=0.0 if y is None else float(y),
        bob_px=float(raw.get("bob_px") or 0),
        bob_hz=float(raw.get("bob_hz") or 0),
        parent=parent,
        ox=int(raw.get("ox") or 0),
        oy=int(raw.get("oy") or 0),
        keys=keys,
        show=show,
        cycle=cycle,
        recolor=recolor,
        pop=pop,
    )


def _check_plate(plate: MouthPlate, width: int, height: int) -> None:
    cw, ch = _size(plate.closed)
    if (cw, ch) != (width, height):
        raise ConfigError(f"mouth {plate.id}: closed plate is {cw}x{ch}, frame is {width}x{height}")
    closed = _rgb(plate.closed)
    if plate.open_path is not None:
        ow, oh = _size(plate.open_path)
        if (ow, oh) != (width, height):
            raise ConfigError(f"mouth {plate.id}: open still is {ow}x{oh}, frame is {width}x{height}")
    if plate.patch is not None:
        pw, ph = _size(plate.patch.image)
        x, y = plate.patch.x, plate.patch.y
        if x < 0 or y < 0 or x + pw > width or y + ph > height:
            raise ConfigError(f"mouth {plate.id}: patch {pw}x{ph} at {x},{y} does not fit")
        if plate.open_path is not None:
            pasted = closed.copy()
            patch = _rgb(plate.patch.image)
            pasted[y : y + ph, x : x + pw] = patch
            opened = _rgb(plate.open_path)
            if not np.array_equal(pasted, opened):
                raise ConfigError(
                    f"mouth {plate.id}: pasting the patch onto the closed plate does not "
                    "match the open still. Export the patch from that still, or drop one of them."
                )


def _check_text(item: TextItem, where: str, width: int) -> None:
    if item.font == "logo":
        item.text = check_logo(item.text)
        tw = logo_width(item.text, item.scale, item.gap)
    elif item.font == "small":
        item.text = check_small(item.text)
        tw = small_width(item.text, item.scale, item.gap)
    else:
        raise ConfigError(f"{where}: font must be logo or small")
    if item.align == "left" and item.x is None:
        raise ConfigError(f"{where}: left-aligned text needs x")
    if item.align == "center":
        if tw > width:
            raise ConfigError(f"{where}: {item.text!r} is {tw}px wide and the frame is {width}")
    elif item.x is not None and item.x + tw > width + item.scale:
        # A 1px outline may hang off; the draw clips. Warn only past a full glyph.
        pass


def load_project(path: str | Path, *, probe: bool = True) -> Project:
    path = Path(path)
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"could not parse {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError("config must be a YAML mapping")
    _unwrap_yaml11(doc)
    validate_schema(doc)

    base = path.parent
    fps = int(doc["fps"])
    width = int(doc["width"])
    height = int(doc["height"])
    if (width, height) != (W, H):
        raise ConfigError(f"frame must be {W}x{H}, got {width}x{height}")
    palette = doc.get("palette") or "off"
    if palette not in ("off", "tg16"):
        raise ConfigError("palette must be off or tg16")

    audio = doc["audio"]
    audio_file = _exists(_rel(base, audio["file"]), "audio.file")
    tail = audio.get("tail") or {"duration": 0, "source": "none"}
    tail_seconds = float(tail.get("duration") or 0)
    tail_source = tail.get("source") or "none"
    if tail_source == "none" and tail_seconds != 0:
        raise ConfigError("audio.tail source none only allows duration 0; use silence for a silent tail")
    if tail_seconds < 0:
        raise ConfigError("audio.tail duration must be >= 0")
    tail_file = None
    chiptune = None
    if tail_source == "file":
        if not tail.get("file"):
            raise ConfigError("audio.tail source file needs tail.file")
        tail_file = _exists(_rel(base, tail["file"]), "audio.tail.file")
    if tail_source == "chiptune":
        spec = tail.get("chiptune") or {}
        key = str(spec.get("key") or "C")
        mode = str(spec.get("mode") or "minor")
        bpm = float(spec.get("bpm") or 120)
        speed = float(spec.get("speed") or 1)
        try:
            note_pc(key)
            phrase_seconds(bpm, speed)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        if mode not in ("minor", "major"):
            raise ConfigError("chiptune mode must be minor or major")
        chiptune = Chiptune(key, mode, bpm, speed)

    if probe:
        probed = _probe_duration(audio_file)
    else:
        probed = float(audio.get("duration") or 0)
    if audio.get("duration") is not None:
        song_seconds = float(audio["duration"])
        if probe and abs(probed - song_seconds) > 0.15:
            raise ConfigError(
                f"audio.duration is {song_seconds:.3f}s but {audio_file.name} probes as {probed:.3f}s"
            )
    else:
        if not probe:
            raise ConfigError("audio.duration is required when duration probing is off")
        song_frames_probe = to_frame(probed, fps)
        song_seconds = song_frames_probe / fps
    song_frames = to_frame(song_seconds, fps)
    total_frames = to_frame(song_seconds + tail_seconds, fps)

    hold_frames = 4
    vocals_doc = doc.get("vocals") or {}
    if vocals_doc:
        hold_frames = int(vocals_doc.get("hold_frames") or 4)
    if hold_frames < 1:
        raise ConfigError("vocals.hold_frames must be >= 1")

    mouths: dict[str, MouthPlate] = {}
    for mid, raw in (doc.get("mouths") or {}).items():
        patch = None
        if raw.get("patch"):
            patch = Patch(
                _exists(_rel(base, raw["patch"]["image"]), f"mouths.{mid}.patch"),
                int(raw["patch"]["x"]),
                int(raw["patch"]["y"]),
            )
        plate = MouthPlate(
            id=str(mid),
            closed=_exists(_rel(base, raw["closed"]), f"mouths.{mid}.closed"),
            open_path=_exists(_rel(base, raw["open"]), f"mouths.{mid}.open") if raw.get("open") else None,
            patch=patch,
        )
        if plate.open_path is None and plate.patch is None:
            raise ConfigError(f"mouth {mid} needs an open still or a patch")
        _check_plate(plate, width, height)
        mouths[plate.id] = plate

    vocals = _parse_vocals(vocals_doc, fps, total_frames, base)

    scenes = []
    for raw in doc["scenes"]:
        scenes.append(_parse_scene(raw, fps, base, width, height, mouths))
    _check_timeline(scenes, total_frames, fps)
    _check_vocals_land(vocals, scenes, mouths, fps)

    for scene in scenes:
        for text in scene.texts:
            _check_text(text, f"scene {scene.id}", width)
        if scene.prompt:
            probe = TextItem(
                scene.prompt.text,
                scene.prompt.font,
                scene.prompt.x,
                scene.prompt.y,
                scene.prompt.align,
                scene.prompt.scale,
                scene.prompt.gap,
                scene.prompt.color,
                scene.prompt.outline,
                0,
            )
            _check_text(probe, f"scene {scene.id} prompt", width)
            scene.prompt.text = probe.text

    contact = []
    for item in doc.get("contact") or []:
        if item.get("frame") is not None:
            frame = int(item["frame"])
        else:
            frame = to_frame(parse_time(item["time"]), fps)
        if not 0 <= frame < total_frames:
            raise ConfigError(f"contact frame {frame} is outside the film")
        contact.append(Contact(frame, str(item.get("label") or "")))

    return Project(
        name=str(doc["name"]),
        fps=fps,
        width=width,
        height=height,
        palette=palette,
        audio_file=audio_file,
        song_seconds=song_seconds,
        song_frames=song_frames,
        tail_seconds=tail_seconds,
        tail_source=tail_source,
        tail_file=tail_file,
        chiptune=chiptune,
        hold_frames=hold_frames,
        mouths=mouths,
        vocals=vocals,
        scenes=scenes,
        contact=contact,
        total_frames=total_frames,
        config_path=path,
        config_dir=base,
    )


def _parse_vocals(doc: dict, fps: int, total_frames: int, base: Path) -> list[Vocal]:
    if not doc:
        return []
    has_lines = bool(doc.get("lines"))
    has_align = bool(doc.get("alignment"))
    if has_lines and has_align:
        raise ConfigError("vocals: set lines or alignment, not both")
    if not has_lines and not has_align:
        return []
    if has_align:
        gap = float(doc.get("gap") if doc.get("gap") is not None else 0.35)
        data = load_alignment(_exists(_rel(base, doc["alignment"]), "vocals.alignment"))
        rows = merge_words(extract_words(data), gap, doc.get("speaker"))
        mouth_default = True if doc.get("mouth") is None else bool(doc["mouth"])
        for row in rows:
            row["mouth"] = mouth_default
    else:
        rows = []
        for raw in doc["lines"]:
            rows.append(
                {
                    "start": parse_time(raw["start"]),
                    "end": parse_time(raw["end"]),
                    "text": str(raw.get("text") or ""),
                    "mouth": True if raw.get("mouth") is None else bool(raw["mouth"]),
                }
            )
    vocals = []
    for row in rows:
        start = float(row["start"])
        end = float(row["end"])
        a = to_frame(start, fps)
        b = to_frame(end, fps)
        if b <= a:
            raise ConfigError(f"vocal {row.get('text')!r} is shorter than one frame ({start} -> {end})")
        if a < 0 or b > total_frames:
            raise ConfigError(f"vocal {row.get('text')!r} falls outside the film")
        vocals.append(Vocal(start, end, a, b, str(row.get("text") or ""), bool(row["mouth"])))
    vocals.sort(key=lambda v: v.start_frame)
    for a, b in zip(vocals, vocals[1:]):
        if a.mouth and b.mouth and a.end_frame > b.start_frame:
            raise ConfigError(f"mouth vocals overlap: {a.text!r} and {b.text!r}")
    return vocals


def _parse_scene(raw: dict, fps: int, base: Path, width: int, height: int, mouths: dict) -> Scene:
    sid = str(raw["id"])
    kind = raw["type"]
    start = parse_time(raw["start"])
    end = parse_time(raw["end"])
    scene = Scene(
        id=sid,
        type=kind,
        start=start,
        end=end,
        start_frame=to_frame(start, fps),
        end_frame=to_frame(end, fps),
        cut=raw.get("cut") or "hard",
        mouth=raw.get("mouth"),
        fade_in=int(raw.get("fade_in") or 0),
    )
    if scene.end_frame <= scene.start_frame:
        raise ConfigError(f"scene {sid} is shorter than one frame")
    if scene.cut != "hard":
        raise ConfigError(f"scene {sid}: only hard cuts are supported")
    if scene.mouth is not None and scene.mouth not in mouths:
        raise ConfigError(f"scene {sid}: unknown mouth {scene.mouth!r}")
    where = f"scene {sid}"
    if kind == "still":
        if scene.mouth is None and not raw.get("image"):
            raise ConfigError(f"{where}: a still needs image or mouth")
        if raw.get("image"):
            scene.image = _exists(_rel(base, raw["image"]), where)
            iw, ih = _size(scene.image)
            if (iw, ih) != (width, height):
                raise ConfigError(f"{where}: still is {iw}x{ih}, frame is {width}x{height}")
    elif kind == "scroll":
        tile = _exists(_rel(base, raw["tile"]), where)
        tw, th = _size(tile)
        tile_w = int(raw["tile_w"]) if raw.get("tile_w") is not None else tw
        if th != height or tw != tile_w:
            raise ConfigError(
                f"{where}: scroll tile is {tw}x{th}; it must be {tile_w} wide and {height} tall"
            )
        direction = raw.get("direction") or "left"
        if direction not in ("left", "right"):
            raise ConfigError(f"{where}: direction must be left or right")
        sprite = None
        if raw.get("sprite"):
            sprite = _parse_sprite(raw["sprite"], scene, fps, base, where + " sprite")
        scene.scroll = Scroll(tile, tile_w, float(raw["scroll_px_per_s"]), direction, sprite)
        if scene.mouth is not None:
            raise ConfigError(f"{where}: mouth plates belong on still scenes")
    elif kind == "stack":
        ids = []
        for i, layer in enumerate(raw["layers"]):
            lwhere = f"{where} layer {i}"
            ltype = layer["type"]
            if ltype == "image":
                image = _exists(_rel(base, layer["image"]), lwhere)
                scene.layers.append(
                    Layer("image", ImageLayer(image, int(layer.get("x") or 0), int(layer.get("y") or 0)))
                )
            elif ltype == "sprite":
                sprite = _parse_sprite(layer, scene, fps, base, lwhere)
                if sprite.id:
                    if sprite.id in ids:
                        raise ConfigError(f"{where}: duplicate sprite id {sprite.id}")
                    ids.append(sprite.id)
                scene.layers.append(Layer("sprite", sprite=sprite))
            else:
                raise ConfigError(f"{lwhere}: unknown layer type {ltype}")
        known = set(ids)
        for layer in scene.layers:
            sp = layer.sprite
            if sp is None:
                continue
            if sp.parent and sp.parent not in known:
                raise ConfigError(f"{where}: sprite {sp.id} parents unknown id {sp.parent}")
            if sp.pop and sp.pop.above and sp.pop.above not in known:
                raise ConfigError(f"{where}: pop above unknown id {sp.pop.above}")
        if scene.mouth is not None:
            raise ConfigError(f"{where}: mouth plates belong on still scenes")
    elif kind == "title":
        bg = raw["background"]
        if bg.get("image") and bg.get("color"):
            raise ConfigError(f"{where}: background is an image or a color")
        if bg.get("image"):
            scene.background_image = _exists(_rel(base, bg["image"]), where)
            iw, ih = _size(scene.background_image)
            if (iw, ih) != (width, height):
                raise ConfigError(f"{where}: title background is {iw}x{ih}")
        elif bg.get("color"):
            scene.background_color = _color(bg["color"], where + " background")
        else:
            raise ConfigError(f"{where}: background needs image or color")
        for i, text in enumerate(raw.get("text") or []):
            scene.texts.append(_parse_text(text, f"{where} text {i}"))
        if raw.get("prompt"):
            p = raw["prompt"]
            outline = _color(p["outline"], where + " prompt outline") if p.get("outline") else None
            scene.prompt = Prompt(
                text=str(p["text"]),
                font=p.get("font") or "small",
                x=None if p.get("x") is None else int(p["x"]),
                y=int(p["y"]),
                align=p.get("align") or "center",
                scale=int(p.get("scale") or 2),
                gap=int(p.get("gap") if p.get("gap") is not None else 1),
                color=_color(p.get("color") or [255, 255, 255], where + " prompt"),
                outline=outline,
                on=float(p.get("on_seconds") or 0.5),
                off=float(p.get("off_seconds") or 0.5),
            )
            if scene.prompt.on <= 0 or scene.prompt.off <= 0:
                raise ConfigError(f"{where}: prompt on and off must be > 0")
        if scene.mouth is not None:
            raise ConfigError(f"{where}: mouth plates belong on still scenes")
    else:
        raise ConfigError(f"{where}: unknown type {kind}")
    return scene


def _parse_text(raw: dict, where: str) -> TextItem:
    font = raw.get("font") or "small"
    align = raw.get("align") or "left"
    color = raw.get("color") or [255, 255, 255]
    outline = _color(raw["outline"], where + " outline") if raw.get("outline") else None
    return TextItem(
        text=str(raw["text"]),
        font=font,
        x=None if raw.get("x") is None else int(raw["x"]),
        y=int(raw["y"]),
        align=align,
        scale=int(raw.get("scale") or (3 if font == "logo" else 2)),
        gap=int(raw.get("gap") if raw.get("gap") is not None else (4 if font == "logo" else 1)),
        color=_color(color, where),
        outline=outline,
        sheen=int(raw.get("sheen") or 0),
    )


def _check_timeline(scenes: list[Scene], total_frames: int, fps: int) -> None:
    if not scenes:
        raise ConfigError("scenes is empty")
    if scenes[0].start_frame != 0:
        raise ConfigError(f"first scene starts at frame {scenes[0].start_frame}, not 0")
    for a, b in zip(scenes, scenes[1:]):
        if a.end_frame != b.start_frame:
            raise ConfigError(
                f"scene {a.id} ends at {format_time(a.end_frame, fps)} and "
                f"{b.id} starts at {format_time(b.start_frame, fps)}; hard cuts have to meet"
            )
    if scenes[-1].end_frame != total_frames:
        raise ConfigError(
            f"scenes end at frame {scenes[-1].end_frame} ({format_time(scenes[-1].end_frame, fps)}) "
            f"but the song plus tail is {total_frames} frames ({format_time(total_frames, fps)})"
        )


def _check_vocals_land(vocals: list[Vocal], scenes: list[Scene], mouths: dict, fps: int) -> None:
    for vocal in vocals:
        if not vocal.mouth:
            continue
        for scene in scenes:
            if scene.end_frame <= vocal.start_frame or scene.start_frame >= vocal.end_frame:
                continue
            if scene.type != "still" or not scene.mouth:
                raise ConfigError(
                    f"vocal {vocal.text!r} ({format_time(vocal.start_frame, fps)}-"
                    f"{format_time(vocal.end_frame, fps)}) lands on scene {scene.id}, which has no mouth plate"
                )
            if scene.mouth not in mouths:
                raise ConfigError(f"scene {scene.id} mouth {scene.mouth} is not defined")


def scene_at(project: Project, frame: int) -> Scene:
    for scene in project.scenes:
        if scene.start_frame <= frame < scene.end_frame:
            return scene
    raise ConfigError(f"no scene for frame {frame}")


def mouth_at(project: Project, frame: int) -> str:
    """open, closed, or off.

    Open only inside a mouth vocal, on the hold-frame phase, and never on the
    last frame of that vocal. A scene with a plate is closed otherwise. A scene
    without one is off.
    """
    scene = scene_at(project, frame)
    active = None
    for vocal in project.vocals:
        if vocal.mouth and vocal.start_frame <= frame < vocal.end_frame:
            active = vocal
            break
    if active is None:
        return "off" if not scene.mouth else "closed"
    if not scene.mouth:
        raise ConfigError(f"frame {frame} is inside a mouth vocal but scene {scene.id} has no plate")
    if frame == active.end_frame - 1:
        return "closed"
    local = frame - active.start_frame
    if (local // project.hold_frames) % 2 == 0:
        return "open"
    return "closed"
