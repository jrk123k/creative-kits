import {parse} from "yaml";
import {
  LAYER_KEYS,
  TimelineError,
  type Colors,
  type Fonts,
  type LayerKey,
  type Layers,
  type LocationLabel,
  type LyricOptions,
  type Scene,
  type StatusLine,
  type StatusTone,
  type TimelineConfig,
  type TransitionKind,
} from "./types";

const COLOR_KEYS = [
  "cyan",
  "red",
  "green",
  "white",
  "grey",
  "dim",
  "box",
] as const;

const TONES = new Set<StatusTone>(["green", "cyan", "red", "grey"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function expectRecord(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new TimelineError(`${label} must be a mapping.`);
  }
  return value;
}

function expectString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TimelineError(`${label} must be a non-empty string.`);
  }
  return value;
}

function expectNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TimelineError(`${label} must be a finite number.`);
  }
  return value;
}

function expectBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new TimelineError(`${label} must be true or false.`);
  }
  return value;
}

function parseColors(value: unknown): Colors {
  const raw = expectRecord(value, "colors");
  const colors = {} as Colors;
  for (const key of COLOR_KEYS) {
    colors[key] = expectString(raw[key], `colors.${key}`);
  }
  return colors;
}

function parseFonts(value: unknown): Fonts {
  const raw = expectRecord(value, "fonts");
  const hud = expectString(raw.hud, "fonts.hud");
  const lyrics = expectString(raw.lyrics, "fonts.lyrics");
  if (hud !== "JetBrains Mono") {
    throw new TimelineError(
      `fonts.hud must be "JetBrains Mono" (the bundled HUD font). Got "${hud}".`,
    );
  }
  if (lyrics !== "Bebas Neue") {
    throw new TimelineError(
      `fonts.lyrics must be "Bebas Neue" (the bundled lyric font). Got "${lyrics}".`,
    );
  }
  return {hud, lyrics};
}

function parseAccentWords(value: unknown): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.some((word) => typeof word !== "string")) {
    throw new TimelineError("accentWords must be a list of strings.");
  }
  return value.map((word) => word.trim()).filter(Boolean);
}

function parseOverrides(value: unknown): LyricOptions["overrides"] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) {
    throw new TimelineError("lyrics.overrides must be a list.");
  }
  return value.map((item, index) => {
    const raw = expectRecord(item, `lyrics.overrides[${index}]`);
    const start = expectNumber(raw.start, `lyrics.overrides[${index}].start`);
    const end = expectNumber(raw.end, `lyrics.overrides[${index}].end`);
    const text = expectString(raw.text, `lyrics.overrides[${index}].text`);
    if (end <= start) {
      throw new TimelineError(
        `lyrics.overrides[${index}] end must be greater than start.`,
      );
    }
    return {start, end, text};
  });
}

function parseLyrics(value: unknown): LyricOptions {
  const defaults: LyricOptions = {
    pauseGapSec: 1.2,
    maxLineChars: 32,
    maxWords: 7,
    holdSec: 0.75,
    overrides: [],
  };
  if (value === undefined) return defaults;
  const raw = expectRecord(value, "lyrics");
  const pauseGapSec =
    raw.pauseGapSec === undefined
      ? defaults.pauseGapSec
      : expectNumber(raw.pauseGapSec, "lyrics.pauseGapSec");
  const maxLineChars =
    raw.maxLineChars === undefined
      ? defaults.maxLineChars
      : expectNumber(raw.maxLineChars, "lyrics.maxLineChars");
  const maxWords =
    raw.maxWords === undefined
      ? defaults.maxWords
      : expectNumber(raw.maxWords, "lyrics.maxWords");
  const holdSec =
    raw.holdSec === undefined
      ? defaults.holdSec
      : expectNumber(raw.holdSec, "lyrics.holdSec");
  if (pauseGapSec <= 0) {
    throw new TimelineError("lyrics.pauseGapSec must be greater than 0.");
  }
  if (maxLineChars < 4) {
    throw new TimelineError("lyrics.maxLineChars must be at least 4.");
  }
  if (!Number.isInteger(maxWords) || maxWords < 1) {
    throw new TimelineError("lyrics.maxWords must be an integer of at least 1.");
  }
  if (holdSec < 0) {
    throw new TimelineError("lyrics.holdSec cannot be negative.");
  }
  return {
    pauseGapSec,
    maxLineChars,
    maxWords,
    holdSec,
    overrides: parseOverrides(raw.overrides),
  };
}

function parseLayers(value: unknown, label: string): Layers {
  const raw = expectRecord(value, label);
  const unknown = Object.keys(raw).filter(
    (key) => !LAYER_KEYS.includes(key as LayerKey),
  );
  if (unknown.length > 0) {
    throw new TimelineError(
      `${label} has unknown keys: ${unknown.join(", ")}. Expected ${LAYER_KEYS.join(", ")}.`,
    );
  }
  const layers = {} as Layers;
  for (const key of LAYER_KEYS) {
    if (!(key in raw)) {
      throw new TimelineError(`${label}.${key} is required.`);
    }
    layers[key] = expectBoolean(raw[key], `${label}.${key}`);
  }
  return layers;
}

function parseLocation(value: unknown, label: string, required: boolean): LocationLabel {
  if (value === undefined) {
    if (required) {
      throw new TimelineError(`${label} is required when the location layer is on.`);
    }
    return {kicker: "LOC", title: "", subtitle: ""};
  }
  const raw = expectRecord(value, label);
  const kicker =
    raw.kicker === undefined ? "LOC" : expectString(raw.kicker, `${label}.kicker`);
  const title = required
    ? expectString(raw.title, `${label}.title`)
    : typeof raw.title === "string"
      ? raw.title
      : "";
  const subtitle = required
    ? expectString(raw.subtitle, `${label}.subtitle`)
    : typeof raw.subtitle === "string"
      ? raw.subtitle
      : "";
  return {kicker, title, subtitle};
}

function parseStatus(value: unknown, label: string, required: boolean): StatusLine[] {
  if (value === undefined) {
    if (required) {
      throw new TimelineError(`${label} is required when the status layer is on.`);
    }
    return [];
  }
  if (!Array.isArray(value) || value.length === 0) {
    throw new TimelineError(`${label} must be a non-empty list.`);
  }
  return value.map((item, index) => {
    const raw = expectRecord(item, `${label}[${index}]`);
    const tone = expectString(raw.tone, `${label}[${index}].tone`) as StatusTone;
    if (!TONES.has(tone)) {
      throw new TimelineError(
        `${label}[${index}].tone must be green, cyan, red, or grey.`,
      );
    }
    return {
      label: expectString(raw.label, `${label}[${index}].label`),
      value: expectString(raw.value, `${label}[${index}].value`),
      tone,
    };
  });
}

function parseScene(value: unknown, index: number): Scene {
  const raw = expectRecord(value, `scenes[${index}]`);
  const id =
    raw.id === undefined
      ? `scene-${index + 1}`
      : expectString(raw.id, `scenes[${index}].id`);
  const sceneIn = expectNumber(raw.in, `scenes[${index}].in`);
  const sceneOut = expectNumber(raw.out, `scenes[${index}].out`);
  if (sceneOut <= sceneIn) {
    throw new TimelineError(`scenes[${index}] (${id}) out must be greater than in.`);
  }
  if (sceneIn < 0) {
    throw new TimelineError(`scenes[${index}] (${id}) in cannot be negative.`);
  }
  const transitionRaw = raw.transition === undefined ? "fade" : raw.transition;
  if (transitionRaw !== "fade" && transitionRaw !== "glitch") {
    throw new TimelineError(
      `scenes[${index}].transition must be "fade" or "glitch".`,
    );
  }
  const transition = transitionRaw as TransitionKind;
  const transitionFrames =
    raw.transitionFrames === undefined
      ? 12
      : expectNumber(raw.transitionFrames, `scenes[${index}].transitionFrames`);
  if (
    !Number.isInteger(transitionFrames) ||
    transitionFrames < 1 ||
    transitionFrames > 90
  ) {
    throw new TimelineError(
      `scenes[${index}].transitionFrames must be an integer from 1 to 90.`,
    );
  }
  const layers = parseLayers(raw.layers, `scenes[${index}].layers`);
  const location = parseLocation(
    raw.location,
    `scenes[${index}].location`,
    layers.location,
  );
  const camera = layers.rec
    ? expectString(raw.camera, `scenes[${index}].camera`)
    : typeof raw.camera === "string"
      ? raw.camera
      : "";
  const status = parseStatus(raw.status, `scenes[${index}].status`, layers.status);
  return {
    id,
    in: sceneIn,
    out: sceneOut,
    transition,
    transitionFrames,
    layers,
    location,
    camera,
    status,
  };
}

export function parseTimeline(yamlText: string): TimelineConfig {
  let document: unknown;
  try {
    document = parse(yamlText);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new TimelineError(`Could not parse timeline YAML: ${message}`);
  }
  const raw = expectRecord(document, "timeline");
  const version = expectNumber(raw.version, "version");
  if (version !== 1) {
    throw new TimelineError(`Unsupported timeline version ${version}. Expected 1.`);
  }
  const fps = expectNumber(raw.fps, "fps");
  const width = expectNumber(raw.width, "width");
  const height = expectNumber(raw.height, "height");
  if (fps !== 30 || width !== 1920 || height !== 1080) {
    throw new TimelineError(
      `Overlay kit only renders 1080p30. Got ${width}x${height} @ ${fps}fps.`,
    );
  }
  if (!Array.isArray(raw.scenes) || raw.scenes.length === 0) {
    throw new TimelineError("scenes must be a non-empty list.");
  }
  const scenes = raw.scenes.map((scene, index) => parseScene(scene, index));
  const ordered = [...scenes].sort((a, b) => a.in - b.in);
  for (let i = 1; i < ordered.length; i++) {
    if (ordered[i].in < ordered[i - 1].out) {
      throw new TimelineError(
        `Scenes "${ordered[i - 1].id}" and "${ordered[i].id}" overlap.`,
      );
    }
  }
  const scenesEnd = ordered.reduce((max, scene) => Math.max(max, scene.out), 0);
  let durationSec: number | undefined;
  if (raw.durationSec !== undefined) {
    durationSec = expectNumber(raw.durationSec, "durationSec");
    if (durationSec <= 0) {
      throw new TimelineError("durationSec must be greater than 0.");
    }
    if (durationSec + 1e-4 < scenesEnd) {
      throw new TimelineError(
        `durationSec (${durationSec}) ends before the last scene (${scenesEnd}).`,
      );
    }
  }
  return {
    version: 1,
    song: expectString(raw.song, "song"),
    alignment: expectString(raw.alignment, "alignment"),
    fps: 30,
    width: 1920,
    height: 1080,
    durationSec,
    // T+ clock resets to 00:00 at songStartSec by default (offset 0).
    timecodeOffsetSec:
      raw.timecodeOffsetSec === undefined ? 0 : expectNumber(raw.timecodeOffsetSec, "timecodeOffsetSec"),
    songStartSec:
      raw.songStartSec === undefined ? 0 : expectNumber(raw.songStartSec, "songStartSec"),
    colors: parseColors(raw.colors),
    fonts: parseFonts(raw.fonts),
    accentWords: parseAccentWords(raw.accentWords),
    lyrics: parseLyrics(raw.lyrics),
    scenes: ordered,
  };
}
