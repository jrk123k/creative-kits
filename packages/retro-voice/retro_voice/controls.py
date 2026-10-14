"""SAM-style voice knobs and the 80s effects chain settings.

Pitch, speed, mouth, and throat use the same 0–255 ranges as the classic
Software Automatic Mouth manual. The mapping onto this synthesizer is ours:

- pitch 64 is the center. Each step is a quarter semitone.
- speed 72 is the center. Larger values speak more slowly.
- mouth 128 is the center. Larger values raise the upper formants (brighter).
- throat 128 is the center. Larger values raise the first formant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


def _byte(name: str, value: int) -> int:
    value = int(value)
    if value < 0 or value > 255:
        raise ValueError(f"{name} must be an integer from 0 to 255 (got {value})")
    return value


@dataclass(frozen=True)
class VoiceControls:
    pitch: int = 64
    speed: int = 72
    mouth: int = 128
    throat: int = 128

    def validated(self) -> "VoiceControls":
        return VoiceControls(
            pitch=_byte("pitch", self.pitch),
            speed=_byte("speed", self.speed),
            mouth=_byte("mouth", self.mouth),
            throat=_byte("throat", self.throat),
        )

    def pitch_scale(self) -> float:
        semitones = (self.pitch - 64) * 0.25
        return 2.0 ** (semitones / 12.0)

    def speed_scale(self) -> float:
        # SAM's SPEED counter: a higher number holds each frame longer.
        return max(0.05, self.speed / 72.0)


VOICE_PRESETS: dict[str, VoiceControls] = {
    "sam": VoiceControls(64, 72, 128, 128),
    "lead": VoiceControls(72, 70, 186, 108),
    "harmony": VoiceControls(52, 86, 86, 172),
    "deep": VoiceControls(40, 88, 78, 64),
    "bright": VoiceControls(96, 66, 196, 154),
}


def voice_preset(name: str) -> VoiceControls:
    key = name.lower()
    if key not in VOICE_PRESETS:
        known = ", ".join(sorted(VOICE_PRESETS))
        raise ValueError(f"unknown voice preset {name!r} (expected {known})")
    return VOICE_PRESETS[key]


@dataclass(frozen=True)
class EffectChain:
    bitcrush: int = 0
    downsample: int = 1
    filter_mode: str = "off"
    cutoff: float = 2400.0
    resonance: float = 0.55
    ring_hz: float = 0.0
    ring_mix: float = 0.0
    chorus_mix: float = 0.0
    chorus_rate: float = 0.55
    chorus_depth_ms: float = 6.0
    chorus_delay_ms: float = 18.0

    def validated(self) -> "EffectChain":
        mode = self.filter_mode.lower()
        if mode not in {"off", "lp", "bp", "hp"}:
            raise ValueError("filter must be off, lp, bp, or hp")
        bits = int(self.bitcrush)
        if bits < 0 or bits > 16:
            raise ValueError("bitcrush must be 0 (off) through 16")
        down = int(self.downsample)
        if down < 1 or down > 32:
            raise ValueError("downsample must be from 1 to 32")
        res = float(self.resonance)
        if res < 0 or res > 0.98:
            raise ValueError("resonance must be from 0 to 0.98")
        for name, value in (
            ("ring mix", self.ring_mix),
            ("chorus mix", self.chorus_mix),
        ):
            if value < 0 or value > 1:
                raise ValueError(f"{name} must be from 0 to 1")
        if self.cutoff <= 0:
            raise ValueError("cutoff must be positive")
        return replace(
            self,
            bitcrush=bits,
            downsample=down,
            filter_mode=mode,
            cutoff=float(self.cutoff),
            resonance=res,
            ring_hz=float(self.ring_hz),
            ring_mix=float(self.ring_mix),
            chorus_mix=float(self.chorus_mix),
            chorus_rate=float(self.chorus_rate),
            chorus_depth_ms=float(self.chorus_depth_ms),
            chorus_delay_ms=float(self.chorus_delay_ms),
        )


EFFECT_PRESETS: dict[str, EffectChain] = {
    "off": EffectChain(),
    "sam": EffectChain(
        bitcrush=8,
        downsample=2,
        filter_mode="bp",
        cutoff=1500,
        resonance=0.58,
        chorus_mix=0.0,
    ),
    "c64": EffectChain(
        bitcrush=8,
        downsample=2,
        filter_mode="lp",
        cutoff=2600,
        resonance=0.72,
        chorus_mix=0.18,
        chorus_rate=0.45,
        chorus_depth_ms=7.0,
    ),
}


def effect_preset(name: str) -> EffectChain:
    key = name.lower()
    if key not in EFFECT_PRESETS:
        known = ", ".join(sorted(EFFECT_PRESETS))
        raise ValueError(f"unknown effects preset {name!r} (expected {known})")
    return EFFECT_PRESETS[key]
