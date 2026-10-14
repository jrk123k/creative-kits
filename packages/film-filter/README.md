# Silent-film finishing filter (1920s look)

> Code created with Cursor and Grok Bots.

Pure ffmpeg + bash (box ffmpeg 7.1.5; filters used: fps, scale, crop, eq, colorchannelmixer, curves, noise, drawbox, vignette). No Node/Chromium.

    ./silentfilm.sh [-p light|standard|heavy] [-v 0|1] [-f FPS] <folder-or-mp4> <out_dir>

Output: `<name>_silent_<preset>.mp4`, H.264 CRF 18, yuv420p, 1280x720 (16:9), audio stripped. Originals are never modified.

| knob | what | light | standard | heavy |
|---|---|---|---|---|
| FPS | frame cadence (drops frames, same duration) | 18 | 17 | 16 |
| GRAIN | noise strength | 8 | 14 | 22 |
| SAT | saturation | 0.75 | 0.6 | 0.45 |
| FLICK | random brightness flicker | 0.02 | 0.04 | 0.07 |
| WEAVE / JIT | gate weave px (sine) / random jitter px | 1.5/1 | 3/2 | 5/4 |
| SCR | scratch line opacity | 0.15 | 0.25 | 0.4 |
| DUST | dust speck opacity | 0.25 | 0.45 | 0.7 |
| TINT | warm sepia/pastel blend (0–1) | 0.6 | 0.8 | 1.0 |

`-v 0` disables the vignette; `-f` overrides FPS. Edit the `case` block to add presets.
Weave uses a 5% overscan crop. Scratches and dust are pseudo-random per frame and repeatable.
