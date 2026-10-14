import {alignmentDuration, resolveLyrics} from "./lyrics";
import type {Alignment, ResolvedTimeline, TimelineConfig} from "./types";

export function resolveTimeline(
  config: TimelineConfig,
  alignment: Alignment,
): ResolvedTimeline {
  const lines = resolveLyrics(alignment, config.lyrics, config.accentWords);
  const scenesEnd = config.scenes.reduce((max, scene) => Math.max(max, scene.out), 0);
  const natural = alignmentDuration(alignment, lines, scenesEnd);
  // durationSec extends the picture past the song (a silent title, for example).
  // Omitting it keeps the song / lyric / scene length.
  const durationSec = config.durationSec === undefined ? natural : config.durationSec;
  const durationInFrames = Math.max(1, Math.ceil(durationSec * config.fps - 1e-6));
  return {
    song: config.song,
    fps: 30,
    width: 1920,
    height: 1080,
    durationSec,
    durationInFrames,
    timecodeOffsetSec: config.timecodeOffsetSec,
    songStartSec: config.songStartSec,
    colors: config.colors,
    fonts: config.fonts,
    accentWords: config.accentWords.map((word) => word.toLowerCase()),
    holdSec: config.lyrics.holdSec,
    scenes: config.scenes,
    lines,
  };
}
