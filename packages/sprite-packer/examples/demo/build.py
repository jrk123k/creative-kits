"""Rebuild the demo atlas, previews, and intro-kit project.

    python examples/demo/build.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))

from examples.demo.make_art import generate
from spritepack.adapt import adapt_file
from spritepack.build import pack_folder


def main() -> None:
    generate(ROOT)
    built = pack_folder(
        ROOT / "frames",
        ROOT / "out",
        name="demo",
        padding=1,
        max_width=270,
    )
    intro = adapt_file(
        built.json_path,
        ROOT / "kit",
        plate=ROOT / "bg" / "hill_256.png",
        name="kit-demo",
    )
    print(f"wrote {built.atlas_path}")
    print(f"wrote {built.json_path}")
    for path in built.previews:
        print(f"wrote {path}")
    print(f"wrote {intro}")


if __name__ == "__main__":
    main()
