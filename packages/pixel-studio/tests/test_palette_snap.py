"""palette_snap: OKLab nearest, Bayer dither, alpha, TG16 clamp."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from palette_snap.cli import main
from palette_snap.palette import LEVELS, snap_image
from palette_snap.snap import extract_palette, oklab_to_srgb_u8, snap_rgba, srgb_u8_to_oklab

ROOT = Path(__file__).resolve().parents[1]
PALETTE_SHA256 = "e34677d556defe8157f7e000650d8035771d007dd91fca1c1157fa56cdb60ba9"


def _rgba(color, w=4, h=4, alpha=255):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = color[0]
    img[..., 1] = color[1]
    img[..., 2] = color[2]
    img[..., 3] = alpha
    return img


class PaletteReuseTests(unittest.TestCase):
    def test_palette_py_is_the_intro_kit_file(self):
        raw = (ROOT / "palette_snap" / "palette.py").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PALETTE_SHA256)

    def test_lattice_and_snap_image(self):
        self.assertEqual(LEVELS, (0, 36, 72, 109, 145, 182, 218, 255))
        src = np.array([[[10, 20, 30], [128, 255, 109]]], dtype=np.uint8)
        got = snap_image(src)
        self.assertEqual(got[0, 0].tolist(), [0, 36, 36])
        self.assertEqual(got[0, 1].tolist(), [145, 255, 109])
        self.assertTrue(np.array_equal(snap_image(got), got))


class ExtractTests(unittest.TestCase):
    def test_most_frequent_then_first_seen(self):
        img = np.zeros((1, 8, 4), dtype=np.uint8)
        img[..., 3] = 255
        # 5 red, 2 blue, 1 green. Green appears before blue.
        img[0, :, :3] = (255, 0, 0)
        img[0, 0, :3] = (0, 255, 0)
        img[0, 1, :3] = (0, 0, 255)
        img[0, 2, :3] = (0, 0, 255)
        pal = extract_palette(img, 2)
        self.assertEqual(pal.tolist(), [[255, 0, 0], [0, 0, 255]])

    def test_transparent_pixels_do_not_count(self):
        img = _rgba((0, 0, 0), w=6, h=1, alpha=0)
        img[0, 5] = (10, 20, 30, 255)
        pal = extract_palette(img, 8)
        self.assertEqual(pal.tolist(), [[10, 20, 30]])

    def test_no_opaque_pixels(self):
        with self.assertRaises(ValueError):
            extract_palette(_rgba((1, 2, 3), alpha=0), 4)

    def test_tg16_merges_before_the_cap(self):
        img = np.zeros((1, 3, 4), dtype=np.uint8)
        img[..., 3] = 255
        img[0, 0, :3] = (10, 20, 30)  # -> (0, 36, 36)
        img[0, 1, :3] = (1, 30, 40)  # -> (0, 36, 36)
        img[0, 2, :3] = (255, 255, 255)
        pal = extract_palette(img, 8, tg16=True)
        self.assertEqual(pal.tolist(), [[0, 36, 36], [255, 255, 255]])


class SnapTests(unittest.TestCase):
    def test_exact_palette_color_is_stable(self):
        pal = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
        img = _rgba((255, 0, 0), w=8, h=8)
        out = snap_rgba(img, pal, dither=True, dither_strength=1)
        self.assertTrue(np.all(out[..., :3] == (255, 0, 0)))
        self.assertTrue(np.all(out[..., 3] == 255))

    def test_alpha_channel_is_copied(self):
        pal = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        img = _rgba((20, 30, 40), w=5, h=3, alpha=0)
        img[..., 3] = np.arange(15, dtype=np.uint8).reshape(3, 5)
        img[0, 0, :3] = (9, 9, 9)
        out = snap_rgba(img, pal)
        self.assertTrue(np.array_equal(out[..., 3], img[..., 3]))
        # Alpha 0 keeps the original RGB, including a non-palette color.
        self.assertEqual(out[0, 0, :3].tolist(), [9, 9, 9])
        # Partial alpha is quantized, alpha byte unchanged.
        self.assertEqual(int(out[0, 1, 3]), 1)
        self.assertIn(out[0, 1, :3].tolist(), ([0, 0, 0], [255, 255, 255]))

    def test_uses_oklab_when_it_disagrees_with_rgb(self):
        pal = np.array(
            [
                [0, 0, 0],
                [255, 0, 0],
                [0, 255, 0],
                [0, 0, 255],
                [255, 255, 0],
                [0, 255, 255],
                [255, 0, 255],
                [128, 128, 128],
            ],
            dtype=np.uint8,
        )
        pal_lab = srgb_u8_to_oklab(pal.reshape(-1, 1, 3)).reshape(-1, 3)
        found = None
        for r in range(0, 256, 17):
            for g in range(0, 256, 17):
                for b in range(0, 256, 17):
                    pix = np.array([r, g, b], dtype=np.int16)
                    rgb_i = int(np.sum((pal.astype(np.int16) - pix) ** 2, axis=1).argmin())
                    lab = srgb_u8_to_oklab(np.array([[[r, g, b]]], dtype=np.uint8)).reshape(3)
                    ok_i = int(np.sum((pal_lab - lab) ** 2, axis=1).argmin())
                    if rgb_i != ok_i:
                        found = ((r, g, b), ok_i)
                        break
                if found:
                    break
            if found:
                break
        self.assertIsNotNone(found, "expected an OKLab/RGB disagreement")
        color, ok_i = found
        out = snap_rgba(_rgba(color, w=1, h=1), pal)
        self.assertEqual(out[0, 0, :3].tolist(), pal[ok_i].tolist())

    def test_only_reference_colors(self):
        ref = np.zeros((2, 2, 4), dtype=np.uint8)
        ref[..., 3] = 255
        ref[0, 0, :3] = (255, 0, 0)
        ref[0, 1, :3] = (0, 0, 255)
        ref[1, :, :3] = (255, 0, 0)
        src = _rgba((0, 255, 0), w=6, h=4)
        pal = extract_palette(ref, 2)
        out = snap_rgba(src, pal)
        flat = out[..., :3].reshape(-1, 3)
        for row in flat:
            self.assertIn(row.tolist(), ([255, 0, 0], [0, 0, 255]))

    def test_cap_is_n_colors(self):
        rng = np.random.default_rng(0)
        img = np.zeros((32, 32, 4), dtype=np.uint8)
        img[..., :3] = rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)
        img[..., 3] = 255
        pal = extract_palette(img, 5)
        self.assertEqual(len(pal), 5)
        out = snap_rgba(img, pal)
        uniq = np.unique(out[..., :3].reshape(-1, 3), axis=0)
        self.assertLessEqual(len(uniq), 5)
        for row in uniq:
            self.assertIn(row.tolist(), pal.tolist())

    def test_midpoint_dither_splits_black_and_white(self):
        pal = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        black = srgb_u8_to_oklab(np.array([[[0, 0, 0]]], dtype=np.uint8))
        white = srgb_u8_to_oklab(np.array([[[255, 255, 255]]], dtype=np.uint8))
        mid = oklab_to_srgb_u8((black + white) / 2.0)[0, 0]
        img = _rgba(mid.tolist(), w=16, h=16)
        flat = snap_rgba(img, pal, dither=False)
        self.assertEqual(len(np.unique(flat[..., :3].reshape(-1, 3), axis=0)), 1)
        dith = snap_rgba(img, pal, dither=True, dither_strength=1)
        colors = np.unique(dith[..., :3].reshape(-1, 3), axis=0)
        self.assertEqual(sorted(map(tuple, colors.tolist())), [(0, 0, 0), (255, 255, 255)])
        # Bayer repeats every 8 pixels.
        self.assertTrue(np.array_equal(dith[:8, :8, :3], dith[8:, 8:, :3]))

    def test_dither_is_deterministic_and_period_8(self):
        pal = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        ramp = np.zeros((8, 64, 4), dtype=np.uint8)
        ramp[..., 3] = 255
        for x in range(64):
            ramp[:, x, :3] = int(round(x * 255 / 63))
        a = snap_rgba(ramp, pal, dither=True)
        b = snap_rgba(ramp, pal, dither=True)
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.all(a[:, 0, :3] == 0))
        self.assertTrue(np.all(a[:, -1, :3] == 255))

    def test_tg16_output_is_on_the_lattice(self):
        rng = np.random.default_rng(1)
        img = np.zeros((24, 24, 4), dtype=np.uint8)
        img[..., :3] = rng.integers(0, 256, size=(24, 24, 3), dtype=np.uint8)
        img[..., 3] = 255
        img[0, 0, 3] = 0
        img[0, 0, :3] = (12, 34, 56)
        pal = extract_palette(img, 32, tg16=True)
        out = snap_rgba(img, pal, tg16=True)
        self.assertEqual(out[0, 0].tolist(), [12, 34, 56, 0])
        opaque = out[..., 3] > 0
        vals = out[..., :3][opaque]
        for channel in range(3):
            self.assertTrue(set(np.unique(vals[:, channel]).tolist()).issubset(set(LEVELS)))
        self.assertLessEqual(len(np.unique(vals, axis=0)), 32)

    def test_rgb_input_becomes_opaque_rgba(self):
        pal = np.array([[0, 0, 0]], dtype=np.uint8)
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[..., :] = (8, 8, 8)
        out = snap_rgba(rgb, pal)
        self.assertEqual(out.shape, (2, 2, 4))
        self.assertTrue(np.all(out[..., 3] == 255))
        self.assertTrue(np.all(out[..., :3] == 0))


class CliTests(unittest.TestCase):
    def test_cli_writes_png_and_palette_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_path = root / "in.png"
            ref_path = root / "ref.png"
            out_path = root / "nested" / "out.png"
            pal_path = root / "pal.json"
            Image.fromarray(_rgba((180, 40, 40), w=10, h=8), "RGBA").save(src_path)
            ref = np.zeros((4, 4, 4), dtype=np.uint8)
            ref[..., 3] = 255
            ref[..., :3] = (255, 0, 0)
            ref[0, 0, :3] = (0, 0, 128)
            Image.fromarray(ref, "RGBA").save(ref_path)
            code = main(
                [
                    str(src_path),
                    "-o",
                    str(out_path),
                    "-r",
                    str(ref_path),
                    "-n",
                    "2",
                    "--tg16",
                    "--palette-out",
                    str(pal_path),
                ]
            )
            self.assertEqual(code, 0)
            with Image.open(out_path) as im:
                got = np.asarray(im.convert("RGBA"))
            self.assertEqual(got.shape, (8, 10, 4))
            self.assertTrue(np.all(got[..., 3] == 255))
            payload = json.loads(pal_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["tg16"])
            self.assertEqual(payload["space"], "oklab")
            self.assertLessEqual(len(payload["colors"]), 2)
            for entry in payload["colors"]:
                for channel in entry["rgb"]:
                    self.assertIn(channel, LEVELS)

    def test_module_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "in.png"
            out = root / "out.png"
            Image.fromarray(_rgba((0, 0, 0), w=2, h=2), "RGBA").save(src)
            proc = subprocess.run(
                [sys.executable, "-m", "palette_snap", str(src), "-o", str(out), "-n", "1"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out.is_file())

    def test_cli_rejects_empty_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "in.png"
            Image.fromarray(_rgba((0, 0, 0), alpha=0), "RGBA").save(src)
            code = main([str(src), "-o", str(root / "out.png")])
            self.assertEqual(code, 1)
            self.assertFalse((root / "out.png").exists())


if __name__ == "__main__":
    unittest.main()
