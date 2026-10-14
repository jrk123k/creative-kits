import unittest

from inwwt.palette import COLODORE, NAMES, PEPTO, get_palette, hex_colors


class PaletteTests(unittest.TestCase):
    def test_sixteen_named_colors(self):
        self.assertEqual(len(NAMES), 16)
        self.assertEqual(len(PEPTO), 16)
        self.assertEqual(len(COLODORE), 16)
        self.assertEqual(len(set(PEPTO)), 16)
        self.assertEqual(len(set(COLODORE)), 16)

    def test_pepto_published_hex(self):
        # Philip "Pepto" Timmermann, 2001, pepto.de/projects/colorvic
        # and VICE pepto-pal.vpl.
        self.assertEqual(PEPTO[0], (0x00, 0x00, 0x00))
        self.assertEqual(PEPTO[1], (0xFF, 0xFF, 0xFF))
        self.assertEqual(PEPTO[6], (0x35, 0x28, 0x79))  # blue
        self.assertEqual(PEPTO[14], (0x6C, 0x5E, 0xB5))  # light blue
        self.assertEqual(PEPTO[15], (0x95, 0x95, 0x95))
        self.assertEqual(hex_colors("pepto")[6], "#352879")

    def test_colodore_vice_hex(self):
        # VICE data/C64/colodore.vpl, "Colodore (PAL)", from colodore.com.
        self.assertEqual(COLODORE[6], (0x27, 0x24, 0xC4))
        self.assertEqual(COLODORE[14], (0x68, 0x64, 0xFF))
        self.assertEqual(COLODORE[3], (0x5B, 0xD6, 0xCE))

    def test_unknown_palette(self):
        with self.assertRaises(ValueError):
            get_palette("cga")

    def test_array_shape(self):
        self.assertEqual(get_palette("Pepto").shape, (16, 3))


if __name__ == "__main__":
    unittest.main()
