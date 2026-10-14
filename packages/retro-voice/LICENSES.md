# Licenses and provenance

Checked 11 October 2026. This project does **not** include Software Automatic Mouth (SAM), Reciter, or any port of them.

The singing voice in *It's Not What We Thought...* is an original formant synthesizer. It aims at the same kind of sound — a small, buzzy, three-formant robot — and it accepts the same style of controls and phoneme spellings. It does not contain SAM's code, coefficient tables, or reciter rules.

## What we ship

| Piece | License | Where it comes from |
| --- | --- | --- |
| This repository (`retro_voice/`, tests, demo scores) | MIT. See `LICENSE`. | Written for this project. |
| NumPy | BSD-3-Clause | Installed from PyPI. Not vendored. |

No audio models, no API keys, no paid services, and no prebuilt speech binaries.

## SAM ports we looked at and did not use

The original SAM was commercial software. Don't Ask, Inc. published it in 1982 (Mark Barton; the manual's license text is reproduced in the discordier/sam tree). That license was personal-use only. It forbids reproducing the program or incorporating it into another program that is transferred to other people. SoftVoice, Inc. still describes itself as the current rights holder and still offers a paid text-to-speech license at <https://www.text2speech.com/>.

The widely circulated "open" ports are disassemblies, not clean-room rewrites. Their authors say so, and they deliberately do not grant an open-source license:

- **s-macke/SAM** (C, the usual ancestor): <https://github.com/s-macke/SAM>. The README says the program was converted from a 6502 disassembly and that the author "cannot put [the] code under any specific open source software license." Abandonware and a "fair use" hope are not a license.
- **vidarh/SAM** (cleaned-up C): <https://github.com/vidarh/SAM>. Same statement. Names SoftVoice, Inc. as the copyright holder.
- **discordier/sam** and the npm package **sam-js**: <https://github.com/discordier/sam>, <https://www.npmjs.com/package/sam-js>. The package says `SEE LICENSE IN README.md`. The README says there is no open-source license and to use it at your own risk. It is a hand translation of the Macke / Hokstad C code.
- **jacklinquan/samtts** (Python): <https://github.com/jacklinquan/samtts>. `License: None`. Same lineage, same refusal to add a license.

Forks that later paste an MIT file onto that code do not clear the original work. We did not vendor, translate, or read those synthesizer sources while writing this one.

## Clean-room option we also did not link

**eSpeak NG** (<https://github.com/espeak-ng/espeak-ng>) is a real open-source formant synthesizer, GPL-3.0-or-later. It would have been a lawful engine. We did not shell out to it or link it: the GPL would cover this tool, and eSpeak's pitch controls are not a note-for-syllable singer locked to a MIDI tempo. The voice here had to hold exact equal-tempered pitches for a duet.

## How this synthesizer was written

- Parallel formant synthesis is a published technique (Dennis Klatt, "Software for a cascade/parallel formant synthesizer," *Journal of the Acoustical Society of America*, 1980, describes the structure). The resonator in `synth.py` is the ordinary two-pole digital resonator: radius from bandwidth, cosine from frequency. It is not a transcription of Klatt's Fortran or of SAM's integer tables.
- Vowel frequencies in `phonemes.py` are rounded adult-male averages in the ranges reported by acoustic phonetics (Peterson & Barney; Hillenbrand et al.). Bandwidths, durations, and the mouth/throat mapping are original.
- The English lexicon in `g2p.py` was written for the demo and a few common words. It is not the CMU dictionary and not SAM's reciter. Unknown words go through letter rules written here.
- SAM phoneme *spellings* (`HEHLOW`, `OH`, `NX`, …) are accepted as an input alphabet because those names were published in the user manual. They are mapped onto our own targets. ARPAbet spellings are accepted the same way.
- The resonant filter is the Chamberlin state-variable structure (low-pass, band-pass, high-pass). The equations are standard and public. This is not reSID and not any other SID emulator.
- MIDI reading and writing follow the Standard MIDI File layout. There is no third-party MIDI library.

## Knobs, and what they do here

The manual's ranges are the user interface people already know. Center values match that manual: pitch 64, speed 72, mouth 128, throat 128.

- **Pitch.** Each step away from 64 is a quarter semitone. In speech this sets the base pitch. In singing the note (or MIDI pitch) is exact, then this knob transposes it: `sung_hz = note_hz * 2 ** ((pitch - 64) * 0.25 / 12)`. Pitch 64 sings the written note.
- **Speed.** Higher is slower, matching SAM's hold-counter. It stretches speech. In singing, the note grid stays locked to tempo; speed only changes how much of each note the consonants occupy.
- **Mouth.** Higher raises the second and third formants (smaller, brighter mouth). Lower darkens them.
- **Throat.** Higher raises the first formant. Lower deepens it.

Those mappings are ours. They are not SAM's internal frequency-table offsets.
