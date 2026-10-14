# chip

> Code created with Cursor and Grok Bots.

A small chiptune and sound-effect renderer aimed at the PC Engine / TurboGrafx-16. You write a text score. `chip` plays it on a 6-channel model of the HuC6280 PSG and writes a stereo WAV or OGG.

It is the piece the 16-bit intro kit can call for a title tail. The kit's old `introkit/chiptune.py` oscillators are replaced by this PSG, behind the same `synthesize()` function. The notes are still that original 23-beat phrase, not a transcription of anyone's song.

Accuracy is "sounds like a PC Engine," not cycle-exact. No DDA streaming. The clock, the scale table, the noise LFSR, and the LFO shifts follow the Hudson manual and the same structure as Geargrafx.

You need Python 3.11+, `numpy`, `soundfile`, and `ffmpeg` only if `soundfile` cannot write Vorbis by itself.

```bash
pip install -e .
python -m unittest discover -s tests

chip render examples/score.mml -o out.wav
chip preset beam_hum -o beam.ogg
chip preset title_loop -o title.wav --loop-length 10
```

If `chip` is not on `PATH` (a user install lands in `~/.local/bin`):

```bash
python -m chip render examples/score.mml -o out.wav
```

## For artists

Channels are **uppercase A–F**. Notes are **lowercase a–g**. A line that starts with `C` is channel C, not the note C. `c4` is middle C, a quarter note, once you are on a channel.

A is PSG channel 1 and B is channel 2. Those two are the LFO pair: A is the carrier, and `lw` chooses the modulator shape. E and F are channels 5 and 6, the only ones that can play noise.

Drop a new cue in `chip/presets/your_name.mml` and it shows up as `chip preset your_name`. Keep the file name to letters, digits, and underscores.

## Presets

| Name | What it is | Length |
| --- | --- | --- |
| `beam_hum` | UFO tractor beam. Low sine, slow deep LFO, a quiet fifth, two noise beds. The file loops. | 6.0 s |
| `blips` | UI: cursor, cursor, confirm arpeggio, cancel ticks. | 2.1 s |
| `jingle` | Four bars in C. Pulse lead, organ, triangle bass, hat, backbeat. | 6.7 s |
| `sting` | E-minor stab, falling saw, noise crack. | 1.2 s |
| `title_loop` | The 23-beat D-minor title phrase. At 138 BPM it is exactly 10.0 s and the file starts and ends in silence, so a player can loop it. | 10.0 s |

```bash
chip presets
chip preset sting -o sting.wav
chip preset title_loop -o title_20s.wav --loops 2
```

## Commands

```text
chip render SCORE.mml -o OUT.wav
chip render SCORE.mml -o OUT.ogg --loops 4
chip render SCORE.mml -o OUT.wav --loop-length 8.0
chip preset NAME -o OUT.ogg
chip preset NAME -o OUT.wav --tempo 120 --loop-length 10
chip presets
chip wavetables
```

| Flag | Meaning |
| --- | --- |
| `-o`, `--output` | `.wav` (16-bit PCM) or `.ogg` (Vorbis). Stereo, 44100 Hz unless you change `--sr`. |
| `--loops N` | Play the loop region N times. Default 1. Material before `\|` is the intro and plays once. |
| `--loop-length SEC` | Repeat the loop until the file covers SEC seconds, then trim to that length. This wins over `--loops`. A hard trim fades the last 8 ms unless the score is seamless, in which case the join is crossfaded instead. |
| `--tempo BPM` | Play the whole score at this tempo. A `t` change inside a channel scales with it. |
| `--seamless` / `--no-seamless` | Force the loop crossfade on or off. Default is whatever `@seamless` says. |
| `--sr` | Sample rate. Default 44100. The intro kit wants 44100. |

The returned level is normalized so the peak sits at about 0.89. A silent score stays silent.

## Score syntax

Comments are `;` or a `#` that starts a token. Blank lines are ignored. A channel can run onto the following lines until the next uppercase `A`–`F` line.

```text
@title Night window
@tempo 120          ; quarter-note BPM
@master 15 15       ; global left and right, 0..15, 15 is loudest
@seamless           ; crossfade the wrap if the edges are still hot
@wave 6 saw         ; copy a stock table into slot 6
@wave 7 0,2,4,...,31   ; or write 32 samples, each 0..31

A | o5 v28 w pulse p15,12 q6 l8
  c e g >c r4
B o4 v18 w organ p10,15 q8 l2 c g
E n1 nf18 v14 p12,12 q8 l8 [c r]4
```

`|` is the loop point. Put it at the same time on every channel that uses it. Channels without `|` still split there. With no `|` anywhere, `--loops` repeats the whole score.

### Directives

| Directive | Meaning |
| --- | --- |
| `@title TEXT` | Name, stored on the score. Not heard. |
| `@tempo BPM` | Starting tempo for every channel. One of these, up top. |
| `@master L R` | Main volume, the PSG's R1. Each side is 0..15 in 3 dB steps. 0 is mute. |
| `@seamless` | Ask the renderer to make a loop wrap click-free. |
| `@wave ID NAME` | Copy stock `NAME` into slot `ID` (0..31). |
| `@wave ID s0,s1,...,s31` | Replace that slot with 32 samples, each 0..31. |

### Stock wavetables

Slots 0–5 are loaded into every score. `chip wavetables` prints the same numbers. `w square` and `w0` are the same thing.

| ID | Name | Shape |
| --- | --- | --- |
| 0 | `square` | 16 samples at 31, 16 at 0 |
| 1 | `saw` | 0,1,2,…,31 |
| 2 | `triangle` | 0,2,4,…,30,31,29,…,1 |
| 3 | `organ` | soft additive wave, fundamental plus a little octave and twelfth |
| 4 | `pulse` | 8 samples at 31, 24 at 0 (25% pulse, good for a lead) |
| 5 | `sine` | 5-bit sine |

Organ, as written into the PSG:

```text
16,22,28,31,31,29,27,25,23,22,21,20,19,18,17,16,16,15,14,13,12,11,10,9,8,6,4,2,0,0,3,9
```

Overwriting slot 3 with `@wave 3 ...` replaces `organ` for that score only.

### Channel commands

Whitespace is ignored. A number after a command can be an integer. Note lengths can also be decimals (`d1.25`).

| Command | Meaning |
| --- | --- |
| `a`–`g` | Note. `#` or `+` sharpens, `-` flattens. Optional length, then dots: `c4`, `c#8.`, `f1.25`. |
| `r` | Rest. `r4`, `r1`, `r8.` |
| `l N` | Default length. `l8` makes later notes eighths. `l8.` is a dotted eighth. Lengths are the usual MML fraction of a whole note: 1 whole, 2 half, 4 quarter, 8 eighth, 16 sixteenth. |
| `o N` | Octave 0..8. `o4` is the octave of middle C. C4 is MIDI 60. |
| `<` `>` | Octave down, octave up. |
| `v N` | Channel volume 0..31 (PSG R4). 31 is loudest, about 1.5 dB per step. 0 is mute. |
| `p L,R` | Balance 0..15 per speaker (PSG R5). 3 dB per step. `p15,15` is center, `p15,0` is hard left, `p0` sets both sides. |
| `w ID` or `w NAME` | Wavetable for the notes that follow. |
| `q N` | Gate, 1..8. The note sounds for N/8 of its time. Default 8, the whole note. `q6` is a detached lead. |
| `t BPM` | Tempo from here, this channel only. |
| `&` | Tie. The previous note plays through its full length (the gate opens up) and the next note does not re-attack. `c4 & c4` is a half note. `c4 & e4` is legato. |
| `[ ... ]N` | Repeat the bracket N times. N defaults to 2. Nesting is fine. `[c e]3` is six notes. |
| `\|` | Loop point, once per channel. |
| `n0` `n1` | Noise off / on. **E and F only.** |
| `nf N` | Noise pitch 0..31. **E and F only.** Higher is higher. This also turns noise on. |
| `lf N` | LFO depth on **A only**. 0 off, 1 add, 2 shift the modulator 2 bits, 3 shift it 4 bits. |
| `lr N` | LFO rate register 0..255. 0 means 256. |
| `ld N` | Modulator period 1..4095. This is channel 2's frequency register. |
| `lw ID` or `lw NAME` | Modulator wavetable. Default `sine`. |

A new note after silence gets a 1.5 ms fade-in, and a note that ends into silence gets a 1.5 ms fade-out, so a raw wavetable step does not click. A seamless drone that fills the whole loop does not fade, or the loop would dip.

### Pitch, noise, LFO

Tone frequency, with the PSG clock at 3.58 MHz (half of the 7.16 MHz CPU clock):

```text
Hz = 3580000 / (32 * F)
```

`F` is the 12-bit register, 1..4095. A4 lands on 254 and C4 on 428, which is the Hudson scale table. You write notes; the renderer computes `F`.

Noise is an 18-bit LFSR (taps at bits 0, 1, 11, 12, 17), not the channel's wavetable. The period in PSG clocks is 32 when the low 5 bits are all 1, otherwise `(bitwise-not of those bits, masked to 5 bits) << 6`. The seed is fixed, so a render is repeatable. E and F use different seeds.

The LFO steps through `lw` once every `ld * lr` PSG clocks. One full pass of the 32 samples is:

```text
Hz = 3580000 / (32 * ld * lr)
```

Each modulator sample is treated as signed (value minus 16, so the range is −16..+15) and added to A's period after the shift from `lf`. A bigger period is a lower note. `lf3` with a full-range triangle is a deep siren. `beam_hum` uses a shallow triangle in slot 6 so the beam stays a hum, about a minor third of wow every two seconds.

Volume is logarithmic, then the speakers are summed. Any stage at 0 (channel, that side of the pan, or that side of `@master`) mutes that speaker. About 45 dB down is silence too.

## Calling it from Python

```python
from chip import render_preset, render_score, write_audio

beam = render_preset("beam_hum", loop_length=4.0)   # float32, shape (n, 2)
write_audio("beam.ogg", beam)

score = render_score("cues/confirm.mml", loops=2, seamless=True)
write_audio("confirm.wav", score)
```

`render_score` accepts a file path or the MML text itself. Keyword arguments match the CLI: `loops`, `loop_length`, `seamless` (`None` follows `@seamless`), `tempo`, `sr`. `normalize=False` leaves the PSG gains alone, which is what the tests use when they measure a 9 dB volume step.

## Plugging it into the intro kit

The kit's title tail imports four names from `introkit.chiptune`. Point those imports here and install this package on the same `PYTHONPATH`.

`introkit/encode.py`:

```python
from chip.kit import METHOD, REASON, SR, fit, synthesize
```

`introkit/project.py`:

```python
from chip.kit import note_pc, phrase_seconds
```

`synthesize(key, mode, bpm, speed)` still returns stereo float32 at 44100 Hz, peak at or under 0.9. `fit(audio, seconds)` still trims or pads, and a trim that cuts more than 50 ms fades the last 10 ms. `phrase_seconds(92, 1.5)` is still exactly 10.0, because the phrase is still 23 beats.

`key` is `C`, `C#`, `Db`, `D`, and the rest of the chromatic names. `mode` is `minor` or `major`. Major lifts the minor-scale degrees the same way the old file did, so a written F becomes F#. `bpm` and `speed` multiply: 92 × 1.5 = 138, which is the tempo written in `chip/presets/title_loop.mml`.

The samples will not match the old oscillator render. The lead is the 25% pulse, the harmony is the square, the bass is the triangle, and the ticks are PSG noise. `METHOD` is `"psg"`. The kit writes that into the chiptune note next to the mix.

Anything that is not the title phrase — a beam, a sting, a blip — goes through `render_preset` or `render_score` instead of `synthesize`.

## Tests

```bash
python -m unittest discover -s tests
```

They check the Hudson A4/C4 registers, that a rendered A4 sits on 440.45 Hz, the 1.5 dB volume steps, hard-left pan, silence at volume 0, LFO pitch movement, noise only on E and F, the 23-beat title at exactly 10.0 s with a quiet loop join, a click-free beam wrap, `--loop-length`, deterministic renders, the kit's `synthesize` / `fit` contract, and a real WAV plus OGG from the CLI.

## Layout

```text
chip/cli.py            argument parser
chip/score.py          MML parser
chip/psg.py            clock, dividers, LFSR, volume
chip/render.py         mix, loop, WAV/OGG
chip/tables.py         square, saw, triangle, organ, pulse, sine
chip/kit.py            intro-kit synthesize / fit / phrase_seconds
chip/presets/*.mml     beam_hum, blips, jingle, sting, title_loop
examples/score.mml     one-bar score for the render command
tests/test_chip.py
```
