"""The demo MP4 is 1920x1080, lasts the timeline, and keeps the song packets."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from introkit.encode import render_movie, tail_pcm
from introkit.project import load_project

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo" / "intro.yaml"
ALIGN = ROOT / "examples" / "demo" / "intro_alignment.yaml"


def _probe(path: Path, entries: str) -> str:
    return subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True,
    ).strip()


def _packets(path: Path) -> list[int]:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "packet=size",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
    )
    sizes = []
    for line in out.splitlines():
        line = line.strip().strip(",")
        if line:
            sizes.append(int(line))
    return sizes


class EncodeTests(unittest.TestCase):
    def test_silence_tail_is_silent(self):
        project = load_project(ALIGN)
        pcm = tail_pcm(project)
        self.assertEqual(pcm.shape[0], int(round(2.3 * 44100)))
        self.assertEqual(float(np.max(np.abs(pcm))), 0.0)

    def test_demo_mp4(self):
        project = load_project(DEMO)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "demo.mp4"
            render_movie(project, dest, preset="veryfast")
            info = _probe(dest, "stream=width,height,codec_name")
            self.assertIn("1920", info)
            self.assertIn("1080", info)
            self.assertIn("h264", info)
            self.assertIn("mp3", info)
            duration = float(_probe(dest, "format=duration"))
            self.assertGreater(duration, 7.9)
            self.assertLess(duration, 8.25)
            song = _packets(project.audio_file)
            audio = dest.with_name(dest.stem + "_audio.mp3")
            joined = _packets(audio)
            self.assertEqual(joined[: len(song)], song)
            frame = Path(tmp) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(dest), "-vf", "select=eq(n\\,30)", "-frames:v", "1", str(frame)],
                check=True,
            )
            im = np.asarray(Image.open(frame).convert("RGB"))
            self.assertEqual(im.shape, (1080, 1920, 3))
            # 240px pillarbox on each side. The picture starts at x=240.
            self.assertEqual(int(im[:, :240].sum()), 0)
            self.assertEqual(int(im[:, -240:].sum()), 0)
            self.assertGreater(int(im[:, 240:-240].sum()), 0)


if __name__ == "__main__":
    unittest.main()
