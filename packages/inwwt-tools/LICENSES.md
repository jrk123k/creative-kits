# Licenses

The Python in this repository is MIT, below. The C64 typeface and the two
color palettes are other people's work and stay under their own terms.

## MIT License

Copyright (c) 2026 It's Not What We Thought tools

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The MIT grant covers this project's code. It does not cover the font file.

## C64 Pro Mono — Style

The screen generator draws with **C64 Pro Mono**, Style's TrueType recreation
of the Commodore 64 character set, version 1.2.1 (15 April 2019).

- File: `inwwt/fonts/C64_Pro_Mono-STYLE.ttf`
- Family name in the font: `C64 Pro Mono`
- Upstream: <http://style64.org/c64-truetype>
- Package: <https://style64.org/file/C64_TrueType_v1.2.1-STYLE.zip> (`fonts/C64_Pro_Mono-STYLE.ttf`)

The font file is unmodified and keeps the filename Style shipped. It is here
because the license allows that inside a software package given away free.
This repository is that package. The file is not offered as a standalone font
download, and it must not be renamed, sold, or dropped into a font collection.

If the file is missing, `inwwt` downloads that official zip and caches
`C64_Pro_Mono-STYLE.ttf`. Set `INWWT_C64_FONT` to point at a copy you
installed yourself.

License text embedded in the font and in `license.txt` from the v1.2.1 zip,
copied here without changes:

> Fonts in this package are (c) 2010-2019 Style.
>
> This license is applicable to each font file included in this package in all their variants (ttf, otf, eot, woff, woff2, svg).
>
> You MAY NOT: sell this font; include/redistribute the font in any font collection regardless of pricing; provide the font for direct download from any web site, modify or rename the font. You MAY: link to "http://style64.org/c64-truetype" in order for others to download and install the font; embed the font (without any modification or file renaming) for display on any web site using @font-face rules; use this font in static images and vector art; include this font (without any modification or file renaming) as part of a software package but ONLY if said software package is freely provided to end users. You may also contact us to negotiate a (possibly commercial) license for your use outside of these guidelines at "http://style64.org/contact-style".
>
> At all times the most recent version of this license can be found at "http://style64.org/c64-truetype/license".

The page at <http://style64.org/c64-truetype/license> says the same thing and
names the faces it covers: C64 User, C64 User Mono, C64 Pro, C64 Pro Mono,
and C64 Elite Mono.

Glyphs are read from the font outlines. Nothing in this repo is a Commodore
character-ROM dump.

## VIC-II palettes

These are measurements of a video signal, not a Commodore asset. The 16 sRGB
triples are stored in `inwwt/palette.py`.

**Pepto** (the default). Philip "Pepto" Timmermann, "All you ever wanted to
know about the colors of the Commodore 64" (2001):
<https://www.pepto.de/projects/colorvic/2001/>.
The same triples ship with the VICE emulator as `pepto-pal.vpl`. Order is the
VIC-II color register, 0 black through 15 light grey. Light grey is
`#959595`.

**Colodore**. Timmermann's later remeasurement, published at
<https://www.colodore.com/>. The site's brightness, contrast, and saturation
controls move the result, so the fixed values here are the ones VICE records
as "Colodore (PAL)" in `data/C64/colodore.vpl`
(<https://sourceforge.net/p/vice-emu/code/HEAD/tree/trunk/vice/data/C64/colodore.vpl>).

## Other tools

Rendering shells out to [FFmpeg](https://ffmpeg.org/) (the system build).
NumPy and Pillow are installed from PyPI and are not vendored. Pillow's
Floyd–Steinberg implementation is what `inwwt` runs on video frames; a
line-by-line version of the same filter lives in `inwwt/dither.py` for tests.
