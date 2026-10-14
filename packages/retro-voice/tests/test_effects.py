import numpy as np

from retro_voice.effects import apply_chain, bitcrush, sample_and_hold, sid_filter
from retro_voice.controls import EffectChain


def test_bitcrush_and_sample_hold():
    audio = np.linspace(-1, 1, 32)
    crushed = bitcrush(audio, 3)
    # 3 bits -> 7 levels, values sit on that grid.
    levels = np.unique(np.round(crushed, 5))
    assert len(levels) <= 8
    held = sample_and_hold(np.array([0.2, 0.8, -0.4, 0.1, 0.5]), 2)
    assert np.allclose(held, [0.2, 0.2, -0.4, -0.4, 0.5])


def test_lowpass_removes_high_harmonics():
    sr = 22050
    t = np.arange(sr) / sr
    noise = np.random.default_rng(0).standard_normal(sr)
    filtered = sid_filter(noise, sr, cutoff=400, resonance=0.2, mode="lp")
    dry = np.abs(np.fft.rfft(noise))
    wet = np.abs(np.fft.rfft(filtered))
    freqs = np.fft.rfftfreq(sr, 1 / sr)
    high = freqs > 4000
    assert wet[high].sum() < dry[high].sum() * 0.35
    # Resonance should change a sine swept near the cutoff.
    tone = np.sin(2 * np.pi * 1000 * t)
    plain = sid_filter(tone, sr, 1000, 0.05, "lp")
    sharp = sid_filter(tone, sr, 1000, 0.9, "lp")
    assert not np.allclose(plain, sharp)
    del tone


def test_chain_keeps_length_and_can_bypass():
    sr = 8000
    audio = np.sin(2 * np.pi * 220 * np.arange(sr) / sr) * 0.5
    dry = apply_chain(audio, sr, EffectChain())
    assert len(dry) == len(audio)
    assert np.allclose(dry, audio)
    wet = apply_chain(
        audio,
        sr,
        EffectChain(bitcrush=5, downsample=4, filter_mode="bp", cutoff=800, resonance=0.7, ring_hz=40, ring_mix=0.5, chorus_mix=0.3),
    )
    assert len(wet) == len(audio)
    assert not np.allclose(wet, audio)
