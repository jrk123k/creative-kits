# Kit Sprite Packer

> Code created with Cursor and Grok Bots.

Pack a folder of pixel frames into one PNG atlas, a JSON file, and a GIF and MP4 preview of each animation. Pixels are copied. Nothing is resampled, and alpha is not composited, so a transparent pixel keeps the RGB it was painted with.

The JSON is the packer's own format. `adapt` turns it into files the 16-bit intro kit can load: one PNG per frame, plus `intro.yaml`. The mapping is below.

You need Python 3.11 or newer and the packages in `requirements.txt`. `ffmpeg` is only used for the MP4. If it is not on `PATH`, the atlas, the JSON, and the GIF are still written.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python examples/demo/build.py
```

`examples/demo` is synthetic art: a 14×12 cow in four turns, and a 256×224 singer with a closed mouth and an open mouth. No outside assets.

## Commands

Run these from the repo root.

```bash
python -m spritepack pack examples/demo/frames -o examples/demo/out \
  --name demo --padding 1 --max-width 270

python -m spritepack unpack examples/demo/out/demo.json -o /tmp/frames

python -m spritepack preview examples/demo/out/demo.json -o /tmp/previews

python -m spritepack adapt examples/demo/out/demo.json \
  -o examples/demo/kit --plate examples/demo/bg/hill_256.png --name kit-demo
```

`pack` writes the atlas, the JSON, and one GIF and one MP4 per animation. `unpack` crops the atlas back to the source filenames. `preview` rebuilds the GIF and MP4 from the JSON alone. `adapt` writes a kit project.

`python examples/demo/build.py` redraws the frames and runs pack and adapt.

| Flag | Default | What it does |
| --- | --- | --- |
| `--padding` | 0 | Empty pixels between frames and around the atlas edge. Rects do not include it. |
| `--max-width` | 4096 | Row width before the shelf wraps. Same limit Pixel Studio uses for a sheet. A frame wider than this still gets a row. |
| `--fps` | 30 | Film rate. The kit's films are 30. A sidecar `fps` wins when it is set. |
| `--hold` | 4 | Default pose length in film frames. This is `cycle.hold` and `vocals.hold_frames` in the kit. |
| `--duration-ms` | from hold and fps | Pose length in milliseconds. 4 frames at 30 fps is 133.333 ms. |
| `--anchor` | `bottom-center` | Preset or `x,y`. See below. |
| `--background` | `#000000` | `#rrggbb`, `r,g,b`, or an image. A sidecar value wins. |
| `--scale` | 4 | Integer nearest-neighbor scale for the preview. |
| `--place` | fitted | `x,y` or `name:x,y`. Where the anchor sits on the preview background. |
| `--place-space` | `anchor` | `anchor` or `top-left`. Pixel Studio's `offset` is top-left. |
| `--kit-place` | | `x,y` on the 256×224 plate, in anchor space. |
| `--frame-duration` | | `file=ms`, repeatable. Beats the sidecar for that frame. |
| `--frame-anchor` | | `file=x,y` or `file=bottom-center`, repeatable. |
| `--no-preview` | | Atlas and JSON only. |

`--place cow:48,52` sets one animation. A bare `--place 48,52` sets all of them.

## Input names

Point `pack` at one folder. PNG only. Subfolders are separate runs. Several animations can share the folder. The name is the shot, and the number is the order.

Checked in this order, so `singer_open_256.png` is the open plate and not frame 256 of `singer_open`:

| Pattern | Where it comes from | Animation |
| --- | --- | --- |
| `{shot}_open_patch.png` | Pixel Studio mouth patch | patch, not a playback frame |
| `{shot}_open_256.png` | open plate | `{shot}`, role open |
| `{shot}_256.png` | closed plate | `{shot}`, role closed |
| `{shot}_sprite_{n}.png` | Pixel Studio sprite export | `{shot}` |
| `{shot}_sprite.png` | one-frame sprite | `{shot}` |
| `{shot}_{n}.png` | intro kit `cow_beam_0.png`, `name_0.png`, Pixel Studio `{shot}_00.png` | `{shot}`, index `n` |
| `{shot}_{label}.png` | Pixel Studio extra plate frame | joins `{shot}` when that plate is in the folder |
| anything else | | its own one-frame animation |

`cow_0.png` comes before `cow_10.png`. A missing number is skipped, not a blank frame. Two files at the same index, or a shot that mixes numbered and `_sprite_` names, is an error.

A closed plate and an open plate make `kind: mouth`. Playback order is closed, open, then any extra plate frames by label.

## Sidecar

If the folder has `sprites.json`, it is read. `manifest.json` is the fallback, and a Pixel Studio sample manifest is recognized.

Per-frame timing and anchors, most specific first:

1. `--frame-duration` / `--frame-anchor`
2. `animations.{name}.frames` in the sidecar
3. the animation's `duration_ms`, `hold`, or `anchor`
4. the sidecar's top-level `duration_ms`, `hold`, or `anchor`
5. `--duration-ms`, or else `--hold` at `--fps`

`hold` is in frames of that file's fps (`animations.{name}.fps`, then the sidecar fps, then `--fps`). The stored `hold_frames` is at the atlas fps. Four frames at 8 fps is 500 ms, which is 15 frames at 30 fps.

```json
{
  "fps": 30,
  "hold": 4,
  "anchor": "bottom-center",
  "animations": {
    "cow": {
      "background": "../bg/pasture.png",
      "place": [48, 52],
      "place_space": "anchor",
      "scale": 8,
      "kit_place": [160, 176],
      "cycle": { "mode": "loop", "skip_last": 0 },
      "frames": { "cow_3.png": { "duration_ms": 400 } }
    }
  }
}
```

`files` is an explicit playback order. `frames` is an object of overrides, or a list of `{"file": "cow_3.png", "duration_ms": 400}`. A list of bare filenames belongs in `files`.

`cycle.mode` is `loop` or `once`. `skip_last` is passed through to the kit. The default mode is `loop`.

A Pixel Studio manifest is the membership list. Other PNGs in that folder, including the background, are not packed. `offset` is top-left on the background and is stored as `kit_top_left`, which the adapter uses as the kit's `x, y` without subtracting the anchor. `mouth: [0, 1]` marks the closed and open frames. `patch.file`, `patch.x`, and `patch.y` are the mouth patch.

Frame keys in a packer sidecar can be the filename, the stem, or the index (`"3"`).

## Atlas

Frames are sorted tallest first, then widest, then by id, and placed on shelves. The copy is a rectangle write. `Image.paste` is not used, because pasting onto empty pixels would multiply RGB by alpha.

Padding of 1 puts one transparent pixel between frames and around the border. The rect in the JSON is the frame only. An atlas wider than `--max-width` only happens when a single frame is wider than that.

RGB sources are stored as RGBA with alpha 255 and unpacked back to RGB. Indexed sources are stored as RGBA. The round trip compares those pixels, not the PNG bytes.

## JSON

`demo.json` is `format: kit-sprite-packer`, version 1. `image` is the atlas filename next to the JSON.

Each animation has `name`, `kind` (`sprite`, `mouth`, or `plate`), `naming`, `frames` (ids in playback order), and `cycle` (`mode`, `skip_last`). A mouth also has `mouth.closed`, `mouth.open`, and `patch` (`x`, `y`, `w`, `h` on the plate, plus `file` when a patch PNG was packed).

Each frame has:

| Field | Meaning |
| --- | --- |
| `rect` | `x`, `y`, `w`, `h` in the atlas. Origin is the top-left. |
| `duration_ms` | How long this pose stays up. |
| `hold_frames` | That duration at the atlas `fps`, rounded with Python's `round`. |
| `anchor` | `x`, `y` in the frame. Origin is the frame's top-left, y grows down. |
| `file` | Source filename, which `unpack` writes back. |
| `mode` | `RGB` or `RGBA`. |

The patch is a frame in `frames` and is not in the mouth's playback list.

## Anchors

The default is bottom-center:

```text
x = width // 2
y = height
```

A 14×12 cow is `(7, 12)`. `y = height` is the boundary under the last pixel row, so the feet sit on the ground line rather than in it. `x = width // 2` is integer division, so an even width anchors on the pixel just right of the midline.

Presets: `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`. An explicit `[x, y]` can sit outside the frame.

On a solid preview background, every frame's anchor is pinned to the same point and the canvas is the union. On an image, `--place` is that point (`place_space: anchor`) or the frame's top-left (`place_space: top-left`). If a sprite would stick out of the image, the canvas grows and the new pixels take the image's top-left color.

## Previews

The GIF is one image per pose. Duration is `duration_ms` rounded to a whole millisecond. Dither is off. If the preview uses 256 colors or fewer, the palette is those colors.

The MP4 repeats each pose for `hold_frames` at the atlas fps, which is the kit's clock. The cow's back pose is 400 ms, so `hold_frames` is 12, and the file is 24 frames at 30 fps (0.800 s): the other three poses are 4 frames each. `ffmpeg` encodes with `libx264rgb` at CRF 0 when that encoder exists, so the scaled pixels survive. Otherwise it falls back to `libx264` and `yuv420p`. Odd sizes get a one-pixel edge pad, because `yuv420p` needs an even size.

`--scale` is a whole number of at least 1. The blow-up is nearest neighbor, after the sprite has been drawn on the background.

## Unpack

```bash
python -m spritepack unpack examples/demo/out/demo.json -o /tmp/frames
```

Each rect is cropped and written under its `file` name. The tests compare those pixels to the sources, including alpha 0 with a nonzero RGB and a partial-alpha pixel.

## Intro kit

The kit does not read an atlas. It reads YAML and one PNG per frame. `adapt` unpacks the frames into `art/`, writes `mapping.yaml` (the annotated fragment), and writes `intro.yaml` (a project `python -m introkit validate` can load). The generated film is one second per mouth, then one second for the sprites, with a silent WAV of that length.

### What maps to what

| Packer | Intro kit |
| --- | --- |
| `file` | a path in `frames:` or `image:` |
| uniform `hold_frames` | `cycle.hold` |
| mixed `hold_frames` | `cycle.hold` is the greatest common divisor, and the longer pose is listed more than once |
| `cycle.mode`, `skip_last` | the same fields. `once` also gets `show_frames` covering the sprite scene |
| anchor at `kit_place` | `x = kit_place.x - anchor.x`, `y = kit_place.y - anchor.y`. Those are the kit's top-left |
| `kit_top_left` (Pixel Studio `offset`) | `x, y` as given. The anchor is not subtracted |
| mouth closed / open | `mouths.{shot}.closed` and `.open` |
| patch `x`, `y` and the open-frame crop | `mouths.{shot}.patch` |
| `hold_frames` on the closed plate | `vocals.hold_frames` |

The kit has one `cycle.hold` for the whole sprite, not a duration per frame. The cow in the demo is holds 4, 4, 4, and 12. The divisor is 4, so `intro.yaml` lists `cow_3.png` three times and sets `cycle.hold: 4`. At 30 fps that back pose stays up for 12 frames, which is the 400 ms from the sidecar.

The kit also has one top-left for the whole cycle. If the frames in one animation disagree about the anchor, the first frame's anchor is the one subtracted.

Default kit placement, when nothing sets `kit_place` or `kit_top_left`, plants the anchor at `(128, 200)` on the 256×224 plate. `--place name:x,y` on `adapt` overrides that, in anchor space. A background plate for the sprite scene is `--plate`, or a flat `(0, 0, 36)` plate when you don't pass one.

The demo cow is 14×12, anchor `(7, 12)`, `kit_place` `(160, 176)`:

```text
x = 160 - 7 = 153
y = 176 - 12 = 164
```

`176` is the ground line on `bg/hill_256.png`. The last pixel row of the cow is the row above it.

Mouth plates have to be 256×224 or the kit rejects them. The singer is that size. A smaller A/B pair is still described under `mouths:` in `mapping.yaml`, and `intro.yaml` places it as a sprite instead. The patch is the bounding box of pixels that differ, taken from the open frame. Pasting it onto the closed plate reproduces the open still. That is the kit's check, and it is the same rectangle Pixel Studio writes as `{shot}_open_patch.png`.

`vocals.hold_frames` flips the mouth: open for that many frames, closed for that many, and the last frame of the line is closed. The generated line runs `0.0` to `0.8` inside the mouth's one-second scene. Scrolls and stacks stay shut, same as the kit.

The generated `intro.yaml` sets `palette: off`. Snap to the PC Engine lattice in the kit if you want it. The demo colors are already on that lattice (`0, 36, 72, 109, 145, 182, 218, 255`), so the snap would not move a pixel.

## Demo

| File | What it is |
| --- | --- |
| `frames/cow_0.png` … `cow_3.png` | 14×12 RGBA. Right, front, left, back. Alpha is 0 or 255. |
| `frames/cow_3.png` | The back pose. The sidecar holds it for 400 ms. |
| `frames/singer_256.png` | Closed mouth, 256×224. |
| `frames/singer_open_256.png` | Open mouth. |
| `frames/singer_open_patch.png` | The differing rectangle at `116, 124`, 24×12. |
| `bg/pasture.png` | Preview ground. The cow's anchor is at `(48, 52)`, drawn at 8×. |
| `bg/hill_256.png` | Kit plate. The anchor is planted at `(160, 176)`. |
| `out/demo.png`, `out/demo.json` | The atlas and the JSON. Padding is 1. |
| `out/cow.gif`, `out/cow.mp4` | The turn, on the pasture. |
| `out/singer.gif`, `out/singer.mp4` | The mouth, at 2×. |
| `kit/intro.yaml` | A two-second intro the kit can validate. |

`python examples/demo/make_art.py` only redraws the PNGs and `sprites.json`.

## Tests

`python -m unittest discover -s tests` checks:

- The filename table above, including `cow_beam_0`, `{shot}_sprite_0`, `{shot}_00`, and `singer_open_256` not being frame 256.
- Two animations in one folder, in numeric order.
- A padded atlas unpacks to the same pixels, including alpha 0 with a nonzero RGB and a half-alpha pixel.
- Bottom-center of 14×12 is `(7, 12)`, and the demo plant point becomes kit `x: 153`, `y: 164`.
- A 400 ms override becomes 12 film frames at 30 fps, and the kit frame list repeats that pose.
- The mouth patch pastes back to the open plate.
- Preview scale 4 turns one pixel into a 4×4 block, and the MP4's first frame matches that block.
- A Pixel Studio manifest keeps `offset`, converts an 8 fps hold into 30 fps frames, and does not pack the background plate.

## Layout

```text
spritepack/          pack, unpack, preview, adapt
examples/demo/       cow, singer, sidecar, atlas, kit project
tests/
```
