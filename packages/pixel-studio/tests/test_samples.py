"""Shipped sample plates follow the intro kit's size, alpha, and palette rules."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from palette_snap.palette import LEVELS

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "studio" / "samples"


def _rgba(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"))


def _assert_lattice(test: unittest.TestCase, img: np.ndarray) -> None:
    opaque = img[..., 3] > 0
    vals = img[..., :3][opaque]
    for channel in range(3):
        test.assertTrue(set(np.unique(vals[:, channel]).tolist()).issubset(set(LEVELS)))


class SampleAssetTests(unittest.TestCase):
    def test_singer_plate_and_patch(self):
        manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
        mouth = manifest["mouth"]
        closed = _rgba(SAMPLES / "singer_256.png")
        opened = _rgba(SAMPLES / "singer_open_256.png")
        patch = _rgba(SAMPLES / mouth["patch"]["file"])
        self.assertEqual(closed.shape, (224, 256, 4))
        self.assertEqual(opened.shape, (224, 256, 4))
        self.assertTrue(np.all(closed[..., 3] == 255))
        self.assertTrue(np.all(opened[..., 3] == 255))
        _assert_lattice(self, closed)
        _assert_lattice(self, opened)
        x, y = mouth["patch"]["x"], mouth["patch"]["y"]
        self.assertEqual(patch.shape[1], mouth["patch"]["w"])
        self.assertEqual(patch.shape[0], mouth["patch"]["h"])
        pasted = closed.copy()
        pasted[y : y + patch.shape[0], x : x + patch.shape[1]] = patch
        self.assertTrue(np.array_equal(pasted, opened))
        self.assertGreater(int(np.any(closed != opened, axis=-1).sum()), 0)

    def test_walker_is_hard_alpha_on_the_lattice(self):
        manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
        frames = [_rgba(SAMPLES / name) for name in manifest["walk"]["frames"]]
        shape = frames[0].shape
        self.assertLess(shape[0], 224)
        self.assertLess(shape[1], 256)
        for frame in frames:
            self.assertEqual(frame.shape, shape)
            alphas = set(np.unique(frame[..., 3]).tolist())
            self.assertTrue(alphas.issubset({0, 255}))
            self.assertIn(0, alphas)
            self.assertIn(255, alphas)
            _assert_lattice(self, frame)
        hill = _rgba(SAMPLES / manifest["walk"]["background"])
        self.assertEqual(hill.shape, (224, 256, 4))
        _assert_lattice(self, hill)

    def test_palette_png_matches_json(self):
        payload = json.loads((ROOT / "studio" / "palettes" / "tg16.json").read_text(encoding="utf-8"))
        with Image.open(ROOT / "studio" / "palettes" / "tg16.png") as im:
            img = np.asarray(im.convert("RGBA"))
        seen = []
        keys = set()
        flat = img.reshape(-1, 4)
        for row in flat:
            if int(row[3]) == 0:
                continue
            key = (int(row[0]), int(row[1]), int(row[2]))
            if key in keys:
                continue
            keys.add(key)
            seen.append(key)
        listed = [tuple(entry["rgb"]) for entry in payload["colors"]]
        self.assertEqual(seen, listed)
        for rgb in listed:
            self.assertTrue(all(channel in LEVELS for channel in rgb))


if __name__ == "__main__":
    unittest.main()
