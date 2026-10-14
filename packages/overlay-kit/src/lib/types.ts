export const LAYER_KEYS = [
  "brackets",
  "location",
  "rec",
  "lyrics",
  "status",
  "equalizer",
] as const;

export type LayerKey = (typeof LAYER_KEYS)[number];

export type Layers = Record<LayerKey, boolean>;

export type StatusTone = "green" | "cyan" | "red" | "grey";

export type StatusLine = {
  label: string;
  value: string;
  tone: StatusTone;
};

export type LocationLabel = {
  kicker: string;
  title: string;
  subtitle: string;
};

export type TransitionKind = "fade" | "glitch";

export type Scene = {
  id: string;
  in: number;
  out: number;
  transition: TransitionKind;
  transitionFrames: number;
  layers: Layers;
  location: LocationLabel;
  camera: string;
  status: StatusLine[];
};

export type Colors = {
  cyan: string;
  red: string;
  green: string;
  white: string;
  grey: string;
  dim: string;
  box: string;
};

export type Fonts = {
  hud: string;
  lyrics: string;
};

export type LyricOverride = {
  start: number;
  end: number;
  text: string;
};

export type LyricOptions = {
  pauseGapSec: number;
  maxLineChars: number;
  maxWords: number;
  holdSec: number;
  overrides: LyricOverride[];
};

export type TimelineConfig = {
  version: 1;
  song: string;
  alignment: string;
  fps: 30;
  width: 1920;
  height: 1080;
  /** Composition length. Omit to use the song, lyric, and scene end. */
  durationSec?: number;
  timecodeOffsetSec: number;
  songStartSec: number;
  colors: Colors;
  fonts: Fonts;
  accentWords: string[];
  lyrics: LyricOptions;
  scenes: Scene[];
};

export type AlignedWord = {
  word: string;
  start: number;
  end: number;
  confidence?: number;
};

export type Alignment = {
  duration_sec?: number;
  words?: AlignedWord[];
  segments?: Array<{
    text?: string;
    start?: number;
    end?: number;
    words?: AlignedWord[];
  }>;
};

export type LyricWord = {
  text: string;
  start: number;
  end: number;
  accent: boolean;
};

export type LyricLine = {
  start: number;
  end: number;
  words: LyricWord[];
};

export type ResolvedTimeline = {
  song: string;
  fps: 30;
  width: 1920;
  height: 1080;
  durationSec: number;
  durationInFrames: number;
  timecodeOffsetSec: number;
  songStartSec: number;
  colors: Colors;
  fonts: Fonts;
  accentWords: string[];
  holdSec: number;
  scenes: Scene[];
  lines: LyricLine[];
};

export class TimelineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TimelineError";
  }
}
