"""Renderer, score syntax, presets, and the intro-kit API."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from chip.kit import SR, fit, note_pc, phrase_seconds, synthesize
from chip.psg import midi_to_divider, noise_period, side_gain
from chip.render import list_presets, render_preset, render_score
from chip.score import ScoreError, parse_score
from chip.tables import STOCK, STOCK_NAMES

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ["beam_hum", "blips", "jingle", "sting", "title_loop"]


def _periods(mono: np.ndarray) -> np.ndarray:
    x = mono.astype(np.float64)
    idx = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    if idx.size < 8:
        raise AssertionError(f"only {idx.size} zero crossings")
    return np.diff(idx).astype(np.float64)


class PsgTests(unittest.TestCase):
    def test_stock_tables_are_5bit(self):
        self.assertEqual(set(STOCK), set(STOCK_NAMES.values()))
        for name, wid in STOCK_NAMES.items():
            table = STOCK[wid]
            self.assertEqual(table.shape, (32,), name)
            self.assertGreaterEqual(int(table.min()), 0, name)
            self.assertLessEqual(int(table.max()), 31, name)

    def test_manual_scale_table(self):
        # Hudson scale table: A4 is register 254, C4 is 428.
        self.assertEqual(midi_to_divider(69), 254)
        self.assertEqual(midi_to_divider(60), 428)

    def test_a4_sounds_at_440(self):
        audio = render_score(
            "@tempo 60\n@master 15 15\nA o4 v31 w square p15,15 q8 l4 a\n",
            normalize=False,
        )
        # Skip the 1.5 ms edge ramps.
        periods = _periods(audio[800:-800, 0])
        hz = SR / float(periods.mean())
        self.assertAlmostEqual(hz, 440.45, delta=1.0)
        self.assertLess(float(periods.std()), 1.5)

    def test_volume_steps_are_1_5db(self):
        self.assertEqual(side_gain(31, 15, 15), 1.0)
        self.assertEqual(side_gain(0, 15, 15), 0.0)
        self.assertEqual(side_gain(31, 0, 15), 0.0)
        # Six channel-level steps is 9 dB.
        ratio = side_gain(25, 15, 15) / side_gain(31, 15, 15)
        self.assertAlmostEqual(ratio, 10 ** (-9 / 20), places=6)

    def test_pan_is_per_speaker(self):
        audio = render_score(
            "@tempo 60\nA o4 v31 w square p15,0 q8 l4 a\n",
            normalize=False,
        )
        self.assertGreater(float(np.max(np.abs(audio[:, 0]))), 0.2)
        self.assertLess(float(np.max(np.abs(audio[:, 1]))), 1e-8)

    def test_zero_volume_is_silent(self):
        audio = render_score("@tempo 60\nA o4 v0 w square q8 l4 a\n", normalize=False)
        self.assertLess(float(np.max(np.abs(audio))), 1e-8)

    def test_lfo_moves_the_pitch(self):
        plain = render_score(
            "@tempo 60\nA o4 v31 w square p15,15 q8 lf0 l4 a\n",
            normalize=False,
        )
        wobbled = render_score(
            "@tempo 60\nA o4 v31 w square p15,15 q8 lf1 lw triangle lr40 ld300 l4 a\n",
            normalize=False,
        )
        plain_std = float(_periods(plain[800:-800, 0]).std())
        lfo_std = float(_periods(wobbled[800:-800, 0]).std())
        self.assertLess(plain_std, 1.5)
        self.assertGreater(lfo_std, plain_std * 2)

    def test_noise_is_only_on_ef_and_is_not_a_tone(self):
        with self.assertRaises(ScoreError):
            parse_score("@tempo 120\nA n1 o4 c\n")
        audio = render_score(
            "@tempo 60\nE n1 nf16 v31 p15,15 q8 l4 c\n",
            normalize=False,
        )
        x = audio[400:-400, 0]
        self.assertGreater(float(np.max(x)), 0.2)
        self.assertLess(float(np.min(x)), -0.2)
        # A square wave's spectrum is peakier than the LFSR.
        tone = render_score("@tempo 60\nA o4 v31 w square p15,15 q8 l4 a\n", normalize=False)
        self.assertGreater(_flatness(x), _flatness(tone[400:-400, 0]) * 1.5)

    def test_noise_period_matches_the_inverted_field(self):
        self.assertEqual(noise_period(0x1F), 32)
        self.assertEqual(noise_period(0), 31 << 6)
        self.assertEqual(noise_period(30), 1 << 6)

    def test_six_channels_all_contribute(self):
        one = render_score("@tempo 120\nA o4 v20 w square q8 l4 c\n", normalize=False)
        six = render_score(
            "\n".join(
                [
                    "@tempo 120",
                    "A o4 v20 w square q8 l4 c",
                    "B o4 v20 w saw q8 l4 e",
                    "C o3 v20 w triangle q8 l4 g",
                    "D o3 v20 w organ q8 l4 c",
                    "E n1 nf12 v20 q8 l4 c",
                    "F n1 nf20 v20 q8 l4 c",
                ]
            ),
            normalize=False,
        )
        self.assertGreater(float(np.sqrt(np.mean(six**2))), float(np.sqrt(np.mean(one**2))) * 1.4)


class ScoreTests(unittest.TestCase):
    def test_lengths_repeats_and_ties(self):
        repeated = parse_score("@tempo 120\nA o4 l4 [c e]2\n")
        self.assertAlmostEqual(repeated.length_seconds, 2.0, places=6)
        tied = parse_score("@tempo 120\nA o4 l4 c & c\n")
        half = parse_score("@tempo 120\nA o4 l2 c\n")
        self.assertAlmostEqual(tied.length_seconds, half.length_seconds, places=6)
        # The tie removes the gap a gate would have left between the two quarters.
        self.assertEqual(tied.channels["A"][0].t1, tied.channels["A"][1].t0)

    def test_loop_point_and_disagreement(self):
        score = parse_score("@tempo 120\nA o4 l4 c | d e f\nB o4 l4 r | c c c\n")
        self.assertAlmostEqual(float(score.loop_start), 0.5, places=6)
        audio = render_score(score, loops=2)
        # Intro 0.5s plus two passes of the 1.5s body.
        self.assertEqual(audio.shape[0], int(round(3.5 * SR)))
        with self.assertRaises(ScoreError):
            parse_score("@tempo 120\nA o4 l4 c | d\nB o4 l4 c c |\n")

    def test_unknown_wave_and_empty(self):
        with self.assertRaises(ScoreError):
            parse_score("@tempo 120\nA w no-such-wave c\n")
        with self.assertRaises(ScoreError):
            parse_score("@tempo 120\n@master 15 15\n")

    def test_custom_wavetable(self):
        score = parse_score("@wave 6 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31\nA w6 o4 c\n")
        self.assertEqual(int(score.waves[6][-1]), 31)


class PresetTests(unittest.TestCase):
    def test_preset_names(self):
        self.assertEqual(list_presets(), PRESETS)

    def test_every_preset_renders(self):
        for name in PRESETS:
            with self.subTest(name=name):
                audio = render_preset(name)
                self.assertEqual(audio.ndim, 2)
                self.assertEqual(audio.shape[1], 2)
                self.assertEqual(audio.dtype, np.float32)
                self.assertTrue(np.isfinite(audio).all())
                self.assertGreater(audio.shape[0], SR // 2)
                self.assertGreater(float(np.max(np.abs(audio))), 0.05)
                self.assertLessEqual(float(np.max(np.abs(audio))), 0.9)

    def test_title_loop_is_23_beats_and_seamless(self):
        from chip.score import load_score

        score = load_score(ROOT / "chip" / "presets" / "title_loop.mml")
        self.assertAlmostEqual(score.length_beats, 23.0, places=6)
        for letter in "ABCE":
            beats = float(score.ends[letter] * score.tempo / 60)
            self.assertAlmostEqual(beats, 23.0, places=6, msg=letter)
        audio = render_preset("title_loop")
        self.assertEqual(audio.shape[0], 10 * SR)
        self.assertLess(float(np.max(np.abs(audio[:2]))), 0.02)
        self.assertLess(float(np.max(np.abs(audio[-2000:]))), 1e-3)
        # Looping the buffer does not step from a hot sample into another.
        jump = float(np.max(np.abs(audio[0] - audio[-1])))
        self.assertLess(jump, 0.02)

    def test_beam_wraps_without_a_click(self):
        audio = render_preset("beam_hum")
        jump = float(np.max(np.abs(audio[0] - audio[-1])))
        self.assertLess(jump, 1e-5)
        self.assertGreater(audio.shape[0], 5 * SR)

    def test_loop_length_trims(self):
        audio = render_preset("sting", loop_length=2.0)
        self.assertEqual(audio.shape[0], 2 * SR)

    def test_renders_are_deterministic(self):
        a = render_preset("blips")
        b = render_preset("blips")
        self.assertTrue(np.array_equal(a, b))


class KitTests(unittest.TestCase):
    def test_phrase_seconds(self):
        self.assertEqual(phrase_seconds(92, 1.5), 10.0)
        self.assertEqual(phrase_seconds(92, 1), 15.0)
        with self.assertRaises(ValueError):
            phrase_seconds(0, 1)
        with self.assertRaises(ValueError):
            note_pc("H")

    def test_synthesize_contract(self):
        audio = synthesize()
        self.assertEqual(audio.shape, (10 * SR, 2))
        self.assertEqual(audio.dtype, np.float32)
        self.assertLessEqual(float(np.max(np.abs(audio))), 0.9)
        self.assertFalse(np.allclose(audio, synthesize(key="E")))
        self.assertFalse(np.allclose(audio, synthesize(mode="major")))
        slow = synthesize(bpm=92, speed=1)
        self.assertEqual(slow.shape[0], 15 * SR)

    def test_fit_trims_and_pads(self):
        audio = synthesize()
        short = fit(audio, 1.0)
        self.assertEqual(short.shape[0], SR)
        self.assertLess(float(np.max(np.abs(short[-10:]))), float(np.max(np.abs(short[: SR // 2]))))
        long = fit(audio, 11.0)
        self.assertEqual(long.shape[0], 11 * SR)
        self.assertTrue(np.all(long[audio.shape[0] :] == 0))


class CliTests(unittest.TestCase):
    def test_render_wav_ogg_and_preset_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            wav = folder / "out.wav"
            ogg = folder / "beam.ogg"
            subprocess.check_call(
                [sys.executable, "-m", "chip", "render", str(ROOT / "examples" / "score.mml"), "-o", str(wav)],
                cwd=ROOT,
            )
            subprocess.check_call(
                [sys.executable, "-m", "chip", "preset", "beam_hum", "-o", str(ogg), "--loop-length", "1.0"],
                cwd=ROOT,
            )
            self.assertEqual(wav.read_bytes()[:4], b"RIFF")
            self.assertEqual(ogg.read_bytes()[:4], b"OggS")
            listed = subprocess.check_output([sys.executable, "-m", "chip", "presets"], cwd=ROOT, text=True)
            self.assertEqual(listed.split(), PRESETS)
            tables = subprocess.check_output([sys.executable, "-m", "chip", "wavetables"], cwd=ROOT, text=True)
            self.assertIn("organ", tables)
            bad = subprocess.run(
                [sys.executable, "-m", "chip", "preset", "nope", "-o", str(wav)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(bad.returncode, 2)
            self.assertIn("unknown preset", bad.stderr)


def _flatness(x: np.ndarray) -> float:
    mag = np.abs(np.fft.rfft(x * np.hanning(x.size))) + 1e-12
    return float(np.exp(np.mean(np.log(mag))) / np.mean(mag))


if __name__ == "__main__":
    unittest.main()
