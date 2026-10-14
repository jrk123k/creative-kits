"""The synthetic cow and the singer mouth pack, unpack, and load in the kit."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from examples.demo.make_art import generate
from spritepack.adapt import adapt_file
from spritepack.build import pack_folder, unpack_folder
from spritepack.images import load_png
from spritepack.mouth import paste_rgb, rgb_equal

INTROKIT = Path("/tmp/introkit")


class DemoArtTests(unittest.TestCase):
    def test_cow_is_14x12_and_the_mouth_patch_pastes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generate(root)
            for index in range(4):
                pixels, mode = load_png(root / "frames" / f"cow_{index}.png")
                self.assertEqual(mode, "RGBA")
                self.assertEqual(pixels.shape, (12, 14, 4))
                alpha = set(np.unique(pixels[..., 3]).tolist())
                self.assertTrue(alpha <= {0, 255})
            closed, _mode = load_png(root / "frames" / "singer_256.png")
            opened, _mode = load_png(root / "frames" / "singer_open_256.png")
            patch, _mode = load_png(root / "frames" / "singer_open_patch.png")
            self.assertEqual(closed.shape[:2], (224, 256))
            pasted = paste_rgb(closed, patch, 116, 124)
            self.assertTrue(rgb_equal(pasted, opened))

    def test_demo_round_trip_is_pixel_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            generate(root)
            built = pack_folder(
                root / "frames",
                Path(tmp) / "out",
                name="demo",
                padding=1,
                max_width=270,
                gif=False,
                mp4=False,
            )
            cow = built.meta.animation("cow")
            self.assertEqual(cow.frames, ["cow_0", "cow_1", "cow_2", "cow_3"])
            self.assertEqual(built.meta.frame("cow_0").anchor, (7, 12))
            self.assertEqual(built.meta.frame("cow_3").hold_frames, 12)
            self.assertEqual(built.meta.frame("cow_0").hold_frames, 4)
            singer = built.meta.animation("singer")
            self.assertEqual(singer.kind, "mouth")
            self.assertEqual(singer.patch["x"], 116)
            self.assertEqual(singer.patch["y"], 124)
            back = Path(tmp) / "back"
            unpack_folder(built.json_path, back)
            for frame in built.meta.frames:
                source, _mode = load_png(root / "frames" / frame.file)
                again, _mode = load_png(back / frame.file)
                self.assertTrue(np.array_equal(source, again), frame.file)

            intro = adapt_file(
                built.json_path,
                Path(tmp) / "kit",
                plate=root / "bg" / "hill_256.png",
                name="kit-demo",
            )
            doc = yaml.safe_load(intro.read_text())
            cow_layer = doc["scenes"][1]["layers"][1]
            self.assertEqual(cow_layer["x"], 153)
            self.assertEqual(cow_layer["y"], 164)
            self.assertEqual(cow_layer["frames"].count("art/cow_3.png"), 3)
            self.assertEqual(doc["mouths"]["singer"]["patch"]["x"], 116)
            if (INTROKIT / "introkit" / "__init__.py").is_file():
                sys.path.insert(0, str(INTROKIT))
                from introkit.project import load_project

                project = load_project(intro)
                self.assertEqual(project.total_frames, 60)
                self.assertEqual(project.scenes[0].mouth, "singer")


if __name__ == "__main__":
    unittest.main()
