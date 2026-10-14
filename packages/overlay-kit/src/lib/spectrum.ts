/** Resting spectrum once playback has passed the end of the song. */
export function silentSpectrum(sampleCount: number): number[] {
  return new Array(sampleCount).fill(0);
}

/**
 * Use the live audio spectrum during the song, and silence after it.
 * `live` is not called once `timeSec` reaches `audioDurationSec`.
 */
export function spectrumAtTime(
  timeSec: number,
  audioDurationSec: number,
  sampleCount: number,
  live: () => number[],
): number[] {
  if (!Number.isFinite(audioDurationSec) || timeSec >= audioDurationSec) {
    return silentSpectrum(sampleCount);
  }
  return live();
}
