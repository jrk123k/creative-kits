"""HuC6280 chiptune renderer.

``render_score`` and ``render_preset`` return stereo float32 audio.
``synthesize`` matches the intro kit's title-cue function.
"""

from chip.kit import METHOD, REASON, SR, fit, note_pc, phrase_seconds, synthesize
from chip.render import list_presets, render_preset, render_score, write_audio
from chip.tables import STOCK_NAMES

__all__ = [
    "METHOD",
    "REASON",
    "SR",
    "STOCK_NAMES",
    "fit",
    "list_presets",
    "note_pc",
    "phrase_seconds",
    "render_preset",
    "render_score",
    "synthesize",
    "write_audio",
]
