# It's Not What We Thought… — video tools

> Code created with Cursor and Grok Bots.

Three small tools for the music video. They cover the era cut, the blue
BASIC screen, and the split-screen choruses in the concept.

1. **Era transition.** Clip A falls through a CRT (curvature, scanlines, bloom), then pixelates and dithers onto the 16-color C64 palette, then the same stages run backwards into clip B. Duration and easing are configurable. Each stage is also a standalone look.
2. **C64 screen.** A 40×25 blue boot screen: border, background, the BASIC V2 banner, `38911 BASIC BYTES FREE`, `READY.`, and a cursor that blinks at the KERNAL rate. A script types, mistypes, and backspaces. PETSCII graphics have names. The frame is an integer nearest-neighbor scale to 1080p.
3. **Compositor.** Vertical split, horizontal split, triptych, and 1+2. A YAML file sets the divider, per-panel look, labels, and which input the audio comes from. ffmpeg does the composite in one filter graph.

Python 3.10+ and ffmpeg. No paid services.

## Install

```bash
pip install -e .
```

`inwwt` needs `ffmpeg` and `ffprobe` on `PATH`.

## Era transition

```bash
inwwt transition \
  --a future.mp4 --b now.mp4 --out transition.mp4 \
  --duration 8 --fps 24 --width 1280 --height 720 \
  --curve smoothstep --dither bayer --palette pepto
```

`--dither` is `bayer` (ordered, default matrix 4×4, `--bayer-size 8` for 8×8), `floyd` (Floyd–Steinberg), or `nearest`. `--palette` is `pepto` or `colodore`. See LICENSES.md for the citations.

`--curve` is `linear`, `smoothstep`, `smootherstep`, `ease-in`, `ease-out`, or `ease-in-out`. It eases the whole timeline before the stages split.

`--phases` is six increasing fractions of that eased timeline:

```text
crt_in, pixelate, dither, hold, undither, unpixel
```

CRT then fades out over whatever is left. The picture switches from A to B in the middle of the hold, while both frames are fully dithered, so the cut is hidden in the 8-bit frame. Defaults: `0.18,0.34,0.46,0.54,0.66,0.82`.

CRT knobs: `--curvature`, `--scanline`, `--bloom`, `--bloom-radius`, `--vignette`, `--chroma`.

### One stage on its own

```bash
inwwt look --input plate.mp4 --out crt.mp4 --look crt
inwwt look --input plate.mp4 --out blocks.mp4 --look pixelate --pixel-scale 6
inwwt look --input plate.mp4 --out dither.mp4 --look dither --dither floyd --palette colodore
inwwt look --input plate.mp4 --out c64.mp4 --look c64
inwwt look --input plate.mp4 --out full.mp4 --look full
```

`c64` is pixelate-to-320-wide plus dither. `full` is the CRT look and then that.

Stills need `--duration`. Video is read at `--fps` (default 24) and can be trimmed with `--duration`.

## C64 screen

```bash
inwwt c64 --script examples/c64_boot.script --out c64.mp4
```

The default frame is 1920×1080. The text matrix is 320×200. It sits in a 384×216 low-resolution frame (32×8 pixels of border) and that whole frame is scaled ×5 with nearest-neighbor, which lands on 1080p exactly. 320×200 itself does not divide 1080. `--scale 4` uses a 480×270 frame instead, with a thicker border.

Colors are the power-on registers: border 14, background 6, text 14. `--palette pepto` is the default. `--blink ntsc` toggles every 20/60 of a second (the KERNAL's `BLNCT` on a 60 Hz machine). `--blink pal` uses 20/50. You can also pass a period in seconds.

The banner and the free-memory line are the strings in the BASIC ROM (`mist64/c64rom`, `basic/init.s`): clear-screen, a carriage return, the banner, a blank line, ` 64K RAM SYSTEM  ` plus `38911` plus ` BASIC BYTES FREE`, then `READY.` with the cursor on the next line.

### Script

```text
.cps 12
.hold 1.1
10 PRINT "HELLO."
.enter
30 PR{typo:ONT:INT} "I THINK IN BASIC."
.enter
.ready
{spade} NOT WHAT WE THOUGHT {heart}
```

Lines that start with `.` are directives. Other lines are typed, including leading spaces. A line whose first non-space character is `#` is a comment.

| Directive | Effect |
| --- | --- |
| `.cps 12` | Characters per second |
| `.delay 0.08` | Seconds before each character, instead of `.cps` |
| `.hold 0.4` | Pause |
| `.enter` | Carriage return |
| `.bs` / `.bs 3` | Backspace |
| `.ready` | The ROM's `READY.` (a leading return, the word, a trailing return) |
| `.boot` / `.noboot` | Power-on screen, or an empty blue screen. Put these before typed lines |
| `.rvs on` | Reverse video |
| `.col 14` | Text color, 0–15 or a palette name (`light blue`) |
| `.charset upper` | `upper` (graphics, the boot set) or `lower` |
| `.cursor off` | Stop drawing the cursor |

Inline, inside a typed line:

| Token | Effect |
| --- | --- |
| `{d:0.4}` | Delay before the next character only |
| `{hold:0.2}` | Extra pause |
| `{typo:ONT:INT}` | Type the mistake, pause, backspace, type the correction |
| `{bs}` `{bs:2}` | Backspace |
| `{sc:65}` `{sc:0x41}` | Screen code. 128–255 are reverse video |
| `{spade}` `{heart}` `{diamond}` `{club}` | Card suits |
| `{hbar}` `{vbar}` `{circle}` `{shade}` `{block}` | Rules, disc, checker, solid block |
| `{lhalf}` `{bblock}` `{tline}` `{tl}` `{tr}` `{bl}` `{br}` | Blocks and an edge-aligned box |
| `{rvs}` `{rvsoff}` `{col:7}` `{cr}` | Reverse, color, return |

`{block}` is screen code 160, a reversed space. The edge box (`tl`, `tr`, `bl`, `br`) uses the corner glyphs; it does not connect to `{hbar}`, which sits in the middle of the cell.

The font is Style's **C64 Pro Mono**. The file in `inwwt/fonts/` keeps Style's name. Read LICENSES.md before copying it.

## Compositor

```bash
inwwt composite --config examples/splitscreen.yaml --out split.mp4
```

`examples/threeway.yaml` is the triptych. `examples/one_plus_two.yaml` is the large-plus-pair layout (`primary` is `left`, `right`, `top`, or `bottom`; panel 0 is the large one).

```yaml
output:
  width: 1920
  height: 1080
  fps: 24
  duration: 8
layout: split-vertical          # split-horizontal, triptych, one-plus-two
divider: {px: 8, color: "101820"}
labels: {show: true, size: 42, position: bottom}
audio: {from: panel, index: 1}  # or from: file / path:, or from: none
panels:
  - src: clips/then.mp4
    label: "1984"
    look: c64                   # none, crt, pixelate, dither, c64, full
    dither: bayer               # bayer, floyd, nearest
    palette: pepto
  - src: clips/now.mp4
    label: "2026"
    look: none
```

Looks are ffmpeg filters in the same graph as the stack: `lenscorrection`, a scanline `geq`, bloom via `gblur` and `blend`, `scale` with `neighbor`, and `paletteuse` against a generated Pepto or Colodore palette. Audio is trimmed from the chosen panel or from an external file. Stills are looped. If `output.duration` is omitted, the composite uses the shortest video.

## Demos

```bash
inwwt demos --out demos
```

This writes four files from generated plates (a wood "THEN", a warm "NOW", a luminous "FUTURE"), each with its own sine tone:

| File | What it shows |
| --- | --- |
| `demos/transition_demo.mp4` | FUTURE degrades to the Pepto palette and resolves into NOW |
| `demos/c64_screen_demo.mp4` | Boot screen, typing, a typo, `READY.`, PETSCII, 1080p |
| `demos/splitscreen_demo.mp4` | 1984 (C64 look) beside 2026, audio from the left |
| `demos/threeway_demo.mp4` | Triptych, future panel with the CRT look, audio from the center |

`--transition-dither floyd` switches the transition demo to Floyd–Steinberg. The default is Bayer, which is the ordered dither.

## Tests

```bash
python -m unittest discover -s tests
```

The suite checks the published palette triples, the Bayer matrix, Floyd–Steinberg error spreading, CRT scanlines and barrel corners, the transition stages, the ROM banner, typing and typos, the NTSC blink, the integer 1080p scale, layout geometry, and a short ffmpeg composite.

## What this is for

Shot 7 of the concept (the CRT glow becoming the other era) and shot 17 (the future frame dithering down to C64) are `inwwt transition`. Shots 1, 2, and 18 are `inwwt c64`. Shots 12 and 16 are `inwwt composite`.
