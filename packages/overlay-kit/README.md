# Overlay Kit

> Code created with Cursor and Grok Bots.

A Remotion HUD that draws a transparent sci-fi layer over a finished music video. One timeline YAML file drives the scenes. The render is 1080p30 only, with alpha, as ProRes 4444 (`.mov`) or VP8 WebM. An ffmpeg script then lays that overlay and the song onto a background plate.

The demo timeline is **The Seventh Observation** (1:57). Word timings come from the WhisperX alignment in `assets/alignment/alignment.json`.

## Licenses

**Remotion** is free for individuals, non-profits, and for-profit organizations with up to 3 employees, including commercial video work. Larger for-profit organizations need a company license. See `node_modules/remotion/LICENSE.md` and [remotion.dev/license](https://www.remotion.dev/license).

**JetBrains Mono** (HUD type) and **Bebas Neue** (lyric type) are bundled in `public/fonts/` under the SIL Open Font License 1.1. The license texts are next to the files:

- `public/fonts/OFL-JetBrainsMono.txt` — Copyright 2020 The JetBrains Mono Project Authors
- `public/fonts/OFL-BebasNeue.txt` — Copyright 2010 Ryoichi Tsunekawa, Dharma Type

## What the frame contains

Layers toggle per scene. There are no quote cards.

- Thin cyan corner brackets.
- Top-left location tag: `LOC`, a bold title, a grey subtitle, in a dark box with cyan corner ticks.
- Top-right record box: running `T+MM:SS.CC` timecode, a blinking red REC dot, and a camera label.
- Lower-third lyrics in Bebas Neue. The current line is on screen. Sung words are white, accent words turn red, unsung words stay dim. Lines change at line boundaries.
- Bottom-left system status (`SYS > NOMINAL` and the rest of the lines in the YAML) plus a cyan bar equalizer driven by the song (`visualizeAudio`).

Scene changes fade or glitch the layers that turn on.

## Layout

```
assets/audio/The_Seventh_Observation.mp3
assets/alignment/alignment.json
public/fonts/                  bundled OFL fonts
public/audio/                  song copy served to Remotion (the render script refreshes it)
timelines/seventh-observation.yaml
src/lib/                       YAML parser, lyric converter, timecode
src/components/                HUD layers
scripts/render-overlay.sh      ProRes 4444 or WebM with alpha
scripts/composite.sh           background + overlay + song -> 1080p30 MP4
scripts/generate-background.sh placeholder slow-pan plate
test/                          parser and lyric converter tests
```

## Requirements

Node 20+ and ffmpeg on `PATH`.

```bash
npm install
npm test
```

## Timeline YAML

`fps`, `width`, and `height` must be `30`, `1920`, and `1080`. Anything else is rejected.

```yaml
version: 1
song: audio/The_Seventh_Observation.mp3   # path inside public/
alignment: assets/alignment/alignment.json
fps: 30
width: 1920
height: 1080
songStartSec: 0                          # T+ clock reads 00:00 here (default 0)
timecodeOffsetSec: 0                     # optional extra offset (default 0)
colors: { cyan, red, green, white, grey, dim, box }
fonts:
  hud: JetBrains Mono
  lyrics: Bebas Neue
accentWords: [humans, hope, galactic]
lyrics:
  pauseGapSec: 1.6
  maxLineChars: 36
  maxWords: 8
  holdSec: 0.85
  overrides:
    - start: 0.16
      end: 4.40
      text: "HELLO AGAIN, *HUMANS*."
scenes:
  - id: intro
    in: 0
    out: 16
    transition: fade          # fade or glitch
    transitionFrames: 18
    layers:
      brackets: true
      location: true
      rec: false
      lyrics: false
      status: false
      equalizer: false
    location:
      kicker: LOC
      title: "MARS · DUNE CREST"
      subtitle: "THE COLONY BELOW"
```

`alignment.json` is a WhisperX-style document: a top-level `words` array of `{word, start, end}`, or the same objects nested under `segments[].words`. `duration_sec` sets the composition length when it is longer than the last scene.

Optional top-level `durationSec` sets the composition length in seconds. Use it when the picture runs past the song: the song still ends on its own, and the audio-driven equalizer rests (silence) after the audio file ends. `durationSec` must be greater than 0 and at least the last scene's `out`. Omit it and the length stays the longer of the alignment, the lyric lines, and the last scene. `timelines/demo-cut.yaml` is a 127s cut of The Seventh Observation: the song plays to 117s and a silent title runs to 127s.

The lyric converter groups those words into lines, breaking on a pause longer than `pauseGapSec` or when the next word would pass `maxLineChars` or `maxWords`. A word is red when it is in `accentWords` (punctuation and case ignored) or wrapped in `*asterisks*` in an override. Overrides replace any automatic lines they overlap and keep the alignment timings when the word counts match.

The demo has four scenes: intro (brackets + location), verse (every layer), bridge (lyrics only), outro (status + equalizer).

## Render

From the repo root.

```bash
# Transparent WebM (VP8 + alpha) for the full song
npm run render:webm

# Transparent ProRes 4444 .mov
npm run render:prores

# A frame range, passed through to Remotion (end is inclusive-style: 0-9 is 10 frames)
bash scripts/render-overlay.sh webm out/sample.webm --frames=660-959

# Placeholder background, then the final MP4
npm run background
npm run composite
```

`scripts/composite.sh` takes four paths:

```bash
bash scripts/composite.sh background.mp4 overlay.webm song.mp3 final.mp4
```

The output is H.264 + AAC, 1920×1080, 30 fps, yuv420p. The overlay must be a transparent ProRes 4444 or WebM. The song is taken from the third input, not from the overlay. WebM input is decoded with libvpx so the alpha side channel is kept.

Props for Remotion are generated from the YAML first (`npm run props` writes `out/props.json`). Studio:

```bash
npm run props
npm run studio
```

## Tests

```bash
npm test
npx tsc --noEmit
```

The tests cover pause and length splits, accent words, `*word*` markers, manual overrides, 1080p30 rejection, overlapping scenes, per-scene layer toggles, and the sample timeline against the real alignment file.


## T+ timer
By default the T+ clock resets to T+00:00.00 at the start of each song. Set `songStartSec` to the second where the song begins in the video; the clock holds at 00:00 before that. `timecodeOffsetSec` is optional and only adds a deliberate offset (default 0).

See NEW_VIDEO_TIMELINE.md for how to make a timeline for a new video.

## Public staging note

Demo song MP3s are **not** included (over 2 MB). See `assets/audio/README.md`.
