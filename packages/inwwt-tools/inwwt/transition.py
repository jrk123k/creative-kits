"""Animated era transition: CRT, then pixelate, then C64 dither, then the reverse.

Clip A degrades. At the bottom of the curve the picture is a C64-resolution
dither and the source switches to clip B, which climbs back out to a clean frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from inwwt.crt import CRTCache, CRTParams, apply_crt
from inwwt.curves import apply_curve
from inwwt.looks import LookParams, collapse
from inwwt.video import FrameReader, FrameWriter, has_audio


@dataclass
class TransitionConfig:
    duration: float = 8.0
    fps: float = 24.0
    width: int = 1280
    height: int = 720
    curve: str = "smoothstep"
    # Stage boundaries as fractions of the eased timeline. Strictly increasing, last < 1.
    crt_in_end: float = 0.18
    pixel_end: float = 0.34
    dither_end: float = 0.46
    hold_end: float = 0.54
    undither_end: float = 0.66
    unpixel_end: float = 0.82
    look: LookParams | None = None
    crt: CRTParams | None = None
    crf: int = 20
    preset: str = "medium"

    def __post_init__(self) -> None:
        bounds = [
            self.crt_in_end,
            self.pixel_end,
            self.dither_end,
            self.hold_end,
            self.undither_end,
            self.unpixel_end,
        ]
        if any(b <= 0 or b >= 1 for b in bounds):
            raise ValueError("stage boundaries must sit strictly between 0 and 1")
        if bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
            raise ValueError("stage boundaries must be strictly increasing")
        if self.duration <= 0 or self.fps <= 0:
            raise ValueError("duration and fps must be positive")

    @property
    def frame_count(self) -> int:
        return max(1, int(round(self.duration * self.fps)))

    def look_params(self) -> LookParams:
        return self.look or LookParams()

    def crt_params(self) -> CRTParams:
        return self.crt or CRTParams()


@dataclass
class StageState:
    source: str  # "a" or "b"
    crt: float
    pixel: float
    dither: float


def _ramp(t: float, start: float, end: float) -> float:
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    return (t - start) / (end - start)


def stage_state(t: float, cfg: TransitionConfig) -> StageState:
    """``t`` is raw 0..1 time. The curve is applied inside."""
    u = apply_curve(t, cfg.curve)
    a, b, c = cfg.crt_in_end, cfg.pixel_end, cfg.dither_end
    d, e, f = cfg.hold_end, cfg.undither_end, cfg.unpixel_end
    mid = 0.5 * (c + d)
    source = "a" if u < mid else "b"

    if u < a:
        crt = _ramp(u, 0.0, a)
    elif u < f:
        crt = 1.0
    else:
        crt = 1.0 - _ramp(u, f, 1.0)

    if u < a:
        pixel = 0.0
    elif u < b:
        pixel = _ramp(u, a, b)
    elif u < e:
        pixel = 1.0
    elif u < f:
        pixel = 1.0 - _ramp(u, e, f)
    else:
        pixel = 0.0

    if u < b:
        dither = 0.0
    elif u < c:
        dither = _ramp(u, b, c)
    elif u < d:
        dither = 1.0
    elif u < e:
        dither = 1.0 - _ramp(u, d, e)
    else:
        dither = 0.0

    return StageState(source, crt, pixel, dither)


def render_frame(frame_a, frame_b, t: float, cfg: TransitionConfig, cache: CRTCache | None):
    state = stage_state(t, cfg)
    frame = frame_a if state.source == "a" else frame_b
    if state.crt > 1e-6:
        frame, cache = apply_crt(frame, state.crt, cfg.crt_params(), cache)
    if state.pixel > 1e-6 or state.dither > 1e-6:
        frame = collapse(frame, state.pixel, state.dither, cfg.look_params())
    return frame, cache


def render_transition(path_a: str, path_b: str, output: str, cfg: TransitionConfig) -> None:
    n = cfg.frame_count
    reader_a = FrameReader(path_a, cfg.width, cfg.height, cfg.fps, n)
    reader_b = FrameReader(path_b, cfg.width, cfg.height, cfg.fps, n)
    audio = has_audio(path_a) and has_audio(path_b)
    extra: list[str] = []
    filt = None
    maps = ["0:v"]
    if audio:
        # stage_state flips A→B when eased time crosses the middle of the hold.
        # Invert the curve so the audio cut lands on that same frame.
        mid = 0.5 * (cfg.dither_end + cfg.hold_end)
        switch = _eased_time_at(mid, cfg.curve) * cfg.duration
        rest = max(0.01, cfg.duration - switch)
        extra = ["-stream_loop", "-1", "-i", path_a, "-stream_loop", "-1", "-i", path_b]
        filt = (
            f"[1:a]atrim=0:{switch:.4f},asetpts=PTS-STARTPTS[a0];"
            f"[2:a]atrim=0:{rest:.4f},asetpts=PTS-STARTPTS[a1];"
            f"[a0][a1]concat=n=2:v=0:a=1[aout]"
        )
        maps = ["0:v", "[aout]"]
    writer = FrameWriter(
        output,
        cfg.width,
        cfg.height,
        cfg.fps,
        crf=cfg.crf,
        preset=cfg.preset,
        extra_inputs=extra,
        filter_complex=filt,
        maps=maps,
        audio=audio,
    )
    cache: CRTCache | None = None
    try:
        for i in range(n):
            t = 0.0 if n == 1 else i / (n - 1)
            frame, cache = render_frame(reader_a.read(), reader_b.read(), t, cfg, cache)
            writer.write(frame)
            if i % max(1, int(cfg.fps)) == 0:
                print(f"transition {i + 1}/{n}", flush=True)
    finally:
        reader_a.close()
        reader_b.close()
        writer.close()


def _eased_time_at(target_eased: float, curve: str) -> float:
    """Invert the easing so audio can switch with the picture. Binary search."""
    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if apply_curve(mid, curve) < target_eased:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
