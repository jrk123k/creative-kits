import unittest

import numpy as np

from inwwt.c64font import FONT_FILENAME, PETSCII_NAMES, ascii_to_screen, bundled_font_path, glyph
from inwwt.c64screen import NTSC_BLINK, PAL_BLINK, cursor_visible, render_program_frame
from inwwt.c64script import BANNER, RAM_LINE, READY, compile_script
from inwwt.palette import PEPTO


class FontTests(unittest.TestCase):
    def test_bundled_filename_is_styles(self):
        self.assertEqual(FONT_FILENAME, "C64_Pro_Mono-STYLE.ttf")
        self.assertTrue(bundled_font_path().is_file())

    def test_uppercase_a_matches_the_8x8_grid(self):
        bits = glyph(ascii_to_screen("A", "upper"), "upper")
        rows = ["".join("#" if v else "." for v in row) for row in bits]
        self.assertEqual(
            rows,
            [
                "........",
                "...##...",
                "..####..",
                ".##..##.",
                ".######.",
                ".##..##.",
                ".##..##.",
                ".##..##.",
            ],
        )

    def test_space_is_empty_and_reverse_space_is_a_block(self):
        self.assertEqual(int(glyph(32).sum()), 0)
        self.assertEqual(int(glyph(160).sum()), 64)

    def test_named_graphics_are_real_screen_codes(self):
        self.assertEqual(PETSCII_NAMES["spade"], 65)
        self.assertEqual(PETSCII_NAMES["heart"], 83)
        self.assertGreater(int(glyph(PETSCII_NAMES["spade"]).sum()), 8)


class ScriptTests(unittest.TestCase):
    def test_boot_screen_matches_the_basic_rom(self):
        program = compile_script("")
        cells, _colors, row, col, charset = program.state_at(0)
        self.assertEqual(charset, "upper")
        self.assertEqual((row, col), (6, 0))

        def row_text(index: int) -> str:
            chars = []
            for code in cells[index]:
                code = int(code)
                if code == 32:
                    chars.append(" ")
                elif 1 <= code <= 26:
                    chars.append(chr(code + 64))
                elif 33 <= code <= 63:
                    chars.append(chr(code))
                else:
                    chars.append("?")
            return "".join(chars).rstrip()

        self.assertEqual(row_text(1), BANNER.rstrip())
        self.assertEqual(row_text(3), RAM_LINE.rstrip())
        self.assertEqual(row_text(5), READY)
        self.assertEqual(len(BANNER), 35)
        self.assertEqual(len(RAM_LINE), 39)
        self.assertLessEqual(len(BANNER), 40)
        self.assertLessEqual(len(RAM_LINE), 40)

    def test_per_character_delay_and_typo(self):
        program = compile_script(".noboot\n.delay 0.1\nAB{typo:X:Y}\n")
        def text_at(t):
            cells, *_rest = program.state_at(t)
            return "".join(chr(int(c) + 64) if 1 <= int(c) <= 26 else " " for c in cells[0]).rstrip()

        self.assertEqual(text_at(0.35), "ABX")
        self.assertEqual(text_at(0.60), "AB")
        self.assertEqual(text_at(0.70), "ABY")

    def test_one_shot_delay(self):
        program = compile_script(".noboot\n.delay 0.5\nA{d:0.1}B\n")
        cells, *_rest = program.state_at(0.55)
        self.assertEqual(int(cells[0, 0]), ascii_to_screen("A"))
        self.assertEqual(int(cells[0, 1]), 32)
        cells, *_rest = program.state_at(0.65)
        self.assertEqual(int(cells[0, 1]), ascii_to_screen("B"))

    def test_petscii_token_and_lower_charset(self):
        program = compile_script(".noboot\n.delay 0\n{spade}{heart}\n")
        cells, *_rest = program.state_at(0)
        self.assertEqual(int(cells[0, 0]), 65)
        self.assertEqual(int(cells[0, 1]), 83)

        lower = compile_script(".noboot\n.charset lower\n.delay 0\nAb\n")
        cells, _c, _r, _col, charset = lower.state_at(0)
        self.assertEqual(charset, "lower")
        self.assertEqual(int(cells[0, 0]), ord("A"))
        self.assertEqual(int(cells[0, 1]), ord("b") - 96)

    def test_ready_directive_and_scroll(self):
        program = compile_script(".noboot\n.delay 0\n.ready\n")
        cells, _c, row, col, _set = program.state_at(1)
        # Leading CR, READY., trailing CR, so the word is on row 1 and the cursor on row 2.
        chars = []
        for code in cells[1, :6]:
            code = int(code)
            if 1 <= code <= 26:
                chars.append(chr(code + 64))
            elif 32 <= code <= 63:
                chars.append(chr(code))
        self.assertEqual("".join(chars), "READY.")
        self.assertEqual((row, col), (2, 0))

        # One row of X, then enough full rows of Y to scroll the X off the top.
        lines = ".noboot\n.delay 0\n" + ("X" * 40) + "\n" + ("\n".join(["Y" * 40] * 24)) + "\n"
        scrolled = compile_script(lines)
        cells, _c, row, col, _set = scrolled.state_at(0)
        self.assertTrue(np.all(cells[:24] == ascii_to_screen("Y")))
        self.assertTrue(np.all(cells[24] == 32))
        self.assertEqual((row, col), (24, 0))


class ScreenTests(unittest.TestCase):
    def test_cursor_blinks_at_the_kernal_rate(self):
        self.assertAlmostEqual(NTSC_BLINK, 20 / 60)
        self.assertAlmostEqual(PAL_BLINK, 20 / 50)
        self.assertTrue(cursor_visible(0.0, NTSC_BLINK))
        self.assertTrue(cursor_visible(0.30, NTSC_BLINK))
        self.assertFalse(cursor_visible(NTSC_BLINK + 0.01, NTSC_BLINK))

    def test_1080p_is_an_integer_nearest_upscale(self):
        program = compile_script(".hold 0\n")
        frame = render_program_frame(program, 0.0, palette_name="pepto", scale=5)
        self.assertEqual(frame.shape, (1080, 1920, 3))
        small = frame[::5, ::5]
        back = np.repeat(np.repeat(small, 5, axis=0), 5, axis=1)
        self.assertTrue(np.array_equal(frame, back))

        border = tuple(int(v) for v in PEPTO[14])
        background = tuple(int(v) for v in PEPTO[6])
        self.assertEqual(tuple(int(v) for v in frame[0, 0]), border)
        # Text area starts at the low-res border (32, 8) times the scale.
        self.assertEqual(tuple(int(v) for v in frame[8 * 5, 32 * 5]), background)

    def test_cursor_cell_toggles(self):
        program = compile_script("")
        on = render_program_frame(program, 0.0, scale=5)
        off = render_program_frame(program, NTSC_BLINK + 0.02, scale=5)
        # Cursor is row 6, col 0 of the text matrix.
        y = (8 + 6 * 8) * 5
        x = 32 * 5
        self.assertEqual(tuple(int(v) for v in on[y, x]), tuple(int(v) for v in PEPTO[14]))
        self.assertEqual(tuple(int(v) for v in off[y, x]), tuple(int(v) for v in PEPTO[6]))
        self.assertFalse(np.array_equal(on, off))


if __name__ == "__main__":
    unittest.main()
