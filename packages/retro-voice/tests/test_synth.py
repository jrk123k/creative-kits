import numpy as np

from retro_voice.controls import VoiceControls, effect_preset
from retro_voice.phonemes import shape_formants
from retro_voice.pitch import estimate_f0
from retro_voice.speak import render_speech
from retro_voice.synth import SR_DEFAULT


def _band_ratio(audio: np.ndarray, sample_rate: int) -> float:
    spec = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    freqs = np.fft.rfftfreq(len(audio), 1 / sample_rate)
    low = np.sum(spec[(freqs > 80) & (freqs < 1000)] ** 2)
    high = np.sum(spec[freqs > 1600] ** 2)
    return high / (low + 1e-12)


def test_mouth_and_throat_move_formants():
    dark = shape_formants(730, 1090, 2440, mouth=16, throat=16)
    bright = shape_formants(730, 1090, 2440, mouth=240, throat=240)
    assert bright[1] > dark[1] * 1.5
    assert bright[0] > dark[0] * 1.4
    neutral = shape_formants(730, 1090, 2440, 128, 128)
    assert abs(neutral[0] - 730) < 1 and abs(neutral[1] - 1090) < 1


def test_speech_speed_and_mouth_are_audible():
    slow = render_speech("hello", VoiceControls(speed=144), effect_preset("off"), seed=1)
    fast = render_speech("hello", VoiceControls(speed=36), effect_preset("off"), seed=1)
    assert len(slow) > len(fast) * 1.6
    dark = render_speech("la", VoiceControls(mouth=16), effect_preset("off"), seed=2)
    bright = render_speech("la", VoiceControls(mouth=240), effect_preset("off"), seed=2)
    assert _band_ratio(bright, SR_DEFAULT) > _band_ratio(dark, SR_DEFAULT) * 2


def test_pitch_knob_raises_speech():
    low = render_speech("la", VoiceControls(pitch=40), effect_preset("off"), seed=3)
    high = render_speech("la", VoiceControls(pitch=112), effect_preset("off"), seed=3)
    low_f0 = estimate_f0(low[len(low) // 4 : len(low) // 2], SR_DEFAULT)
    high_f0 = estimate_f0(high[len(high) // 4 : len(high) // 2], SR_DEFAULT, fmax=1000)
    assert high_f0 > low_f0 * 1.7
