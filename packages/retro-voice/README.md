# It's Not What We Thought...

> Code created with Cursor and Grok Bots.

A small command-line singer: text goes in, a buzzy three-formant robot comes out, and a MIDI melody can be sung in two voices over an 8-bar beat.

The voice is a clean-room formant synthesizer. It is not the Commodore Software Automatic Mouth, and it does not contain those ports. Why that choice was made is written up in [LICENSES.md](LICENSES.md). The code in this repo is MIT. The only runtime dependency is NumPy.

## Run it

```bash
python -m pip install numpy
python -m pytest
python -m retro_voice demo all --out-dir demos
```

That writes:

- `demos/demo_spoken.wav` — three spoken lines, three voice presets
- `demos/demo_song.wav` — eight bars, drum machine, lead, and harmony
- `demos/stems/lead.wav`, `harmony.wav`, `beat.wav`
- `demos/lead.mid`, `demos/harmony.mid`, the `.rvscore` files, and `duet.json`

The song is rendered by reading those MIDI files back in. Tempo is 100 BPM, so a quarter note is exactly 0.6 seconds and the whole piece is 19.2 seconds.

## Speak

```bash
python -m retro_voice say "It's not what we thought." -o line.wav
python -m retro_voice say --phonemes "HH EH L OW" -o hello.wav
python -m retro_voice say --phonemes "HEHLOW" -o hello_sam.wav \
  --pitch 80 --speed 72 --mouth 170 --throat 120 --effects sam
```

`--phonemes` accepts spaced ARPAbet (`HH EH1 L OW`) or a jammed SAM-style string (`HEHLOW`). A few manual spellings are aliases: `OH`→`AO`, `UX`→`UW`, `NX`→`NG`, `H`→`HH`.

Pitch, speed, mouth, and throat are integers from 0 to 255.

| Knob | Center | What it does |
| --- | --- | --- |
| `--pitch` | 64 | Quarter-semitone steps. 64 is the written pitch when singing. |
| `--speed` | 72 | Higher is slower. |
| `--mouth` | 128 | Higher is brighter (upper formants up). |
| `--throat` | 128 | Higher raises the first formant. |

Presets: `sam`, `lead`, `harmony`, `deep`, `bright`.

## Sing

One syllable token per note. Hyphens split a word. A lone `-` holds the previous syllable across the next note.

```text
It's not what we thought to-night
thought - friend
glo- - ry
beau- ti- ful
[TH AO T]
```

`to-night` is two notes of the word "tonight". `thought - friend` holds "thought" on the middle note. `glo- - ry` is "glory" on three notes, the middle one a melisma. Brackets bypass the dictionary for that note.

A text score (`tune.rvscore`):

```text
tempo 100
preset lead
pitch 72
mouth 186
throat 108

C4 1 It's
E4 1 not
G4 1 what
E4 1 we
A4 2 thought
G4 1 to-
E4 1 night
```

```bash
python -m retro_voice sing --score tune.rvscore -o lead.wav --align
python -m retro_voice sing --midi demos/lead.mid --lyrics-file demos/lead.txt \
  --tempo 100 --preset lead --effects c64 -o lead.wav
```

`--tempo` locks the MIDI ticks to that BPM (a drum machine and a second voice can share it). Without `--tempo`, a file with one tempo uses that tempo. If the file changes tempo, the vocal follows the tempo map; the synthesized beat stays at the first tempo.

Polyphonic MIDI is folded to one line: the highest note sounding at each moment is the one that is sung. A new note cuts off the previous one.

Sung frequency is the MIDI note, then the pitch knob:

```text
sung_hz = note_hz * 2 ** ((pitch - 64) * 0.25 / 12)
```

The note lengths are the tempo. Speed does not move the bar line; it only changes how long the consonants are inside each note.

## Duet

`demos/duet.json` is the shape:

```json
{
  "tempo": 100,
  "bars": 8,
  "beat": true,
  "effects": "c64",
  "voices": [
    {"name": "lead", "midi": "lead.mid", "lyrics_file": "lead.txt", "preset": "lead", "gain": 0.82},
    {"name": "harmony", "midi": "harmony.mid", "lyrics_file": "harmony.txt", "preset": "harmony", "gain": 0.7}
  ]
}
```

```bash
python -m retro_voice duet --spec demos/duet.json -o mix.wav --stems-dir stems
```

Lead is brighter and a little sharp of the written notes (`pitch 72`, open mouth). Harmony is darker and a few semitones lower (`pitch 52`, closed mouth, higher throat). Stems are separate WAVs. The mix is lead + harmony + the 8-bar beat, then a single peak normalize.

The beat is code: kick, snare, hats, and a square-wave bass in C. It is eight bars of 4/4.

## Effects

The chain, in order: ring mod, resonant filter, sample-and-hold, bitcrush, chorus.

```bash
python -m retro_voice say "It's not what we thought." -o crushed.wav \
  --effects off --bitcrush 6 --downsample 3 \
  --filter bp --cutoff 1400 --resonance 0.7 \
  --ring 35 --ring-mix 0.25 --chorus 0.2
```

| Preset | Character |
| --- | --- |
| `off` | Dry formant voice. |
| `sam` | 8-bit, hold-by-2, band-pass around 1.5 kHz. Used on the spoken demo. |
| `c64` | 8-bit, hold-by-2, resonant low-pass, a little chorus. Used on the duet. |

The filter is a state-variable low-pass / band-pass / high-pass with a resonance control. It is not a SID emulator.

## The demo lyric

Lead, over all eight bars:

> It's not what we thought tonight, a tin voice in the wires sang what we wrote on the bench. It's not what we thought, friend.

"Thought" near the end is held across two notes (`thought - friend`).

Harmony answers underneath:

> We know it's not what we thought. Sing it back. Hold on. It's not true.

Placeholder words, written for this project.

## Tests

```bash
python -m pytest
```

The tests cover hyphen and melisma alignment, SAM and ARPAbet phoneme strings, MIDI round-trip (including chords and overlaps), sung pitch against the note, tempo locking, mouth brightness, the effects chain, and the CLI.
