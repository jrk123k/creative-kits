"""WAV IO and mixing."""

from __future__ import annotations

import wave

import numpy as np


def peak_normalize(audio: np.ndarray, peak: float = 0.9) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.size == 0:
        return audio
    level = float(np.max(np.abs(audio)))
    if level < 1e-8:
        return audio
    return audio * (peak / level)


def mix_tracks(tracks: list[np.ndarray], gains: list[float]) -> np.ndarray:
    if not tracks:
        return np.zeros(0, dtype=np.float64)
    length = max(len(track) for track in tracks)
    mixed = np.zeros(length, dtype=np.float64)
    for track, gain in zip(tracks, gains):
        mixed[: len(track)] += np.asarray(track, dtype=np.float64) * float(gain)
    return mixed


def write_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim != 1:
        raise ValueError("write_wav expects a mono buffer")
    pcm = np.clip(np.round(samples * 32767.0), -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(pcm.tobytes())


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError(f"{path} is not mono 16-bit PCM")
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float64) / 32767.0
    return audio, sample_rate
