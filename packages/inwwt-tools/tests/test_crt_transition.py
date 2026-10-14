import unittest

import numpy as np

from inwwt.crt import CRTParams, apply_crt
from inwwt.curves import CURVES, apply_curve
from inwwt.looks import LookParams, collapse
from inwwt.palette import get_palette
from inwwt.transition import TransitionConfig, stage_state


class CurveTests(unittest.TestCase):
    def test_endpoints_and_monotonic(self):
        for name in CURVES:
            self.assertAlmostEqual(apply_curve(0, name), 0.0)
            self.assertAlmostEqual(apply_curve(1, name), 1.0)
            samples = [apply_curve(i / 20, name) for i in range(21)]
            self.assertEqual(samples, sorted(samples))


class CRTTests(unittest.TestCase):
    def test_zero_strength_is_unchanged(self):
        image = np.random.default_rng(1).integers(0, 256, size=(30, 40, 3), dtype=np.uint8)
        out, _cache = apply_crt(image, 0.0)
        self.assertTrue(np.array_equal(out, image))

    def test_scanlines_darken_every_other_row(self):
        image = np.full((48, 64, 3), 180, dtype=np.uint8)
        out, _cache = apply_crt(image, 1.0, CRTParams(curvature=0.0, bloom=0.0, vignette=0.0, chroma=0.0, scanline=0.5))
        # Curvature 0 still runs the remap, but the center of a flat field is flat.
        even = int(out[20, 32, 0])
        odd = int(out[21, 32, 0])
        self.assertGreater(even, odd)

    def test_barrel_blackens_the_corner(self):
        image = np.full((48, 64, 3), 255, dtype=np.uint8)
        out, _cache = apply_crt(
            image,
            1.0,
            CRTParams(curvature=0.35, bloom=0.0, vignette=0.0, chroma=0.0, scanline=0.0),
        )
        self.assertLess(int(out[0, 0].max()), 16)
        self.assertGreater(int(out[24, 32].min()), 200)


class TransitionTests(unittest.TestCase):
    def test_stages_degrade_then_recover(self):
        cfg = TransitionConfig()
        start = stage_state(0.0, cfg)
        self.assertEqual(start.source, "a")
        self.assertEqual(start.crt, 0.0)
        self.assertEqual(start.pixel, 0.0)
        self.assertEqual(start.dither, 0.0)

        # Middle of the hold, on the eased clock. Sample a raw time whose
        # eased value sits inside the hold.
        hold = stage_state(0.5, cfg)
        self.assertEqual(hold.pixel, 1.0)
        self.assertEqual(hold.dither, 1.0)
        self.assertEqual(hold.crt, 1.0)

        end = stage_state(1.0, cfg)
        self.assertEqual(end.source, "b")
        self.assertEqual(end.crt, 0.0)
        self.assertEqual(end.pixel, 0.0)
        self.assertEqual(end.dither, 0.0)

    def test_frame_count(self):
        self.assertEqual(TransitionConfig(duration=6, fps=24).frame_count, 144)

    def test_bad_phases_rejected(self):
        with self.assertRaises(ValueError):
            TransitionConfig(crt_in_end=0.5, pixel_end=0.2, dither_end=0.6, hold_end=0.7, undither_end=0.8, unpixel_end=0.9)

    def test_full_collapse_uses_only_palette_colors(self):
        palette = get_palette("pepto")
        image = np.random.default_rng(2).integers(0, 256, size=(36, 64, 3), dtype=np.uint8)
        for method in ("bayer", "floyd"):
            out = collapse(image, 1.0, 1.0, LookParams(dither=method, c64_width=32, palette="pepto"))
            colors = set(map(tuple, np.unique(out.reshape(-1, 3), axis=0)))
            self.assertTrue(colors.issubset(set(map(tuple, palette))), method)
            self.assertEqual(out.shape, image.shape)


if __name__ == "__main__":
    unittest.main()
