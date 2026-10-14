import unittest

import numpy as np

from inwwt.dither import bayer, bayer_matrix, floyd_steinberg, floyd_steinberg_native, nearest
from inwwt.palette import get_palette


class DitherTests(unittest.TestCase):
    def test_bayer_4x4_is_the_standard_matrix(self):
        self.assertEqual(
            bayer_matrix(4).tolist(),
            [
                [0, 8, 2, 10],
                [12, 4, 14, 6],
                [3, 11, 1, 9],
                [15, 7, 13, 5],
            ],
        )

    def test_bayer_size_must_be_power_of_two(self):
        with self.assertRaises(ValueError):
            bayer_matrix(3)

    def test_nearest_uses_only_palette_colors(self):
        palette = get_palette("pepto")
        image = np.random.default_rng(0).integers(0, 256, size=(24, 32, 3), dtype=np.uint8)
        out = nearest(image, palette)
        self.assertTrue(set(map(tuple, out.reshape(-1, 3))).issubset(set(map(tuple, palette))))

    def test_flat_black_stays_black_under_modest_bayer(self):
        palette = get_palette("pepto")
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        out = bayer(image, palette, size=4, spread=48)
        self.assertTrue(np.all(out == 0))

    def test_bayer_breaks_up_a_flat_gray(self):
        palette = get_palette("pepto")
        image = np.full((32, 32, 3), 128, dtype=np.uint8)
        out = bayer(image, palette, size=8, spread=64)
        colors = np.unique(out.reshape(-1, 3), axis=0)
        self.assertGreater(len(colors), 1)
        self.assertTrue(set(map(tuple, colors)).issubset(set(map(tuple, palette))))

    def test_native_floyd_spreads_error_to_the_right(self):
        # 200 is closer to white than black. Error is 200-255 = -55.
        # The pixel on the right receives (-55 * 7) // 16 = -24, and stays black.
        palette = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        image = np.array([[[200, 200, 200], [0, 0, 0]]], dtype=np.uint8)
        out = floyd_steinberg_native(image, palette)
        self.assertEqual(out[0, 0].tolist(), [255, 255, 255])
        self.assertEqual(out[0, 1].tolist(), [0, 0, 0])

    def test_pillow_floyd_stays_inside_the_c64_palette(self):
        palette = get_palette("colodore")
        ramp = np.linspace(0, 255, 48, dtype=np.uint8)
        image = np.stack([np.tile(ramp, (24, 1))] * 3, axis=-1)
        out = floyd_steinberg(image, palette)
        colors = set(map(tuple, np.unique(out.reshape(-1, 3), axis=0)))
        self.assertTrue(colors.issubset(set(map(tuple, palette))))
        self.assertGreater(len(colors), 1)


if __name__ == "__main__":
    unittest.main()
