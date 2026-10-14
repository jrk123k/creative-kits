import tempfile
import unittest
from pathlib import Path

import numpy as np

from inwwt.compositor import CompositeConfig, Panel, build_filter_complex, layout_rects, load_config
from inwwt.video import run_ffmpeg, video_size


def _cfg(layout, n, **kwargs):
    panels = [Panel(src=f"p{i}.mp4", label=f"E{i}", look="none") for i in range(n)]
    return CompositeConfig(panels=panels, width=1920, height=1080, duration=1.0, layout=layout, divider_px=8, **kwargs)


class GeometryTests(unittest.TestCase):
    def _assert_tiled(self, cfg):
        rects = layout_rects(cfg)
        self.assertEqual(len(rects), len(cfg.panels))
        canvas = np.zeros((cfg.height, cfg.width), dtype=np.int32)
        for i, rect in enumerate(rects, start=1):
            self.assertGreater(rect.w, 0)
            self.assertGreater(rect.h, 0)
            view = canvas[rect.y : rect.y + rect.h, rect.x : rect.x + rect.w]
            self.assertTrue(np.all(view == 0), "panels overlap")
            view[:] = i
        # Every non-panel pixel is part of a divider gap, and the gaps are thin.
        empty = canvas == 0
        self.assertEqual(int(empty.sum()), cfg.width * cfg.height - sum(r.w * r.h for r in rects))

    def test_splits_and_triptych_cover_with_gaps(self):
        self._assert_tiled(_cfg("split-vertical", 2))
        self._assert_tiled(_cfg("split-horizontal", 2))
        self._assert_tiled(_cfg("triptych", 3))
        vertical = layout_rects(_cfg("split-vertical", 2))
        self.assertEqual(vertical[0].x, 0)
        self.assertEqual(vertical[1].x, vertical[0].w + 8)
        self.assertEqual(vertical[0].w + vertical[1].w + 8, 1920)

    def test_one_plus_two_sides(self):
        for side in ("left", "right", "top", "bottom"):
            cfg = _cfg("one-plus-two", 3, primary=side, primary_ratio=0.6)
            self._assert_tiled(cfg)
            rects = layout_rects(cfg)
            self.assertGreater(rects[0].w * rects[0].h, rects[1].w * rects[1].h)

    def test_wrong_panel_count(self):
        with self.assertRaises(ValueError):
            layout_rects(_cfg("triptych", 2))


class GraphTests(unittest.TestCase):
    def test_yaml_and_c64_graph(self):
        text = """
output: {width: 640, height: 360, fps: 12, duration: 1}
layout: split-vertical
divider: {px: 4, color: "101820"}
labels: {show: true, size: 20}
audio: {from: none}
panels:
  - {src: a.mp4, label: "1984:", look: c64, dither: floyd, palette: pepto}
  - {src: b.mp4, label: "2026", look: none}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.yaml"
            path.write_text(text, encoding="utf-8")
            cfg = load_config(path)
        self.assertEqual(cfg.layout, "split-vertical")
        self.assertEqual(cfg.audio_from, "none")
        graph = build_filter_complex(cfg, {"pepto": 2}, fontfile="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        self.assertIn("paletteuse=dither=floyd_steinberg", graph)
        self.assertIn("overlay=x=0:y=0", graph)
        self.assertIn("1984\\:", graph)
        self.assertIn("[v]", graph)

    def test_crt_look_is_in_the_graph(self):
        cfg = _cfg("triptych", 3)
        cfg.panels[2].look = "crt"
        graph = build_filter_complex(cfg, {}, fontfile="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        self.assertIn("lenscorrection", graph)
        self.assertIn("geq=", graph)
        self.assertIn("drawtext=", graph)


class FFmpegIntegrationTests(unittest.TestCase):
    def test_split_with_c64_look_and_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name, color, tone in (("a", "0xCC4422", 220), ("b", "0x226688", 440)):
                run_ffmpeg(
                    [
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={color}:s=160x90:r=12:d=0.6",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={tone}:sample_rate=48000:duration=0.6",
                        "-shortest",
                        "-pix_fmt",
                        "yuv420p",
                        str(tmp / f"{name}.mp4"),
                    ]
                )
            yaml = tmp / "layout.yaml"
            yaml.write_text(
                f"""
output: {{width: 320, height: 180, fps: 12, duration: 0.5, crf: 28, preset: veryfast}}
layout: split-horizontal
divider: {{px: 4, color: "000000"}}
labels: {{show: true, size: 16}}
audio: {{from: panel, index: 1}}
panels:
  - {{src: {tmp / "a.mp4"}, label: "1984", look: c64, dither: bayer, palette: pepto}}
  - {{src: {tmp / "b.mp4"}, label: "2026", look: crt}}
""",
                encoding="utf-8",
            )
            cfg = load_config(yaml)
            out = tmp / "out.mp4"
            from inwwt.compositor import render_composite

            render_composite(cfg, str(out))
            self.assertEqual(video_size(out), (320, 180))
            from inwwt.video import has_audio

            self.assertTrue(has_audio(out))
            self.assertLess(out.stat().st_size, 2_000_000)


if __name__ == "__main__":
    unittest.main()
