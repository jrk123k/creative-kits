"""Mouth windows, duration, alignment, and the demo project."""

from __future__ import annotations

from pathlib import Path
import unittest

from introkit.film import Film
from introkit.project import load_project
from introkit.vocals import merge_words

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo" / "intro.yaml"


class KitTests(unittest.TestCase):
    def test_demo_duration_frames(self):
        project = load_project(DEMO)
        film = Film(project)
        self.assertGreater(film.frame_count, 0)

    def test_demo_loads(self):
        project = load_project(DEMO)
        self.assertTrue(project.shots)

    def test_merge_words(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.4, "speaker": "Nova"},
            {"word": "there", "start": 0.45, "end": 0.8, "speaker": "Nova"},
        ]
        lines = merge_words(words, gap=0.5, speaker="Nova")
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
