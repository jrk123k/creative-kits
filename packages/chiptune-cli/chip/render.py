"""Turn a parsed score into stereo float audio and write WAV or OGG."""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np

from chip.psg import PEAK, PSG_CLOCK, SR, lfsr_step, midi_to_divider, noise_period, side_gain
from chip.score import CHANNELS, Score, ScoreError, Segment, load_score, parse_score

PRESET_DIR = Path(__file__).resolve().parent / "presets"
RAMP_SEC = 0.0015
XFADE = 256


def list_presets() -> list[str]:
    if not PRESET_DIR.is_dir():
        return []
    return sorted(p.stem for p in PRESET_DIR.glob("*.mml"))


def preset_text(name: str) -> str:
    path = PRESET_DIR / f"{name}.mml"
    if not path.is_file():
        known = ", ".join(list_presets()) or "(none)"
        raise ScoreError(f"unknown preset {name!r} (have {known})")
    return path.read_text(encoding="utf-8")


def render_score(
    source: Score | str | Path,
    *,
    loops: int = 1,
    loop_length: float | None = None,
    seamless: bool | None = None,
    tempo: float | None = None,
    transpose=None,
    sr: int = SR,
    normalize: bool = True,
) -> np.ndarray:
    """Stereo float32 in ``[-1, 1]``, shape ``(n, 2)``, at ``sr`` Hz.

    ``loops`` repeats the region after ``|`` (or the whole score). ``loop_length``
    is a duration in seconds: the loop is repeated to cover it, then trimmed.
    ``seamless`` crossfades the wrap when the edges are still hot; a score can
    request this with ``@seamless``. ``tempo`` replaces the written BPM and
    scales every ``t`` change with it. ``transpose`` maps a MIDI note to a new one.
    """
    score = _as_score(source)
    if loops < 1:
        raise ScoreError("loops must be >= 1")
    if loop_length is not None and loop_length <= 0:
        raise ScoreError("loop-length must be positive")
    if sr < 8000:
        raise ScoreError("sample rate must be at least 8000")

    factor = Fraction(1)
    if tempo is not None:
        if tempo <= 0:
            raise ScoreError("tempo must be positive")
        factor = score.tempo / Fraction(tempo).limit_denominator(1_000_000)

    use_seamless = score.seamless if seamless is None else bool(seamless)
    channels = {c: [_scale_seg(s, factor) for s in score.channels[c]] for c in CHANNELS}
    length = score.length * factor
    loop_start = score.loop_start * factor
    body = length - loop_start
    if body <= 0:
        raise ScoreError("loop region is empty")

    if loop_length is not None:
        intro = float(loop_start)
        need = float(loop_length) - intro
        loops = max(1, math.ceil(need / float(body) - 1e-12))

    expanded = {
        c: _expand(channels[c], loop_start, body, loops) for c in CHANNELS
    }
    total = loop_start + body * loops
    n = int(round(float(total) * sr))
    if n < 1:
        raise ScoreError("render is empty")

    mix = np.zeros((n, 2), dtype=np.float64)
    seeds = {"E": 1, "F": 0x15555}
    for index, letter in enumerate(CHANNELS):
        _mix_channel(
            mix,
            expanded[letter],
            score,
            sr,
            transpose,
            use_seamless,
            loop_start,
            total,
            seeds.get(letter, 1 + index),
        )

    if loop_length is not None:
        target = int(round(float(loop_length) * sr))
        if mix.shape[0] < target:
            mix = np.pad(mix, ((0, target - mix.shape[0]), (0, 0)))
        else:
            mix = np.array(mix[:target], copy=True)
        if not use_seamless:
            _fade_tail(mix, sr)

    if use_seamless:
        mix = _loop_crossfade(mix, XFADE)

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if normalize and peak > PEAK:
        mix *= PEAK / peak
    return mix.astype(np.float32)


def render_preset(name: str, **kwargs) -> np.ndarray:
    return render_score(preset_text(name), **kwargs)


def write_audio(path: str | Path, audio: np.ndarray, sr: int = SR) -> Path:
    """Write stereo float audio to ``.wav`` (16-bit) or ``.ogg`` (Vorbis)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    if data.ndim != 2 or data.shape[1] != 2:
        raise ScoreError("audio must be stereo, shape (n, 2)")
    ext = dest.suffix.lower()
    if ext == ".wav":
        _write_wav(dest, data, sr)
    elif ext == ".ogg":
        _write_ogg(dest, data, sr)
    else:
        raise ScoreError(f"unsupported output {dest.suffix!r} (use .wav or .ogg)")
    return dest


def _as_score(source: Score | str | Path) -> Score:
    if isinstance(source, Score):
        return source
    if isinstance(source, Path):
        return load_score(source)
    text = str(source)
    # A score body can be long; only short single-line strings are file paths.
    if "\n" not in text and len(text) < 4096 and Path(text).is_file():
        return load_score(text)
    return parse_score(text)


def _scale_seg(seg: Segment, factor: Fraction) -> Segment:
    if factor == 1:
        return seg
    return replace(
        seg,
        t0=seg.t0 * factor,
        t1=seg.t1 * factor,
        note_end=seg.note_end * factor,
    )


def _expand(segments: list[Segment], loop_start: Fraction, body: Fraction, loops: int) -> list[Segment]:
    out: list[Segment] = []
    for seg in segments:
        if seg.note_end <= loop_start:
            out.append(seg)
            continue
        if seg.t0 >= loop_start:
            piece = seg
        else:
            # A note sitting on the loop point plays its head once, then the tail repeats.
            head = replace(seg, t1=min(seg.t1, loop_start), note_end=loop_start)
            if head.note_end > head.t0:
                out.append(head)
            piece = replace(seg, t0=loop_start, t1=max(loop_start, seg.t1))
        for k in range(loops):
            delta = body * k
            out.append(replace(piece, t0=piece.t0 + delta, t1=piece.t1 + delta, note_end=piece.note_end + delta))
    out.sort(key=lambda s: (s.t0, s.note_end))
    return out


def _mix_channel(mix, segments, score: Score, sr, transpose, seamless, loop_start, total, seed: int) -> None:
    n = mix.shape[0]
    sounding = [s for s in segments if s.sounding and s.vol > 0]
    starts_at_loop = bool(sounding) and sounding[0].t0 <= loop_start
    reaches_end = bool(sounding) and sounding[-1].t1 >= total
    phase = 0.0
    lfo_phase = 0.0
    clock = 0.0
    noise_seed = seed & 0x3FFFF or 1
    period = noise_period(16)
    prev_end = 0

    indexed = _sample_spans(segments, sr, n)
    for seg, (a, b) in zip(segments, indexed):
        if seg.noise:
            gap = a - prev_end
            if gap > 0:
                noise_seed, clock = _advance_noise(gap, sr, period, noise_seed, clock)
            period = noise_period(seg.noise_reg)
        if b <= a or seg.vol <= 0:
            prev_end = max(prev_end, a)
            continue
        prev = _previous_sounding(segments, seg)
        nxt = _next_sounding(segments, seg)
        attack = not (prev is not None and prev.t1 == seg.t0)
        release = not (nxt is not None and seg.t1 == nxt.t0)
        if seamless and starts_at_loop and reaches_end:
            if seg.t0 <= loop_start:
                attack = False
            if seg.t1 >= total:
                release = False
        count = b - a
        if seg.noise:
            sig, noise_seed, clock = _noise_block(count, sr, period, noise_seed, clock)
        else:
            midi = seg.midi if seg.midi is not None else 60
            if transpose is not None:
                midi = int(transpose(midi))
            divider = midi_to_divider(midi)
            wave = score.waves[seg.wave]
            if seg.lfo_mode:
                sig, phase, lfo_phase = _render_lfo(
                    count, sr, divider, wave, phase,
                    score.waves[seg.lfo_wave], lfo_phase,
                    seg.lfo_mode, seg.lfo_rate, seg.lfo_div,
                )
            else:
                sig, phase = _render_wave(count, sr, divider, wave, phase)
        _apply_ramp(sig, sr, attack, release)
        left = side_gain(seg.vol, seg.pan_l, score.master_l)
        right = side_gain(seg.vol, seg.pan_r, score.master_r)
        mix[a:b, 0] += sig * left
        mix[a:b, 1] += sig * right
        prev_end = b


def _previous_sounding(segments: list[Segment], seg: Segment) -> Segment | None:
    prev = None
    for other in segments:
        if other is seg:
            break
        if other.sounding:
            prev = other
    return prev


def _next_sounding(segments: list[Segment], seg: Segment) -> Segment | None:
    seen = False
    for other in segments:
        if other is seg:
            seen = True
            continue
        if seen and other.sounding:
            return other
    return None


def _sample_spans(segments: list[Segment], sr: int, n: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    last_end = 0
    for seg in segments:
        a = int(round(float(seg.t0) * sr))
        b = int(round(float(seg.t1) * sr))
        a = min(max(0, a), n)
        b = min(max(0, b), n)
        if spans and seg.sounding:
            prev = segments[len(spans) - 1]
            if prev.sounding and prev.t1 == seg.t0:
                a = last_end
                b = max(a, b)
        spans.append((a, b))
        if seg.sounding:
            last_end = b
    return spans


def _render_wave(count: int, sr: int, divider: int, wave: np.ndarray, phase: float):
    step = (PSG_CLOCK / divider) / sr
    pos = phase + np.arange(count, dtype=np.float64) * step
    idx = np.floor(pos).astype(np.int64) & 31
    sig = (wave[idx].astype(np.float64) - 16.0) / 16.0
    return sig, float(np.fmod(phase + count * step, 32.0))


def _render_lfo(count, sr, divider, wave, phase, lfo_wave, lfo_phase, mode, rate, div):
    mod_step = (PSG_CLOCK / (max(1, div) * max(1, rate))) / sr
    k = np.arange(count, dtype=np.float64)
    mod_idx = np.floor(lfo_phase + k * mod_step).astype(np.int64) & 31
    signed = lfo_wave[mod_idx].astype(np.int32) - 16
    freq = divider + signed * (1 << ((mode - 1) * 2))
    np.clip(freq, 1, 4095, out=freq)
    step = (PSG_CLOCK / freq) / sr
    pos = phase + np.cumsum(step) - step
    idx = np.floor(pos).astype(np.int64) & 31
    sig = (wave[idx].astype(np.float64) - 16.0) / 16.0
    new_phase = float(np.fmod(phase + float(np.sum(step)), 32.0))
    new_lfo = float(np.fmod(lfo_phase + count * mod_step, 32.0))
    return sig, new_phase, new_lfo


def _noise_block(count: int, sr: int, period: int, seed: int, clock: float):
    clocks = clock + np.arange(count, dtype=np.float64) * (PSG_CLOCK / sr)
    steps = np.floor(clocks / period).astype(np.int64)
    base = int(steps[0])
    rel = steps - base
    values = np.empty(int(rel[-1]) + 1, dtype=np.float64)
    state = seed & 0x3FFFF or 1
    for i in range(values.size):
        values[i] = 0.9375 if (state & 1) else -1.0
        state = lfsr_step(state)
    next_clock = clock + count * (PSG_CLOCK / sr)
    next_step = int(math.floor(next_clock / period))
    # ``state`` is the seed at ``base + len(values)``. Rewind is unnecessary:
    # the next block starts at next_step, which equals base + len(values)
    # or one less when the next sample lands on the same step. Recompute.
    state = seed & 0x3FFFF or 1
    for _ in range(max(0, next_step - base)):
        state = lfsr_step(state)
    return values[rel], state, next_clock


def _advance_noise(count: int, sr: int, period: int, seed: int, clock: float):
    next_clock = clock + count * (PSG_CLOCK / sr)
    steps = int(math.floor(next_clock / period) - math.floor(clock / period))
    state = seed & 0x3FFFF or 1
    for _ in range(max(0, steps)):
        state = lfsr_step(state)
    return state, next_clock


def _apply_ramp(sig: np.ndarray, sr: int, attack: bool, release: bool) -> None:
    n = sig.size
    if n < 2 or not (attack or release):
        return
    ramp = min(int(RAMP_SEC * sr), max(1, n // 4))
    if attack and release and n < ramp * 2:
        ramp = max(1, n // 2)
    if attack and ramp:
        sig[:ramp] *= np.linspace(0.0, 1.0, ramp, endpoint=False)
    if release and ramp:
        sig[-ramp:] *= np.linspace(1.0, 0.0, ramp, endpoint=False)


def _fade_tail(mix: np.ndarray, sr: int) -> None:
    fade = min(mix.shape[0] // 2, int(0.008 * sr))
    if fade < 2:
        return
    if float(np.max(np.abs(mix[-fade:]))) < 0.02:
        return
    ramp = np.linspace(1.0, 0.0, fade, endpoint=False)[:, None]
    mix[-fade:] *= ramp


def _loop_crossfade(mix: np.ndarray, xf: int) -> np.ndarray:
    n = mix.shape[0]
    if n < xf * 4:
        return mix
    if float(np.max(np.abs(mix[:2]))) < 0.02 and float(np.max(np.abs(mix[-32:]))) < 0.02:
        return mix
    out = np.array(mix, copy=True)
    t = np.linspace(0.0, 1.0, xf)[:, None]
    # Roll so the last blended frame is the first frame of the buffer.
    target = np.roll(out[:xf], -1, axis=0)
    out[-xf:] = out[-xf:] * (1.0 - t) + target * t
    return out


def _write_wav(dest: Path, data: np.ndarray, sr: int) -> None:
    import soundfile as sf

    sf.write(dest, data, sr, subtype="PCM_16")


def _write_ogg(dest: Path, data: np.ndarray, sr: int) -> None:
    import soundfile as sf

    try:
        sf.write(dest, data, sr, format="OGG", subtype="VORBIS")
        return
    except Exception:
        pass
    if shutil.which("ffmpeg") is None and shutil.which("oggenc") is None:
        raise ScoreError("OGG needs soundfile Vorbis support, ffmpeg, or oggenc")
    wav = dest.with_suffix(".tmp.wav")
    try:
        sf.write(wav, data, sr, subtype="PCM_16")
        if shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "5", str(dest)],
                check=True,
            )
        else:
            subprocess.run(["oggenc", "-q", "5", "-o", str(dest), str(wav)], check=True)
    finally:
        wav.unlink(missing_ok=True)
