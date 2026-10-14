import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {formatTimecode} from "../src/lib/timecode.js";
import {parseTimeline} from "../src/lib/parseTimeline.js";
import {resolveTimeline} from "../src/lib/resolveTimeline.js";
import {layerMotion} from "../src/lib/motion.js";
import {spectrumAtTime} from "../src/lib/spectrum.js";
import {TimelineError, type Alignment} from "../src/lib/types.js";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const colors = `
colors:
  cyan: "#5CE1FF"
  red: "#FF2E2E"
  green: "#3DFF8A"
  white: "#F3F6FA"
  grey: "#8B95A7"
  dim: "#5C6775"
  box: "rgba(5, 10, 16, 0.70)"
fonts:
  hud: JetBrains Mono
  lyrics: Bebas Neue
`;

function timeline(body: string): string {
  return `
version: 1
song: song.mp3
alignment: assets/alignment/alignment.json
fps: 30
width: 1920
height: 1080
timecodeOffsetSec: 170.38
${colors}
${body}
`;
}

const oneScene = `
scenes:
  - id: intro
    in: 0
    out: 4
    transition: fade
    layers:
      brackets: true
      location: true
      rec: false
      lyrics: false
      status: false
      equalizer: false
    location:
      title: "MARS · DUNE CREST"
      subtitle: "THE COLONY BELOW"
`;

test("formatTimecode matches the HUD reference at the demo offset", () => {
  assert.equal(formatTimecode(170.38), "T+02:50.38");
  assert.equal(formatTimecode(0), "T+00:00.00");
  assert.equal(formatTimecode(65.01), "T+01:05.01");
});

test("parser reads global fields, scenes, and layer toggles", () => {
  const config = parseTimeline(timeline(oneScene));
  assert.equal(config.fps, 30);
  assert.equal(config.width, 1920);
  assert.equal(config.height, 1080);
  assert.equal(config.song, "song.mp3");
  assert.equal(config.timecodeOffsetSec, 170.38);
  assert.equal(config.fonts.hud, "JetBrains Mono");
  assert.equal(config.scenes[0].layers.brackets, true);
  assert.equal(config.scenes[0].layers.lyrics, false);
  assert.equal(config.scenes[0].location.title, "MARS · DUNE CREST");
  assert.equal(config.scenes[0].location.kicker, "LOC");
  assert.equal(config.scenes[0].transition, "fade");
  assert.equal(config.lyrics.pauseGapSec, 1.2);
});

test("parser rejects anything other than 1080p30", () => {
  assert.throws(
    () => parseTimeline(timeline(oneScene).replace("fps: 30", "fps: 24")),
    (error: unknown) => {
      assert.ok(error instanceof TimelineError);
      assert.match(error.message, /1080p30/);
      return true;
    },
  );
  assert.throws(
    () => parseTimeline(timeline(oneScene).replace("width: 1920", "width: 1280")),
    /1080p30/,
  );
});

test("parser rejects overlapping scenes and unknown layers", () => {
  const overlap = `
scenes:
  - id: a
    in: 0
    out: 5
    layers:
      brackets: true
      location: false
      rec: false
      lyrics: false
      status: false
      equalizer: false
  - id: b
    in: 4
    out: 8
    layers:
      brackets: false
      location: false
      rec: true
      lyrics: false
      status: false
      equalizer: false
    camera: "CAM 05 · SHOULDER"
`;
  assert.throws(() => parseTimeline(timeline(overlap)), /overlap/i);
  const unknown = oneScene.replace("equalizer: false", "eq: false");
  assert.throws(() => parseTimeline(timeline(unknown)), /unknown keys/i);
});

test("status and camera labels are required only when those layers are on", () => {
  assert.throws(
    () =>
      parseTimeline(
        timeline(`
scenes:
  - id: verse
    in: 0
    out: 2
    layers:
      brackets: false
      location: false
      rec: true
      lyrics: true
      status: true
      equalizer: true
`),
      ),
    /camera/i,
  );
});

test("layer motion fades new layers in and glitches on scene changes", () => {
  const config = parseTimeline(
    timeline(`
scenes:
  - id: intro
    in: 0
    out: 2
    transition: fade
    transitionFrames: 15
    layers:
      brackets: true
      location: true
      rec: false
      lyrics: false
      status: false
      equalizer: false
    location:
      title: MARS
      subtitle: DUNE
  - id: verse
    in: 2
    out: 4
    transition: glitch
    transitionFrames: 10
    layers:
      brackets: true
      location: false
      rec: false
      lyrics: true
      status: false
      equalizer: false
`),
  );
  const introStart = layerMotion(config.scenes, 0, "brackets", 0);
  assert.equal(introStart.opacity, 0);
  const introSettled = layerMotion(config.scenes, 1, "brackets", 30);
  assert.equal(introSettled.opacity, 1);
  assert.equal(layerMotion(config.scenes, 1, "lyrics", 30).visible, false);
  const verseLyrics = layerMotion(config.scenes, 2.01, "lyrics", 61);
  assert.equal(verseLyrics.visible, true);
  assert.ok(verseLyrics.glitch > 0);
  const verseBrackets = layerMotion(config.scenes, 2.01, "brackets", 60);
  assert.equal(verseBrackets.visible, true);
  assert.ok(verseBrackets.glitch > 0);
  assert.ok(verseBrackets.jitterX !== 0);
});

test("durationSec is optional and extends the picture past the song", () => {
  const alignment: Alignment = {
    duration_sec: 10,
    words: [{word: "Hello", start: 0.2, end: 0.8}],
  };
  const omitted = parseTimeline(timeline(oneScene));
  assert.equal(omitted.durationSec, undefined);
  const natural = resolveTimeline(omitted, alignment);
  assert.equal(natural.durationSec, 10);
  assert.equal(natural.durationInFrames, Math.ceil(10 * 30 - 1e-6));

  const extended = parseTimeline(timeline(`durationSec: 25\n${oneScene}`));
  assert.equal(extended.durationSec, 25);
  const resolved = resolveTimeline(extended, alignment);
  assert.equal(resolved.durationSec, 25);
  assert.equal(resolved.durationInFrames, 750);
  assert.ok(resolved.durationSec > alignment.duration_sec!);

  assert.throws(
    () => parseTimeline(timeline(`durationSec: 0\n${oneScene}`)),
    /durationSec/,
  );
  assert.throws(
    () => parseTimeline(timeline(`durationSec: 2\n${oneScene}`)),
    /ends before the last scene/,
  );
});

test("the equalizer is silent once playback passes the song", () => {
  const songSec = 117.002375;
  let samples = 0;
  const during = spectrumAtTime(116.5, songSec, 4, () => {
    samples += 1;
    return [0.2, 0.4, 0.8, 0.1];
  });
  assert.deepEqual(during, [0.2, 0.4, 0.8, 0.1]);
  assert.equal(samples, 1);

  const atEnd = spectrumAtTime(songSec, songSec, 4, () => {
    samples += 1;
    return [0.9, 0.9, 0.9, 0.9];
  });
  assert.deepEqual(atEnd, [0, 0, 0, 0]);
  const titleCard = spectrumAtTime(120, songSec, 4, () => {
    throw new Error("must not read audio after the song");
  });
  assert.deepEqual(titleCard, [0, 0, 0, 0]);
  assert.equal(samples, 1);
});

test("seventh-observation timeline parses", () => {
  const yamlText = readFileSync(join(root, "timelines/seventh-observation.yaml"), "utf8");
  const tl = parseTimeline(yamlText);
  expect(tl.scenes.length).toBeGreaterThan(0);
});

test("sample timeline resolves The Seventh Observation", () => {
  const yamlText = readFileSync(
    join(root, "timelines/seventh-observation.yaml"),
    "utf8",
  );
  const alignment = JSON.parse(
    readFileSync(join(root, "assets/alignment/alignment.json"), "utf8"),
  ) as Alignment;
  const config = parseTimeline(yamlText);
  assert.equal(config.durationSec, undefined);
  const resolved = resolveTimeline(config, alignment);
  assert.equal(resolved.fps, 30);
  assert.equal(resolved.width, 1920);
  assert.equal(resolved.height, 1080);
  assert.equal(resolved.durationInFrames, Math.ceil(resolved.durationSec * 30 - 1e-6));
  assert.ok(resolved.durationSec > 116 && resolved.durationSec < 118);
  assert.equal(resolved.scenes.length, 4);
  assert.deepEqual(
    resolved.scenes.map((scene) => scene.id),
    ["intro", "verse", "bridge", "outro"],
  );
  assert.equal(resolved.scenes[0].layers.brackets, true);
  assert.equal(resolved.scenes[0].layers.lyrics, false);
  assert.equal(resolved.scenes[1].layers.equalizer, true);
  assert.equal(resolved.scenes[2].layers.lyrics, true);
  assert.equal(resolved.scenes[2].layers.brackets, false);
  assert.equal(resolved.scenes[3].layers.status, true);
  assert.equal(resolved.scenes[3].layers.equalizer, true);
  assert.equal(resolved.scenes[3].layers.lyrics, false);
  const humans = resolved.lines.flatMap((line) => line.words).find((item) =>
    item.text.toLowerCase().includes("human"),
  );
  assert.ok(humans);
  assert.equal(humans.accent, true);
  assert.ok(resolved.lines.length >= 8);
  const alones = resolved.lines.filter((line) =>
    line.words.every((word) => word.text.toLowerCase().includes("alone")),
  );
  assert.equal(alones.length, 2);
  assert.ok(alones[0].end < 86, `first ALONE line should end before the held note, got ${alones[0].end}`);
  assert.ok(alones[1].start >= alones[0].end - 0.05);
});

test("T+ clock defaults to 00:00 at song start", () => {
  const raw = timeline(oneScene).replace(/timecodeOffsetSec: 170\.38\n/, "");
  const config = parseTimeline(raw);
  assert.equal(config.timecodeOffsetSec, 0);
  assert.equal(config.songStartSec, 0);
});
