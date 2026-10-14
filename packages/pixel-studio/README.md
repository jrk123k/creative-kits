# Pixel Studio

> Code created with Cursor and Grok Bots.

A local pixel editor for the 16-bit intro kit. Plates stay **256×224**. Sprites stay tight RGBA. The palette stays locked. There is no build step and no network load: open the page, paint, and drop the PNGs into a kit project.

`palette_snap/palette.py` is the intro kit’s `palette.py`, copied verbatim. The TG16 clamp is that file’s `snap_image` (3 bits per channel: `0, 36, 72, 109, 145, 182, 218, 255`).

## Run the studio

```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests
cd studio
python3 -m http.server 8741
```

Then open [http://127.0.0.1:8741](http://127.0.0.1:8741).

The page loads the TG16 master palette and the singer mouth sample. **Singer sample** is the 256×224 closed/open pair. **Walker sample** is a 4-frame sprite on `hill_bg_256.png`.

You need a current browser. Python’s static server is only there to serve the files. The editor itself is `studio/index.html`, `studio.css`, `studio.js`, and `zip.js`.

## Paint a shot

1. **New** → 256×224 for a plate, or a small size for a sprite. Or **Load frames** / **Load folder** (PNG, multi-file). Frames are sorted by filename. A frame that is not the size of the first one is resampled with nearest neighbor.
2. The swatches on the right are the only colors the pencil and fill will write. Load them from a PNG (unique opaque colors, most frequent first, capped at 256) or from JSON:

   ```json
   { "name": "shot", "colors": [ { "name": "lip", "rgb": [145, 109, 145] } ] }
   ```

   A bare list of `[r, g, b]` or `#rrggbb` works too. **TG16 JSON** restores the kit palette. **TG16 PNG** is the same colors as a strip, if you want to test the PNG loader.
3. Tools: **B** pencil, **E** eraser (sets alpha to 0, keeps the RGB), **G** fill, **I** eyedropper. Right-click also picks. If the pixel is not in the palette, the eyedropper selects the nearest OKLab swatch. Undo is Ctrl+Z, redo is Ctrl+Shift+Z or Ctrl+Y. Brush is 1, 2, or 4 pixels, anchored at the top-left of the cursor.
4. **Snap frame** / **Snap all** map opaque pixels onto the locked palette in OKLab. **Bayer** is the same 8×8 lightness dither as the CLI. **TG16** clamps through the 9-bit lattice. Alpha 0 pixels are left alone. The badge counts opaque pixels that are not in the palette.
5. Editor zoom is for drawing. The preview’s **1× / 4× / 8×** buttons are nearest-neighbor, which is what ffmpeg does later.

## Preview, onion skin, mouth flap

The preview loops the filmstrip at the fps slider (the kit’s films are usually 30; the samples use 12 and 8 so the flap is easy to see). **Onion skin** draws the previous frame over the current one. On a mouth pair it draws the other pose, so the lip change stays visible even when the plate is opaque.

**Background** puts a plate behind the frames. **x / y** is where the frame sits on that plate. The walker sample is already lined up on the hill.

**Mouth A/B** flips the closed frame and the open frame. Each one holds for N frames. N defaults to **4**, which is `vocals.hold_frames` in the kit. The readout under the preview says `CLOSED · 2/4` or `OPEN`. The last-frame-of-the-line rule is the kit’s, not the loop’s: the loop just alternates.

The YAML block is the `mouths:` entry. **Mouth patch** saves the bounding box of pixels that differ, taken from the open frame, as `{shot}_open_patch.png`. Pasting that rectangle onto the closed plate reproduces the open still. Copy the `x` and `y` into the kit YAML.

**Ghost** does the same onion overlay on the drawing canvas.

## Save

The shot field is the filename stem.

| Names | Files |
| --- | --- |
| Plate pair | `{shot}_256.png`, `{shot}_open_256.png`, other frames `{shot}_{name}.png` |
| Sprite frames | `{shot}_sprite.png`, or `{shot}_sprite_0.png`, `{shot}_sprite_1.png`, … |
| Numbered | `{shot}_00.png`, `{shot}_01.png`, … |

- **This frame** downloads the current PNG.
- **All frames** downloads a zip of those names.
- **Sprite sheet** is a horizontal strip (it wraps near 4096px). The kit does not load the sheet; it is for checking the cycle.
- **Mouth patch** is `{shot}_open_patch.png`.

Put the PNGs in the kit project’s `art/` folder and point the YAML at them. Paths in the YAML are relative to the YAML file. Do not deliver 2× art.

Kit reminders, from the intro kit README:

- Still plates and mouth plates are 256×224, opaque, hard edges, no anti-aliasing.
- A mouth patch is only the pixels that changed. `x` and `y` are the top-left on the plate.
- Sprites are RGBA. Alpha is 0 or 255 unless you mean a soft fringe (the kit allows that on purpose, as with the beam).
- A background is often 16 to 256 colors. A sprite on hardware is 16. Reuse one outline, one shadow, one highlight.
- Do not paint the title logo or the blinking prompt into the title background. The prompt color `(0, 255, 218)` is reserved for that test.

Regenerate the bundled samples with `python3 scripts/make_samples.py`.

## palette_snap

Snap a picture to N colors taken from a reference frame. Distance is OKLab. Alpha is copied. Pixels with alpha 0 keep their RGB. `--dither` is ordered Bayer 8×8 on OKLab lightness: strength 1 does not knock an exact palette color off its cell, and a midpoint between black and white splits into both. `--tg16` clamps the palette and the output with `snap_image`.

```bash
python3 -m palette_snap photo.png -o art/portrait_256.png \
  --reference art/singer_256.png --colors 16 --tg16

python3 -m palette_snap photo.png -o art/portrait_256.png \
  -r art/singer_256.png -n 16 --dither --tg16 \
  --palette-out art/portrait_palette.json
```

`--colors` defaults to 16. The reference defaults to the input. Colors are the most frequent opaque pixels, ties broken by first appearance. If the reference has fewer than N colors, you get all of them. The line on stderr reports the size and the count actually used.

Output is an RGBA PNG. Channels are unchanged where alpha is 0.

## Tests

```bash
python3 -m unittest discover -s tests
```

The tests check the OKLab choice against RGB distance, the Bayer split, alpha, the N-color cap, the TG16 lattice, the CLI, the byte-for-byte intro-kit `palette.py`, and the sample plates (patch paste identity, walker alpha 0/255, 256×224 plates).

## Layout

```text
palette_snap/     CLI and OKLab snap; palette.py is the intro kit file
studio/           static editor (index.html, studio.js, studio.css, zip.js)
studio/palettes/  tg16.json and tg16.png
studio/samples/   singer plates, patch, walker, hill
scripts/make_samples.py
tests/
```
