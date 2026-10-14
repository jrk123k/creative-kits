"""Command line for the intro kit."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from introkit import __version__
from introkit.encode import render_movie
from introkit.errors import ConfigError
from introkit.film import Film
from introkit.project import format_time, load_project, mouth_at


def _project(path: str):
    try:
        return load_project(path)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc


def _cmd_validate(args) -> None:
    project = _project(args.config)
    mouths = sum(1 for v in project.vocals if v.mouth)
    print(
        f"{project.name}: {project.total_frames} frames "
        f"({format_time(project.total_frames, project.fps)}) "
        f"{len(project.scenes)} scenes, {mouths} mouth lines"
    )


def _cmd_timeline(args) -> None:
    project = _project(args.config)
    print(f"{project.name}  {project.width}x{project.height}  {project.fps} fps  palette={project.palette}")
    print(f"song {project.song_seconds:.3f}s + tail {project.tail_seconds:.3f}s ({project.tail_source})")
    print(f"total {project.total_frames} frames, {format_time(project.total_frames, project.fps)}")
    for scene in project.scenes:
        print(
            f"  {format_time(scene.start_frame, project.fps):>10}  "
            f"{format_time(scene.end_frame, project.fps):>10}  "
            f"{scene.cut:<4}  {scene.type:<6}  {scene.id}"
            + (f"  mouth={scene.mouth}" if scene.mouth else "")
        )
    if project.vocals:
        print("vocals")
        for vocal in project.vocals:
            flag = "mouth" if vocal.mouth else "quiet"
            print(
                f"  {format_time(vocal.start_frame, project.fps):>10}  "
                f"{format_time(vocal.end_frame, project.fps):>10}  {flag:<5}  {vocal.text}"
            )


def _cmd_frame(args) -> None:
    project = _project(args.config)
    film = Film(project)
    if args.frame is not None:
        frame = int(args.frame)
    else:
        frame = int(round(float(args.time) * project.fps))
    rgb = film.render(frame)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, "RGB").save(dest)
    print(f"wrote {dest} frame={frame} scene={film.scene_at(frame).id} mouth={film.mouth_at(frame)}")


def _contact_frames(project, film: Film):
    if project.contact:
        return [(c.frame, c.label) for c in project.contact]
    frames = []
    step = max(1, project.total_frames // 8)
    for frame in range(0, project.total_frames, step):
        frames.append((frame, f"{format_time(frame, project.fps)} {film.scene_at(frame).id}"))
    return frames[:12]


def _cmd_preview(args) -> None:
    project = _project(args.config)
    film = Film(project)
    cells = _contact_frames(project, film)
    scale = 2
    label_h = 16
    cell_w = project.width * scale
    cell_h = project.height * scale + label_h
    cols = 6 if len(cells) > 6 else max(1, len(cells))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (12, 12, 16))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (frame, label) in enumerate(cells):
        rgb = film.render(frame)
        im = Image.fromarray(rgb, "RGB").resize(
            (project.width * scale, project.height * scale), Image.Resampling.NEAREST
        )
        c, r = i % cols, i // cols
        x, y = c * cell_w, r * cell_h
        sheet.paste(im, (x, y))
        draw.text((x + 4, y + project.height * scale + 2), label, fill=(230, 230, 220), font=font)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    print(f"wrote {dest}")


def _cmd_mouth_log(args) -> None:
    project = _project(args.config)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="") as fh:
        writer = csv.writer(fh)
        from introkit.project import scene_at

        writer.writerow(["frame", "time", "scene", "mouth"])
        for frame in range(project.total_frames):
            scene = scene_at(project, frame)
            writer.writerow([frame, format_time(frame, project.fps), scene.id, mouth_at(project, frame)])
    print(f"wrote {dest} ({project.total_frames} frames)")


def _cmd_render(args) -> None:
    project = _project(args.config)
    dest = Path(args.out)
    try:
        render_movie(project, dest, preset=args.preset, limit=args.limit)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"wrote {dest}")
    if args.contact:
        args.out = args.contact
        _cmd_preview(args)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="introkit", description="Render a 16-bit intro from a YAML config.")
    parser.add_argument("--version", action="version", version=f"introkit {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check the config, assets, and timeline")
    v.add_argument("config")
    v.set_defaults(func=_cmd_validate)

    t = sub.add_parser("timeline", help="print scenes and vocal windows")
    t.add_argument("config")
    t.set_defaults(func=_cmd_timeline)

    f = sub.add_parser("frame", help="write one native frame")
    f.add_argument("config")
    f.add_argument("--time", type=float, default=None)
    f.add_argument("--frame", type=int, default=None)
    f.add_argument("-o", "--out", required=True)
    f.set_defaults(func=_cmd_frame)

    p = sub.add_parser("preview", help="write a contact sheet of native frames")
    p.add_argument("config")
    p.add_argument("-o", "--out", required=True)
    p.set_defaults(func=_cmd_preview)

    m = sub.add_parser("mouth-log", help="write a per-frame mouth csv")
    m.add_argument("config")
    m.add_argument("-o", "--out", required=True)
    m.set_defaults(func=_cmd_mouth_log)

    r = sub.add_parser("render", help="encode a 1920x1080 MP4")
    r.add_argument("config")
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--preset", default="medium")
    r.add_argument("--limit", type=int, default=None, help="encode only the first N frames")
    r.add_argument("--contact", default=None, help="also write a contact sheet")
    r.set_defaults(func=_cmd_render)

    args = parser.parse_args(argv)
    if args.cmd == "frame" and args.time is None and args.frame is None:
        parser.error("frame needs --time or --frame")
    args.func(args)


if __name__ == "__main__":
    main()
