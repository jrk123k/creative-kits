# creative-kits

> Code created with Cursor and Grok Bots.

Public monorepo of reusable creative CLI / kit tools for AI music-video and retro-style production.

**Proposed repository name:** `creative-kits` (public), under the GitHub account that owns this staging.

This tree is a **local staging** copy only. Nothing has been pushed.

## Packages

| Package | What it does |
| --- | --- |
| `16bit-intro-kit` | YAML-driven 16-bit style intro renderer (Python + ffmpeg). |
| `pixel-studio` | Browser pixel studio + palette snap CLI. |
| `sprite-packer` | Sprite discovery, packing, mouth timing, previews. |
| `chiptune-cli` | MML → PSG-style chiptune WAV. |
| `retro-voice` | Original formant synth for speech/singing (MIT; not SAM). |
| `inwwt-tools` | C64 screen / CRT / compositor tools for *It's Not What We Thought...*. Free package; includes Style C64 Pro Mono under its font terms. |
| `continuity-checker` | Lore / voice-bible / VO-fit checker (v2). Samples sanitized for public. |
| `film-filter` | ffmpeg bash filter for 1920s silent-film look (`silentfilm.sh`). |
| `overlay-kit` | Remotion HUD overlay for music videos. **Song audio not shipped** (bring your own under `assets/audio/`). |

## Not in this repo

Private ops tools (box transfer helpers, PM board, contribution checkers, scrub rule lists, continuity paste tooling), large demo videos/archives, and personal project media stay off this tree.

## License

Project-authored code is MIT (root `LICENSE`). Third-party fonts and Remotion keep their own terms — see `docs/THIRD_PARTY.md` and each package's `LICENSE` / `LICENSES.md`.

## Quick start

Each package is self-contained. Open `packages/<name>/README.md` for install and run steps. Typical needs: Python 3.11+, ffmpeg on PATH; overlay-kit also needs Node 20+.
