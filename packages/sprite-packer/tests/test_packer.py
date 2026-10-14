"""Names, pixel round trip, anchors, durations, previews, and the kit mapping."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from spritepack.anchors import resolve_anchor
from spritepack.build import pack_folder, unpack_folder
from spritepack.cli import main
from spritepack.discover import classify, discover
from spritepack.errors import SpritePackError
from spritepack.images import load_png
from spritepack.mouth import diff_box, paste_rgb, rgb_equal
from spritepack.preview import render_animation
from spritepack.timing import hold_from_duration, kit_cycle
from spritepack.adapt import expanded_files, sprite_top_left
from spritepack.meta import read


def _png(path: Path, array: np.ndarray, mode: str = "RGBA") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, mode).save(path, format="PNG")


def _rgba(w, h, color) -> np.ndarray:
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = color[0]
    img[..., 1] = color[1]
    img[..., 2] = color[2]
    img[..., 3] = color[3] if len(color) == 4 else 255
    return img


class NamingTests(unittest.TestCase):
    def test_patterns_match_the_kit_and_pixel_studio(self):
        cases = {
            "cow_beam_0.png": ("cow_beam", 0, None, "numbered"),
            "cow_beam_10.png": ("cow_beam", 10, None, "numbered"),
            "name_0.png": ("name", 0, None, "numbered"),
            "walker_00.png": ("walker", 0, None, "numbered"),
            "walker_sprite_0.png": ("walker", 0, None, "sprite"),
            "walker_sprite_3.png": ("walker", 3, None, "sprite"),
            "saucer_sprite.png": ("saucer", 0, None, "sprite"),
            "singer_256.png": ("singer", 0, "closed", "plate"),
            "singer_open_256.png": ("singer", 1, "open", "plate"),
            "portrait_closeup_open_256.png": ("portrait_closeup", 1, "open", "plate"),
            "portrait_closeup_256.png": ("portrait_closeup", 0, "closed", "plate"),
            "singer_open_patch.png": ("singer", 0, "patch", "plate"),
            "notes.png": ("notes", 0, None, "single"),
        }
        for filename, expected in cases.items():
            self.assertEqual(classify(filename), expected, filename)

    def test_a_folder_keeps_several_animations_in_index_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("cow_2.png", "cow_0.png", "cow_10.png", "critter_1.png", "critter_0.png"):
                _png(folder / name, _rgba(2, 2, (1, 2, 3, 255)))
            found = discover([path for path in sorted(folder.glob("*.png"))])
            groups = {}
            for item in found:
                groups.setdefault(item.animation, []).append(item)
            cows = sorted(groups["cow"], key=lambda item: item.index)
            critters = sorted(groups["critter"], key=lambda item: item.index)
            self.assertEqual([item.file for item in cows], ["cow_0.png", "cow_2.png", "cow_10.png"])
            self.assertEqual([item.index for item in critters], [0, 1])

    def test_plate_extras_join_the_shot_and_open_is_not_frame_256(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("singer_256.png", "singer_open_256.png", "singer_blink.png"):
                _png(folder / name, _rgba(4, 4, (9, 9, 9, 255)))
            found = discover(list(folder.glob("*.png")))
            by_file = {item.file: item for item in found}
            self.assertEqual(by_file["singer_open_256.png"].animation, "singer")
            self.assertEqual(by_file["singer_open_256.png"].role, "open")
            self.assertEqual(by_file["singer_blink.png"].animation, "singer")
            self.assertEqual(by_file["singer_blink.png"].role, "blink")
            self.assertGreater(by_file["singer_blink.png"].index, 1)

    def test_mixed_styles_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _png(folder / "cow_0.png", _rgba(2, 2, (0, 0, 0, 255)))
            _png(folder / "cow_sprite_1.png", _rgba(2, 2, (0, 0, 0, 255)))
            with self.assertRaises(SpritePackError):
                discover(list(folder.glob("*.png")))


class RoundTripTests(unittest.TestCase):
    def test_pixels_survive_padding_and_partial_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            out = Path(tmp) / "out"
            # Alpha 0 keeps a nonzero RGB. A partial pixel is not composited away.
            a = np.zeros((3, 5, 4), dtype=np.uint8)
            a[0, 0] = (1, 2, 3, 0)
            a[1, 2] = (10, 20, 30, 128)
            a[2, 4] = (255, 0, 128, 255)
            b = _rgba(4, 2, (7, 8, 9, 255))
            b[0, 0] = (4, 5, 6, 0)
            _png(folder / "name_0.png", a)
            _png(folder / "name_1.png", b)
            _png(folder / "other_0.png", _rgba(2, 6, (40, 50, 60, 255)), "RGBA")
            built = pack_folder(folder, out, name="demo", padding=2, max_width=16, gif=False, mp4=False)
            atlas, _mode = load_png(built.atlas_path)
            self.assertEqual(atlas.shape[2], 4)
            for frame in built.meta.frames:
                x, y, w, h = frame.rect
                crop = atlas[y : y + h, x : x + w]
                source, _mode = load_png(folder / frame.file)
                self.assertTrue(np.array_equal(crop, source), frame.file)
                self.assertGreaterEqual(x, 2)
                self.assertGreaterEqual(y, 2)
            # Orthogonal neighbors stay at least padding apart.
            rects = [frame.rect for frame in built.meta.frames]
            for i, left in enumerate(rects):
                for right in rects[i + 1 :]:
                    self.assertFalse(_overlap(left, right))
            unpacked = Path(tmp) / "back"
            unpack_folder(built.json_path, unpacked)
            for frame in built.meta.frames:
                source, source_mode = load_png(folder / frame.file)
                again, again_mode = load_png(unpacked / frame.file)
                self.assertEqual(again_mode if source_mode == "RGB" else "RGBA", again_mode)
                self.assertTrue(np.array_equal(source, again), frame.file)

    def test_rgb_sources_come_back_as_rgb(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            rgb = np.zeros((2, 2, 3), dtype=np.uint8)
            rgb[0, 0] = (12, 34, 56)
            _png(folder / "still_0.png", rgb, "RGB")
            built = pack_folder(folder, Path(tmp) / "out", gif=False, mp4=False)
            unpack_folder(built.json_path, Path(tmp) / "back")
            with Image.open(Path(tmp) / "back" / "still_0.png") as im:
                self.assertEqual(im.mode, "RGB")
                self.assertTrue(np.array_equal(np.array(im), rgb))


class AnchorDurationTests(unittest.TestCase):
    def test_bottom_center_of_a_14x12_frame_is_7_12(self):
        self.assertEqual(resolve_anchor("bottom-center", 14, 12), (7, 12))
        self.assertEqual(resolve_anchor("top-left", 14, 12), (0, 0))
        self.assertEqual(resolve_anchor("center", 14, 12), (7, 6))

    def test_default_hold_is_4_at_30_fps_and_overrides_win(self):
        self.assertEqual(hold_from_duration(133.333, 30), 4)
        self.assertEqual(hold_from_duration(400, 30), 12)
        self.assertEqual(kit_cycle([4, 4, 4, 12]), (4, [1, 1, 1, 3]))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            for index in range(4):
                _png(folder / f"cow_{index}.png", _rgba(14, 12, (255, 255, 255, 255)))
            sidecar = {
                "fps": 30,
                "hold": 4,
                "anchor": "bottom-center",
                "animations": {
                    "cow": {
                        "frames": {"cow_3.png": {"duration_ms": 400, "anchor": [3, 11]}},
                        "cycle": {"mode": "once", "skip_last": 1},
                    }
                },
            }
            (folder / "sprites.json").write_text(json.dumps(sidecar))
            built = pack_folder(
                folder,
                Path(tmp) / "out",
                frame_durations={"cow_1.png": 100},
                gif=False,
                mp4=False,
            )
            by_file = {frame.file: frame for frame in built.meta.frames}
            self.assertEqual(by_file["cow_0.png"].hold_frames, 4)
            self.assertEqual(by_file["cow_0.png"].anchor, (7, 12))
            self.assertEqual(by_file["cow_1.png"].hold_frames, 3)  # CLI 100 ms at 30 fps
            self.assertEqual(by_file["cow_3.png"].hold_frames, 12)
            self.assertEqual(by_file["cow_3.png"].anchor, (3, 11))
            cow = built.meta.animation("cow")
            self.assertEqual(cow.cycle_mode, "once")
            self.assertEqual(cow.skip_last, 1)
            hold, files = expanded_files(built.meta, cow)
            self.assertEqual(hold, 1)  # gcd(4, 3, 4, 12) == 1
            self.assertEqual(files.count("art/cow_3.png"), 12)
            self.assertEqual(files.count("art/cow_1.png"), 3)

    def test_kit_top_left_for_the_demo_cow(self):
        # 14×12, bottom-center (7, 12), planted at (160, 176).
        self.assertEqual(sprite_top_left((7, 12), (160, 176)), (153, 164))


class MouthTests(unittest.TestCase):
    def test_patch_paste_matches_the_open_plate(self):
        closed = np.zeros((8, 10, 4), dtype=np.uint8)
        closed[..., 0] = 20
        closed[..., 3] = 255
        opened = closed.copy()
        opened[2:5, 3:8] = (200, 10, 10, 255)
        box = diff_box(closed, opened)
        self.assertEqual(box, (3, 2, 5, 3))
        patch = opened[2:5, 3:8]
        pasted = paste_rgb(closed, patch, 3, 2)
        self.assertTrue(rgb_equal(pasted, opened))

    def test_plate_names_pack_a_mouth_and_a_numbered_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            closed = np.full((6, 8, 3), 30, dtype=np.uint8)
            opened = closed.copy()
            opened[1:4, 2:6] = (180, 20, 20)
            _png(folder / "bust_256.png", closed, "RGB")
            _png(folder / "bust_open_256.png", opened, "RGB")
            patch = opened[1:4, 2:6]
            _png(folder / "bust_open_patch.png", patch, "RGB")
            _png(folder / "cow_0.png", _rgba(14, 12, (255, 0, 0, 255)))
            _png(folder / "cow_1.png", _rgba(14, 12, (0, 255, 0, 255)))
            built = pack_folder(folder, Path(tmp) / "out", gif=False, mp4=False)
            mouth = built.meta.animation("bust")
            self.assertEqual(mouth.kind, "mouth")
            self.assertEqual(mouth.frames, ["bust_256", "bust_open_256"])
            self.assertEqual(mouth.patch["x"], 2)
            self.assertEqual(mouth.patch["y"], 1)
            self.assertEqual(mouth.patch["file"], "bust_open_patch.png")
            self.assertEqual(built.meta.animation("cow").kind, "sprite")
            self.assertEqual(len(built.meta.frames), 5)  # 2 plates + patch + 2 cow


class PreviewTests(unittest.TestCase):
    def test_integer_scale_is_nearest_and_mp4_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            sprite = np.zeros((2, 2, 4), dtype=np.uint8)
            sprite[0, 0] = (255, 0, 0, 255)
            sprite[1, 1] = (0, 0, 255, 128)
            other = sprite.copy()
            other[0, 0] = (0, 255, 0, 255)
            _png(folder / "dot_0.png", sprite)
            _png(folder / "dot_1.png", other)
            built = pack_folder(
                folder,
                Path(tmp) / "out",
                scale=4,
                background="#010203",
                hold=2,
                fps=10,
                gif=True,
                mp4=True,
            )
            meta = read(built.json_path)
            atlas, _mode = load_png(built.atlas_path)
            frames, durations = render_animation(meta, atlas, meta.animation("dot"))
            self.assertEqual(frames[0].shape, (8, 8, 3))
            # The red pixel is a 4×4 block. Anchor is bottom-center (1, 2),
            # so the frame sits in a tight canvas the size of the sprite.
            block = frames[0][0:4, 0:4]
            self.assertTrue(np.all(block == (255, 0, 0)))
            self.assertEqual(durations, [200, 200])
            gif = built.meta.path.parent / "dot.gif"
            with Image.open(gif) as im:
                self.assertEqual(im.n_frames, 2)
                self.assertEqual(im.size, (8, 8))
            mp4 = built.meta.path.parent / "dot.mp4"
            self.assertTrue(mp4.is_file())
            extracted = Path(tmp) / "frame0.png"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(mp4),
                    "-vf",
                    "select=eq(n\\,0)",
                    "-frames:v",
                    "1",
                    str(extracted),
                ],
                check=True,
            )
            with Image.open(extracted) as im:
                got = np.array(im.convert("RGB"))
            self.assertTrue(np.array_equal(got, frames[0]), "mp4 frame 0 drifted from the nearest-neighbor preview")


class AdaptTests(unittest.TestCase):
    def test_mapping_uses_top_left_and_repeated_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            for index, color in enumerate(((10, 10, 10, 255), (20, 20, 20, 255))):
                _png(folder / f"cow_{index}.png", _rgba(14, 12, color))
            (folder / "sprites.json").write_text(
                json.dumps(
                    {
                        "fps": 30,
                        "hold": 4,
                        "animations": {
                            "cow": {
                                "kit_place": [160, 176],
                                "frames": {"cow_1.png": {"duration_ms": 400}},
                            }
                        },
                    }
                )
            )
            built = pack_folder(folder, Path(tmp) / "out", name="demo", gif=False, mp4=False)
            code = main(["adapt", str(built.json_path), "-o", str(Path(tmp) / "kit")])
            self.assertEqual(code, 0)
            mapping = yaml.safe_load((Path(tmp) / "kit" / "mapping.yaml").read_text())
            cow = mapping["sprites"]["cow"]
            self.assertEqual(cow["x"], 153)
            self.assertEqual(cow["y"], 164)
            self.assertEqual(cow["cycle"]["hold"], 4)
            self.assertEqual(cow["frames"].count("art/cow_1.png"), 3)
            intro = yaml.safe_load((Path(tmp) / "kit" / "intro.yaml").read_text())
            layer = intro["scenes"][0]["layers"][1]
            self.assertEqual(layer["x"], 153)
            self.assertEqual(layer["y"], 164)
            self.assertEqual(layer["cycle"]["hold"], 4)


class PixelStudioManifestTests(unittest.TestCase):
    def test_manifest_orders_frames_and_keeps_the_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for index in range(4):
                _png(folder / f"walker_{index}.png", _rgba(4, 6, (index, 0, 0, 255)))
            _png(folder / "hill_bg_256.png", np.zeros((8, 8, 3), dtype=np.uint8), "RGB")
            manifest = {
                "walk": {
                    "shot": "walker",
                    "naming": "sprite",
                    "frames": ["walker_0.png", "walker_1.png", "walker_2.png", "walker_3.png"],
                    "hold": 4,
                    "fps": 8,
                    "background": "hill_bg_256.png",
                    "offset": [112, 136],
                }
            }
            (folder / "manifest.json").write_text(json.dumps(manifest))
            built = pack_folder(folder, Path(tmp) / "out", fps=30, gif=False, mp4=False)
            self.assertEqual([anim.name for anim in built.meta.animations], ["walker"])
            walker = built.meta.animation("walker")
            self.assertEqual(walker.place, (112, 136))
            self.assertEqual(walker.place_space, "top-left")
            self.assertEqual(walker.kit_top_left, (112, 136))
            # 4 frames at 8 fps is 500 ms, which is 15 frames at the packer's 30 fps.
            self.assertEqual(built.meta.frame("walker_0").hold_frames, 15)
            self.assertEqual(built.meta.frame("walker_0").duration_ms, 500.0)
            # The hill plate is a background, not a packed frame.
            self.assertNotIn("hill_bg_256", [frame.id for frame in built.meta.frames])


class CliTests(unittest.TestCase):
    def test_pack_and_unpack_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "frames"
            _png(folder / "name_0.png", _rgba(3, 3, (1, 2, 3, 255)))
            out = Path(tmp) / "out"
            code = main(["pack", str(folder), "-o", str(out), "--no-preview", "--name", "atlas"])
            self.assertEqual(code, 0)
            back = Path(tmp) / "back"
            code = main(["unpack", str(out / "atlas.json"), "-o", str(back)])
            self.assertEqual(code, 0)
            source, _mode = load_png(folder / "name_0.png")
            again, _mode = load_png(back / "name_0.png")
            self.assertTrue(np.array_equal(source, again))


def _overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


if __name__ == "__main__":
    unittest.main()
