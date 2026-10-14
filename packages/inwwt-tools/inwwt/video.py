"""ffmpeg helpers: probe, raw-frame streaming, and encode."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import numpy as np

STILL_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class FFmpegError(RuntimeError):
    pass


def _drain(pipe, bucket: list[bytes]) -> None:
    if pipe is None:
        return
    bucket.append(pipe.read())


def run_ffmpeg(args: list[str], *, stdin: bytes | None = None) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace")[-4000:]
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}):\n{tail}")


def probe(path: str | Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace")[-2000:]
        raise FFmpegError(f"ffprobe failed for {path}:\n{tail}")
    return json.loads(proc.stdout.decode("utf-8"))


def has_audio(path: str | Path) -> bool:
    info = probe(path)
    return any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))


def duration_of(path: str | Path) -> float | None:
    if is_still(path):
        return None
    info = probe(path)
    raw = info.get("format", {}).get("duration")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def is_still(path: str | Path) -> bool:
    return Path(path).suffix.lower() in STILL_SUFFIXES


def video_size(path: str | Path) -> tuple[int, int]:
    info = probe(path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    raise FFmpegError(f"no video stream in {path}")


class FrameReader:
    """Stream RGB frames from a video or a still, looped to ``count`` frames."""

    def __init__(self, path: str | Path, width: int, height: int, fps: float, count: int):
        self.width = width
        self.height = height
        self.frame_bytes = width * height * 3
        self.count = count
        still = is_still(path)
        cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-nostdin"]
        if still:
            cmd += ["-loop", "1", "-i", str(path)]
        else:
            cmd += ["-stream_loop", "-1", "-i", str(path)]
        cmd += [
            "-vf",
            f"scale={width}:{height}:flags=bilinear,fps={fps},format=rgb24",
            "-frames:v",
            str(count),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
        self._stderr: list[bytes] = []
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._thread = threading.Thread(target=_drain, args=(self._proc.stderr, self._stderr), daemon=True)
        self._thread.start()
        self._left = count
        self._closed = False

    def read(self) -> np.ndarray:
        assert self._proc.stdout is not None
        buf = self._proc.stdout.read(self.frame_bytes)
        if len(buf) != self.frame_bytes:
            self.close()
            err = b"".join(self._stderr).decode("utf-8", errors="replace")[-2000:]
            raise FFmpegError(f"short read from ffmpeg ({len(buf)} bytes). {err}")
        self._left -= 1
        return np.frombuffer(buf, dtype=np.uint8).reshape((self.height, self.width, 3)).copy()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._proc.poll() is None:
            self._proc.kill()
        self._proc.wait()
        self._thread.join(timeout=2)

    def __iter__(self):
        try:
            for _ in range(self.count):
                yield self.read()
        finally:
            self.close()


class FrameWriter:
    """Encode raw RGB frames. Optional extra ffmpeg inputs carry audio."""

    def __init__(
        self,
        path: str | Path,
        width: int,
        height: int,
        fps: float,
        *,
        crf: int = 20,
        preset: str = "medium",
        extra_inputs: list[str] | None = None,
        filter_complex: str | None = None,
        maps: list[str] | None = None,
        audio: bool = False,
    ):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-v",
            "error",
            "-nostdin",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
        ]
        if extra_inputs:
            cmd += extra_inputs
        if filter_complex:
            cmd += ["-filter_complex", filter_complex]
        if maps:
            for item in maps:
                cmd += ["-map", item]
        else:
            cmd += ["-map", "0:v"]
        cmd += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-movflags",
            "+faststart",
        ]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "160k"]
        else:
            cmd += ["-an"]
        cmd.append(self.path)
        self._stderr: list[bytes] = []
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self._thread = threading.Thread(target=_drain, args=(self._proc.stderr, self._stderr), daemon=True)
        self._thread.start()
        self._closed = False

    def write(self, frame: np.ndarray) -> None:
        assert self._proc.stdin is not None
        try:
            self._proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        except BrokenPipeError as exc:
            self.close()
            err = b"".join(self._stderr).decode("utf-8", errors="replace")[-3000:]
            raise FFmpegError(f"encoder closed the pipe:\n{err}") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._proc.stdin and not self._proc.stdin.closed:
            self._proc.stdin.close()
        code = self._proc.wait()
        self._thread.join(timeout=5)
        if code != 0:
            err = b"".join(self._stderr).decode("utf-8", errors="replace")[-4000:]
            raise FFmpegError(f"encoder failed ({code}):\n{err}")
