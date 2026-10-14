# 16-bit intro kit

> Code created with Cursor and Grok Bots.

A config-driven TurboGrafx-CD style opener. One YAML file lists the song, the shots, and how the mouth, scroll, and sprites move. The renderer paints native **256×224** frames at the fps in the config (30 for both examples), optionally snaps them onto the PC Engine 9-bit palette, and ffmpeg scales with nearest neighbor to 1440×1080, pillarboxed to **1920×1080**.

The song is packet-copied (`-c copy`). It is not re-encoded. Silence, a code-written chiptune, or another audio file is appended after it for the title hold.

No network calls and no paid or AI APIs. You need Python 3, the packages in `requirements.txt`, and `ffmpeg` on `PATH`.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python -m introkit render examples/demo/intro.yaml -o dist/demo.mp4
python -m introkit render examples/demo/intro.yaml -o dist/demo.mp4
```

`examples/demo` is a synthetic intro with generated placeholder art, so it runs without the reference stills. `examples/demo/intro.yaml` is the reference cut: the same timeline, mouth windows, walk, hilltop cow, LOGO card, and title as reference cut. Key frames match that film pixel for pixel.

## For artists: what to draw

Copy `examples/demo` and point the YAML at your files. Paths are relative to the YAML file. Native size is exactly **256×224**. Do not deliver 2× art; the upscale happens in ffmpeg.

| Role | Size | Mode | Notes |
| --- | --- | --- | --- |
| Still plate (portrait, chair, viewscreen, title background, hill background) | 256×224 | RGB or opaque RGBA | One picture per shot. Hard cut to the next scene. No anti-aliasing, no soft edges. |
| Mouth, closed | 256×224 | RGB | The plate with the mouth shut. This is the picture used outside a vocal line. |
| Mouth, open still | 256×224 | RGB | Optional. The same plate with the mouth open. If you also give a patch, the kit pastes the patch onto the closed plate and **errors if that is not pixel-identical** to this still. |
| Mouth patch | as small as the changed pixels | RGB | Opaque rectangle. `x` and `y` are the top-left on the 256×224 plate. |
| Scroll tile | `tile_w` × 224 | RGB | The image width is the loop width. It must meet itself on the left and right edges. Height is exactly 224. |
| Bobbing sprite (the walk) | any, tight bounds | **RGBA** | Alpha 0 outside the character. Alpha is 0 or 255. A soft fringe will halo. |
| Moving sprite (saucer, beam, cow, critter) | any, tight bounds | **RGBA** | Same alpha rule. Partial alpha is allowed when you mean it (the soft beam is soft). |
| Foreground plate (the ridge) | 256×224 | RGBA | Opaque where it covers sprites, alpha 0 where the sky or the saucer should show through. |
| Title background | 256×224 | RGB | The kit draws the logo and the blinking prompt on top. Do not paint that text into the picture. |

Suggested names, matching the reference example: `{shot}_256.png` for plates, `{shot}_open_256.png` plus `{shot}_open_patch.png` for mouths, `{name}_sprite.png` for sprites, `{name}_tile.png` for scroll tiles. The YAML is what actually gets loaded; the names are a convention.

### Palette

Set `palette: tg16` to snap every output pixel onto the PC Engine lattice, 3 bits per channel:

`0, 36, 72, 109, 145, 182, 218, 255`

Paint on those levels and the snap changes nothing. `palette: "off"` (or bare `off`) leaves your pixels alone. reference cut is `off` because the stills are used as given.

Tips that keep a shot looking like a CD-ROM cutscene:

- A sprite on the real hardware is 16 colors, a background often 16 to 256. Stay in that range. One plate in the reference set is fine around 64.
- Hard pixel edges. No gradients, no unique near-blacks, no anti-aliased hair.
- One outline color, one shadow, one highlight. Reuse them across the shot.
- The prompt color in the reference title is `(0, 255, 218)` with outline `(72, 72, 109)`. If you use that cyan in the title background, the blink test cannot see the prompt.
- Mouth patches should only change the mouth. The closed plate and the open still are otherwise the same pixels.

### Mouth A/B

```yaml
mouths:
  portrait:
    closed: art/portrait_256.png
    open: art/portrait_open_256.png      # optional identity check
    patch:
      image: art/portrait_open_patch.png
      x: 118
      y: 124
```

You need `closed` plus either `open`, `patch`, or both. The film draws the patch pasted on the closed plate when both exist. Flip rate is `vocals.hold_frames` (default **4**): four frames of the open plate, four of the closed plate, at the config fps. The **last frame of every mouth line is closed**, even if the phase would have been open.

A mouth line that lands on a scene with no `mouth:` is an error. Put `mouth: false` on lines where nobody on screen is singing (the human "Alone.", a title card). Those lines do not open a mouth.

Mouth plates belong on `type: still` scenes. Scrolls and stacks stay shut.

### Vocals

Inline:

```yaml
vocals:
  hold_frames: 4
  lines:
    - { start: "0:00.0", end: "0:04.4", text: "Hello again, humans." }
    - { start: "1:30.4", end: "1:31.1", text: "Alone.", mouth: false }
```

Times are seconds, or `M:SS.s`.

Or a WhisperX-style JSON. The loader uses `word_segments` if present, otherwise each segment's `words`, otherwise the segments themselves. Each word needs `start` and `end`. A gap **greater than** `gap` seconds starts a new line; a gap at or under the threshold merges, including a gap equal to the threshold. `speaker` keeps only that speaker when the words have a `speaker` field.

```yaml
vocals:
  hold_frames: 4
  alignment: alignment.json
  gap: 0.35
  mouth: true
```

```json
{
  "word_segments": [
    {"word": "HELLO", "start": 0.20, "end": 0.50},
    {"word": "THERE", "start": 0.55, "end": 1.60}
  ]
}
```

`examples/demo/intro_alignment.yaml` loads `alignment.json` and produces the same mouth window as the inline demo.

### Shots

Scenes abut. The first starts at 0. The last ends at song duration + tail duration. A gap or an overlap is an error. `cut: hard` is the only transition. There is no dissolve between scenes.

**Still.** `image:` and/or `mouth:`. With a mouth and no image, the closed plate is the picture.

**Scroll.** Looping tile plus an optional bobbing sprite. `scroll_px_per_s` moves the tile left (the character reads as walking right). `direction: right` flips that. Bob and scroll use **film time** from frame 0, so a later visit to the same corridor continues the phase instead of restarting it. reference bobs `2` px at `2` Hz: `y + round(2 * sin(2π * 2 * t))`.

**Stack.** Layers from back to front: `image` or `sprite`.

A sprite can have:

- `x`, `y`, or `keys` with `t` (seconds from the **scene** start) or `frame` (absolute frame index) and `ease: linear` or `smoothstep`. After the last key the sprite holds.
- `frames` plus `cycle`. `mode: loop` with `hold` (default 4) cycles forever. `mode: once` spreads the frames across the show window. `skip_last` keeps the final frames for the pop.
- `show: [start, end]` in absolute times, or `show_frames: [start, end]`. End is exclusive.
- `parent`, `ox`, `oy`. The child sits on the parent's **rounded** position plus the offset, so a beam stays glued to a rising saucer.
- `recolor`: exact RGBA replaced with another RGBA, on every frame of that sprite.
- `pop`: the last `frames` of the show window. Either `image`, or a nearest-neighbor squash (`squash_h`, `canvas_h`, `paste_y`) plus an optional `flash` rectangle. `above: some_id` draws the pop after that later layer instead of in this sprite's slot. `y` overrides the keyframed y for the pop frame.

The reference hill is the reference for all of that: saucer eases from y=138 to y=101 over 2.0s, the beam is parented to it, the cow plays four poses once up the beam, squashes and flashes on the last frame above the saucer, and the ridge plate covers both.

**Title.** `background` is an `image` or a `color`. `text` entries use `font: logo` (beveled G, R, A, Y, C, E only) or `font: small` (4×6 uppercase, digits, and `. , ' ! ? -`, scaled by `scale`). `sheen` is a speed in pixels per frame; the reference card uses `3`. `fade_in` is a frame count of a fade up from black. `prompt` blinks `on_seconds` / `off_seconds` (0.5 / 0.5 in both examples). The names are `on_seconds` and `off_seconds` because bare YAML `on` and `off` are booleans.

### Audio and the chiptune

```yaml
audio:
  file: audio/song.mp3
  duration: 117.0          # optional; checked against ffprobe within 0.15s
  tail:
    duration: 10.0
    source: chiptune       # chiptune, silence, file, or none
    chiptune:
      key: D               # C, C#, Db, D, ...
      mode: minor          # minor or major
      bpm: 92
      speed: 1.5
```

`source: none` with `duration: 0` ends the film with the song. `silence` appends digital silence. `file` appends that file, trimmed or padded to `duration` (the tail is encoded; the song is still copied). `chiptune` plays the built-in 23-beat fallback phrase, transposed and time-scaled, then trimmed or padded to the tail. At D minor, 92 bpm, speed 1.5 the phrase is exactly 10.0s, which is the reference title.

The phrase is an original arrangement, not a transcription. Pitch tracking on the song's first 15 seconds did not hold a melody.

### What the MP4 is

Native frames go in as raw rgb24. The video filter is exactly:

```text
scale=1440:1080:flags=neighbor,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black
```

H.264 CRF 18, `yuv420p`, audio stream copy, `-shortest`. The picture length is `round((song + tail) * fps)` frames.

## Commands

```bash
python -m introkit validate examples/demo/intro.yaml
python -m introkit timeline examples/demo/intro.yaml
python -m introkit frame examples/demo/intro.yaml --time 0.4 -o out/frame.png
python -m introkit preview examples/demo/intro.yaml -o out/contact.png
python -m introkit mouth-log examples/demo/intro.yaml -o out/mouth_log.csv
python -m introkit render examples/demo/intro.yaml -o dist/demo.mp4
python examples/demo/make_art.py    # rebuild the placeholder pngs and the 6s song
```

`render --preset veryfast` is the same file with a faster x264 preset. The shipped films use `medium`.

## Tests

`python -m unittest discover -s tests` checks:

- The mouth is open only inside mouth windows, on the 4-frame phase, and the last frame of each line is closed.
- Outside those windows the mouth is closed (plate on screen) or off (no plate).
- The timeline covers the song plus the tail with no gaps, and the reference cut is 3810 frames (2:07.0).
- Word alignment merges and splits on the gap threshold.
- The reference open frames match the open stills, and 18 native frames match the v6 film.
- The demo MP4 is 1920×1080, about 8.0s, pillarboxed, and the song's MP3 packet sizes are the prefix of the joined audio.

## Layout

```text
introkit/          loader, fonts, chiptune, compositor, ffmpeg
schema/intro.schema.json
examples/demo/     placeholder art, inline vocals, alignment vocals
examples/demo/   v6 config, stills, mouths, cow, song
tests/
dist/              demo.mp4, demo.mp4, demo_contact.png, intro_kit_source.zip
```
