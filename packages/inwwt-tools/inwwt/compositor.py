"""Split-screen and three-way layouts rendered as one ffmpeg filter graph.

YAML selects the layout, the divider, per-panel era looks, labels, and which
input the audio comes from. Looks that need the C64 palette (``dither``,
``c64``, ``full``) use ffmpeg's ``paletteuse`` against a palette PNG this
module writes. CRT, scanlines, and bloom are ffmpeg filters in the same graph.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from inwwt.palette import write_ffmpeg_palette
from inwwt.video import duration_of, has_audio, is_still, run_ffmpeg

LAYOUTS = ("split-vertical", "split-horizontal", "triptych", "one-plus-two")
LOOKS = ("none", "crt", "pixelate", "dither", "c64", "full")

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Panel:
    src: str
    label: str = ""
    look: str = "none"
    dither: str = "bayer"
    palette: str = "pepto"
    pixel_scale: int = 6
    c64_width: int = 320


@dataclass
class CompositeConfig:
    panels: list[Panel]
    width: int = 1920
    height: int = 1080
    fps: float = 24.0
    duration: float | None = None
    layout: str = "split-vertical"
    divider_px: int = 4
    divider_color: str = "000000"
    primary: str = "left"
    primary_ratio: float = 0.5
    show_labels: bool = True
    label_size: int = 36
    label_position: str = "bottom"
    label_font: str | None = None
    audio_from: str = "panel"  # panel, file, none
    audio_index: int = 0
    audio_path: str | None = None
    crf: int = 20
    preset: str = "medium"
    extra: dict = field(default_factory=dict)


def _norm_layout(name: str) -> str:
    key = name.strip().lower().replace("_", "-")
    aliases = {
        "vertical": "split-vertical",
        "horizontal": "split-horizontal",
        "split": "split-vertical",
        "1+2": "one-plus-two",
        "one+two": "one-plus-two",
    }
    key = aliases.get(key, key)
    if key not in LAYOUTS:
        raise ValueError(f"unknown layout {name!r}; choose from {', '.join(LAYOUTS)}")
    return key


def _split_sizes(total: int, count: int, gap: int) -> list[int]:
    usable = total - gap * (count - 1)
    if usable < count:
        raise ValueError("frame is too small for this many panels and the divider")
    base, rem = divmod(usable, count)
    return [base + (1 if i < rem else 0) for i in range(count)]


def layout_rects(cfg: CompositeConfig) -> list[Rect]:
    """Pixel rectangles for each panel. Gaps between them are the divider."""
    layout = _norm_layout(cfg.layout)
    n = len(cfg.panels)
    gap = cfg.divider_px
    w, h = cfg.width, cfg.height
    if layout == "split-vertical":
        if n != 2:
            raise ValueError("split-vertical needs exactly 2 panels")
        a, b = _split_sizes(w, 2, gap)
        return [Rect(0, 0, a, h), Rect(a + gap, 0, b, h)]
    if layout == "split-horizontal":
        if n != 2:
            raise ValueError("split-horizontal needs exactly 2 panels")
        a, b = _split_sizes(h, 2, gap)
        return [Rect(0, 0, w, a), Rect(0, a + gap, w, b)]
    if layout == "triptych":
        if n != 3:
            raise ValueError("triptych needs exactly 3 panels")
        sizes = _split_sizes(w, 3, gap)
        x = 0
        rects = []
        for size in sizes:
            rects.append(Rect(x, 0, size, h))
            x += size + gap
        return rects
    if n != 3:
        raise ValueError("one-plus-two needs exactly 3 panels (large, then the pair)")
    if not 0.2 <= cfg.primary_ratio <= 0.8:
        raise ValueError("primary_ratio must be between 0.2 and 0.8")
    side = cfg.primary.strip().lower()
    if side in {"left", "right"}:
        span = w - gap
        primary = int(round(span * cfg.primary_ratio))
        other = span - primary
        top, bot = _split_sizes(h, 2, gap)
        if side == "left":
            return [
                Rect(0, 0, primary, h),
                Rect(primary + gap, 0, other, top),
                Rect(primary + gap, top + gap, other, bot),
            ]
        return [
            Rect(other + gap, 0, primary, h),
            Rect(0, 0, other, top),
            Rect(0, top + gap, other, bot),
        ]
    if side in {"top", "bottom"}:
        span = h - gap
        primary = int(round(span * cfg.primary_ratio))
        other = span - primary
        left, right = _split_sizes(w, 2, gap)
        if side == "top":
            return [
                Rect(0, 0, w, primary),
                Rect(0, primary + gap, left, other),
                Rect(left + gap, primary + gap, right, other),
            ]
        return [
            Rect(0, other + gap, w, primary),
            Rect(0, 0, left, other),
            Rect(left + gap, 0, right, other),
        ]
    raise ValueError("primary must be left, right, top, or bottom")


def _hex_color(value: str) -> str:
    text = value.strip().lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError(f"color must be RRGGBB, got {value!r}")
    return text.lower()


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def _escape_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:")


def default_label_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("no DejaVu or Liberation font found for labels")


def _dither_name(name: str) -> str:
    key = name.strip().lower()
    if key == "bayer":
        return "bayer:bayer_scale=2"
    if key in {"floyd", "floyd-steinberg", "fs"}:
        return "floyd_steinberg"
    if key in {"none", "nearest"}:
        return "none"
    raise ValueError(f"unknown dither {name!r}")


def _needs_palette(look: str) -> bool:
    return look in {"dither", "c64", "full"}


def build_filter_complex(
    cfg: CompositeConfig,
    palette_inputs: dict[str, int],
    *,
    fontfile: str,
) -> str:
    """Return the filter_complex string. ``palette_inputs`` maps palette name to input index."""
    rects = layout_rects(cfg)
    chains: list[str] = []
    use_count: dict[str, int] = {}
    for panel in cfg.panels:
        if _needs_palette(panel.look):
            use_count[panel.palette] = use_count.get(panel.palette, 0) + 1
    for name, count in use_count.items():
        index = palette_inputs[name]
        if count == 1:
            continue
        labels = "".join(f"[pal_{name}_{i}]" for i in range(count))
        chains.append(f"[{index}:v]split={count}{labels}")
    consumed: dict[str, int] = {name: 0 for name in use_count}

    def palette_label(name: str) -> str:
        index = palette_inputs[name]
        count = use_count[name]
        if count == 1:
            return f"{index}:v"
        n = consumed[name]
        consumed[name] = n + 1
        return f"pal_{name}_{n}"

    for i, (panel, rect) in enumerate(zip(cfg.panels, rects)):
        chains.extend(_panel_filters(i, panel, rect, cfg.fps, palette_label if _needs_palette(panel.look) else None))

    color = _hex_color(cfg.divider_color)
    # The canvas is the divider. Panels are overlaid on top, leaving the gap.
    chains.append(f"color=c=0x{color}:s={cfg.width}x{cfg.height}:r={cfg.fps}:d={cfg.duration:.3f}[bg]")
    current = "bg"
    for i, rect in enumerate(rects):
        nxt = f"ov{i}"
        chains.append(f"[{current}][p{i}]overlay=x={rect.x}:y={rect.y}:format=auto[{nxt}]")
        current = nxt

    if cfg.show_labels:
        font = _escape_path(fontfile)
        size = cfg.label_size
        for i, (panel, rect) in enumerate(zip(cfg.panels, rects)):
            if not panel.label:
                continue
            text = _escape_drawtext(panel.label)
            if cfg.label_position == "top":
                y = rect.y + 20
            else:
                y = rect.y + rect.h - size - 28
            x = rect.x + 20
            nxt = f"lb{i}"
            chains.append(
                f"[{current}]drawtext=fontfile='{font}':text='{text}':x={x}:y={y}:"
                f"fontsize={size}:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10[{nxt}]"
            )
            current = nxt
    chains.append(f"[{current}]format=yuv420p[v]")
    return ";".join(chains)


def _panel_filters(index: int, panel: Panel, rect: Rect, fps: float, palette_for) -> list[str]:
    look = panel.look.strip().lower()
    if look not in LOOKS:
        raise ValueError(f"unknown look {panel.look!r}")
    src = f"{index}:v"
    w, h = rect.w, rect.h
    base = (
        f"[{src}]fps={fps},scale={w}:{h}:flags=lanczos,setsar=1"
    )
    if look == "none":
        return [f"{base}[p{index}]"]
    if look == "pixelate":
        tw = max(1, w // max(1, panel.pixel_scale))
        th = max(1, h // max(1, panel.pixel_scale))
        return [f"{base},scale={tw}:{th}:flags=neighbor,scale={w}:{h}:flags=neighbor[p{index}]"]
    if look == "crt":
        return _crt_chain(base, f"p{index}")
    if look == "dither":
        pal = palette_for(panel.palette)
        dither = _dither_name(panel.dither)
        return [
            f"{base},format=rgb24[d{index}]",
            f"[d{index}][{pal}]paletteuse=dither={dither}[p{index}]",
        ]
    if look in {"c64", "full"}:
        cw = max(2, min(panel.c64_width, w))
        ch = max(2, int(round(h * (cw / w))))
        pal = palette_for(panel.palette)
        dither = _dither_name(panel.dither)
        lines = []
        if look == "full":
            lines.extend(_crt_chain(base, f"c{index}"))
        if look == "c64":
            lines.append(f"{base},scale={cw}:{ch}:flags=neighbor,format=rgb24[s{index}]")
        else:
            lines.append(f"[c{index}]scale={cw}:{ch}:flags=neighbor,format=rgb24[s{index}]")
        lines.append(f"[s{index}][{pal}]paletteuse=dither={dither}[q{index}]")
        lines.append(f"[q{index}]scale={w}:{h}:flags=neighbor[p{index}]")
        return lines
    raise ValueError(look)


def _crt_chain(source_chain: str, out_label: str) -> list[str]:
    """CRT curvature, bloom, vignette, and scanlines.

    ``source_chain`` is either a full ``[in]filters`` prefix or we treat it
    as the start of the chain. It must not already end in a label.
    """
    # source_chain ends without an output label. split needs a labeled input,
    # so close the prefix first.
    return [
        f"{source_chain},split[b{out_label}][g{out_label}]",
        f"[g{out_label}]gblur=sigma=8[glow{out_label}]",
        (
            f"[b{out_label}][glow{out_label}]blend=all_mode=screen:all_opacity=0.35,"
            f"lenscorrection=cx=0.5:cy=0.5:k1=-0.18:k2=-0.04,"
            f"vignette=angle=PI/4,format=rgb24,"
            f"geq=r='r(X,Y)*(0.75+0.25*eq(mod(Y\\,2)\\,0))':"
            f"g='g(X,Y)*(0.75+0.25*eq(mod(Y\\,2)\\,0))':"
            f"b='b(X,Y)*(0.75+0.25*eq(mod(Y\\,2)\\,0))'[{out_label}]"
        ),
    ]


def load_config(path: str | Path) -> CompositeConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("composite config must be a YAML mapping")
    output = data.get("output") or {}
    divider = data.get("divider") or {}
    labels = data.get("labels") or {}
    audio = data.get("audio") or {}
    one = data.get("one_plus_two") or data.get("one-plus-two") or {}
    panels = []
    for raw in data.get("panels") or []:
        panels.append(
            Panel(
                src=str(raw["src"]),
                label=str(raw.get("label") or ""),
                look=str(raw.get("look") or "none"),
                dither=str(raw.get("dither") or "bayer"),
                palette=str(raw.get("palette") or "pepto"),
                pixel_scale=int(raw.get("pixel_scale") or 6),
                c64_width=int(raw.get("c64_width") or 320),
            )
        )
    if not panels:
        raise ValueError("config needs at least one panel")
    duration = output.get("duration", data.get("duration"))
    return CompositeConfig(
        panels=panels,
        width=int(output.get("width", 1920)),
        height=int(output.get("height", 1080)),
        fps=float(output.get("fps", 24)),
        duration=None if duration is None else float(duration),
        layout=str(data.get("layout") or "split-vertical"),
        divider_px=int(divider.get("px", divider.get("size", 4))),
        divider_color=str(divider.get("color", "000000")),
        primary=str(one.get("primary", data.get("primary", "left"))),
        primary_ratio=float(one.get("primary_ratio", data.get("primary_ratio", 0.5))),
        show_labels=bool(labels.get("show", True)),
        label_size=int(labels.get("size", 36)),
        label_position=str(labels.get("position", "bottom")),
        label_font=labels.get("font"),
        audio_from=str(audio.get("from", "panel")),
        audio_index=int(audio.get("index", 0)),
        audio_path=audio.get("path"),
        crf=int(output.get("crf", 20)),
        preset=str(output.get("preset", "medium")),
    )


def resolve_duration(cfg: CompositeConfig) -> float:
    if cfg.duration and cfg.duration > 0:
        return cfg.duration
    lengths = []
    for panel in cfg.panels:
        if is_still(panel.src):
            continue
        found = duration_of(panel.src)
        if found:
            lengths.append(found)
    if not lengths:
        raise ValueError("set output.duration when every panel is a still image")
    return min(lengths)


def render_composite(cfg: CompositeConfig, output: str) -> str:
    """Render and return the filter graph that was used."""
    cfg.duration = resolve_duration(cfg)
    # Validate geometry before launching ffmpeg.
    layout_rects(cfg)
    font = cfg.label_font or default_label_font()
    names = []
    for panel in cfg.panels:
        if _needs_palette(panel.look) and panel.palette not in names:
            names.append(panel.palette)
    with tempfile.TemporaryDirectory(prefix="inwwt-pal-") as tmp:
        palette_inputs: dict[str, int] = {}
        args: list[str] = ["-v", "error"]
        for panel in cfg.panels:
            if is_still(panel.src):
                args += ["-loop", "1", "-t", f"{cfg.duration:.3f}", "-i", panel.src]
            else:
                args += ["-stream_loop", "-1", "-t", f"{cfg.duration:.3f}", "-i", panel.src]
        for offset, name in enumerate(names):
            png = Path(tmp) / f"{name}.png"
            write_ffmpeg_palette(png, name)
            args += ["-i", str(png)]
            palette_inputs[name] = len(cfg.panels) + offset
        audio_input = None
        audio_from = cfg.audio_from.strip().lower()
        if audio_from == "file":
            if not cfg.audio_path:
                raise ValueError("audio.from is file, but audio.path is missing")
            args += ["-stream_loop", "-1", "-t", f"{cfg.duration:.3f}", "-i", cfg.audio_path]
            audio_input = len(cfg.panels) + len(names)
        elif audio_from == "panel":
            if not 0 <= cfg.audio_index < len(cfg.panels):
                raise ValueError("audio.index is outside the panel list")
            src = cfg.panels[cfg.audio_index].src
            if is_still(src) or not has_audio(src):
                raise ValueError(f"panel {cfg.audio_index} has no audio stream")
            audio_input = cfg.audio_index
        elif audio_from != "none":
            raise ValueError("audio.from must be panel, file, or none")

        graph = build_filter_complex(cfg, palette_inputs, fontfile=font)
        if audio_input is not None:
            graph += f";[{audio_input}:a]atrim=0:{cfg.duration:.3f},asetpts=PTS-STARTPTS[aout]"
        args += ["-filter_complex", graph, "-map", "[v]"]
        if audio_input is not None:
            args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
        else:
            args += ["-an"]
        args += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            str(cfg.crf),
            "-preset",
            cfg.preset,
            "-movflags",
            "+faststart",
            "-t",
            f"{cfg.duration:.3f}",
            output,
        ]
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(args)
        return graph
