"""Song audio is packet-copied. The tail (silence, chiptune, or a file) is appended."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from introkit.chiptune import METHOD, REASON, SR, fit, synthesize
from introkit.errors import ConfigError
from introkit.film import Film
from introkit.project import Project, format_time

# Scale 256x224 with nearest neighbor to 1440x1080, then pillarbox to 1920x1080.
VIDEO_FILTER = "scale=1440:1080:flags=neighbor,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"


def probe_stream(path: Path) -> dict:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,channels",
                "-of",
                "default=noprint_wrappers=1",
                str(path),
            ],
            text=True,
        )
    except FileNotFoundError as exc:
        raise ConfigError("ffprobe is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ConfigError(f"ffprobe failed on {path}") from exc
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def _decode_f32(path: Path) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "2",
            "-ar",
            str(SR),
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size % 2:
        audio = audio[:-1]
    return audio.reshape(-1, 2)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros((max(0, int(round(seconds * SR))), 2), dtype=np.float32)


def tail_pcm(project: Project) -> np.ndarray:
    """Tail audio plus a 0.30s pad so MP3 priming cannot eat the ending."""
    dur = project.tail_seconds
    if project.tail_source in ("silence", "none"):
        body = _silence(dur)
    elif project.tail_source == "chiptune":
        spec = project.chiptune
        assert spec is not None
        body = fit(synthesize(spec.key, spec.mode, spec.bpm, spec.speed), dur)
    elif project.tail_source == "file":
        assert project.tail_file is not None
        body = fit(_decode_f32(project.tail_file), dur)
    else:
        raise ConfigError(f"unknown tail source {project.tail_source}")
    return np.concatenate([body, _silence(0.30)], axis=0)


def _write_mp3(pcm: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "f32le",
            "-ar",
            str(SR),
            "-ac",
            "2",
            "-i",
            "pipe:0",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            str(path),
        ],
        input=np.ascontiguousarray(pcm).tobytes(),
        check=True,
    )


def _quote(path: Path) -> str:
    return str(path.resolve()).replace("'", r"'\''")


def build_audio(project: Project, dest: Path) -> Path:
    """Return an audio file whose song packets are the original file's packets.

    When there is no tail, `dest` is not written and the song path is returned.
    Otherwise the song and the tail are concatenated with `-c copy`.
    """
    song_info = probe_stream(project.audio_file)
    if song_info.get("codec_name") not in ("mp3", "pcm_s16le", "pcm_s16be"):
        # wav shows up as pcm_*. mp3 is the path the reference song and the demo use.
        if song_info.get("codec_name") != "mp3":
            raise ConfigError(
                f"song codec is {song_info.get('codec_name')!r}; use mp3 or wav so the song can be stream-copied"
            )
    if project.tail_seconds <= 0 or project.tail_source == "none":
        return project.audio_file
    if song_info.get("codec_name") != "mp3":
        raise ConfigError("a tail is appended with stream copy; the song file needs to be mp3")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tail = dest.with_name(dest.stem + "_tail.mp3")
    _write_mp3(tail_pcm(project), tail)
    if project.tail_source == "chiptune" and project.chiptune is not None:
        note = dest.with_name(dest.stem + "_chiptune.txt")
        spec = project.chiptune
        note.write_text(
            f"{METHOD}\nkey={spec.key} mode={spec.mode} bpm={spec.bpm} speed={spec.speed}\n{REASON}\n"
        )
        print(f"title music: {METHOD} {spec.key} {spec.mode} {spec.bpm}bpm x{spec.speed}", flush=True)
    listing = dest.with_name(dest.stem + "_concat.txt")
    joined = dest.with_name(dest.stem + "_joined.mp3")
    listing.write_text(f"file '{_quote(project.audio_file)}'\nfile '{_quote(tail)}'\n")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            str(joined),
        ],
        check=True,
    )
    # Keep a margin past the picture so an MP3 frame boundary cannot pull
    # -shortest under the last video frame. The song packets stay intact.
    trim = project.total_seconds + 0.20
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(joined),
            "-c",
            "copy",
            "-t",
            f"{trim:.3f}",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            str(dest),
        ],
        check=True,
    )
    return dest


def encode_video(project: Project, film: Film, audio: Path, dest: Path, preset: str = "medium", limit: int | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = project.total_frames if limit is None else min(limit, project.total_frames)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{project.width}x{project.height}",
        "-r",
        str(project.fps),
        "-i",
        "pipe:0",
        "-i",
        str(audio),
        "-vf",
        VIDEO_FILTER,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(frames):
            rgb = film.render(i)
            proc.stdin.write(rgb.tobytes())
            if i % 150 == 0:
                scene = film.scene_at(i)
                print(
                    f"frame {i}/{frames} {format_time(i, project.fps)} {scene.id} mouth={film.mouth_at(i)}",
                    flush=True,
                )
    except BrokenPipeError:
        proc.wait()
        raise RuntimeError(f"ffmpeg exited {proc.returncode}") from None
    finally:
        proc.stdin.close()
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg exited {code}")


def render_movie(project: Project, dest: Path, preset: str = "medium", limit: int | None = None) -> None:
    film = Film(project)
    audio = build_audio(project, dest.with_name(dest.stem + "_audio.mp3"))
    encode_video(project, film, audio, dest, preset=preset, limit=limit)
