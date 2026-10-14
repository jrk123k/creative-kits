"""PC Engine / TurboGrafx-CD 9-bit color (3 bits per channel).

Hardware levels are v * 255 // 7 for v in 0..7:
0, 36, 72, 109, 145, 182, 218, 255.

`snap_image` quantizes a frame onto that lattice (the optional `tg16` mode).
`fade_image` is the indexed fade used by the title card: mix toward black,
snap to the lattice, then pick the nearest entry in the master palette below.
Index 0 is transparent on sprites and black if it reaches the framebuffer.
"""

from __future__ import annotations

import numpy as np

LEVELS = (0, 36, 72, 109, 145, 182, 218, 255)

# name -> RGB already on the 9-bit lattice. Index 0 is reserved (transparent).
_NAMED = [
    ("black", (0, 0, 0)),
    ("white", (255, 255, 255)),
    ("steel0", (36, 36, 72)),
    ("steel1", (72, 72, 109)),
    ("steel2", (109, 109, 145)),
    ("steel3", (145, 145, 182)),
    ("steel4", (182, 182, 218)),
    ("steel5", (218, 218, 255)),
    ("skin0", (109, 109, 145)),
    ("skin1", (145, 145, 182)),
    ("skin2", (182, 182, 218)),
    ("skin3", (218, 218, 255)),
    ("suit0", (36, 72, 72)),
    ("suit1", (72, 109, 109)),
    ("suit2", (109, 145, 145)),
    ("suit3", (145, 182, 182)),
    ("suit4", (182, 218, 218)),
    ("suit5", (218, 255, 255)),
    ("lip", (145, 109, 145)),
    ("mouth", (36, 0, 36)),  # open-mouth interior only
    ("wall0", (72, 109, 145)),
    ("wall1", (109, 145, 182)),
    ("wall2", (145, 182, 218)),
    ("wall3", (182, 218, 218)),
    ("wall4", (218, 218, 255)),
    ("floor0", (36, 72, 109)),
    ("floor1", (72, 109, 145)),
    ("floor2", (109, 145, 182)),
    ("light", (218, 255, 255)),
    ("screen", (0, 0, 109)),
    ("screen2", (0, 36, 145)),
    ("cyan", (0, 218, 255)),
    ("cyan2", (0, 145, 218)),
    ("amber", (218, 145, 0)),
    ("orange", (255, 109, 0)),
    ("red", (218, 0, 0)),
    ("red2", (145, 0, 0)),
    ("green", (0, 182, 72)),
    ("blue", (0, 109, 218)),
    ("navy", (0, 36, 109)),
    ("ocean0", (0, 36, 109)),
    ("ocean1", (0, 72, 182)),
    ("ocean2", (0, 109, 218)),
    ("ocean3", (36, 145, 218)),
    ("land0", (36, 109, 36)),
    ("land1", (36, 145, 72)),
    ("land2", (109, 145, 72)),
    ("land3", (145, 109, 72)),
    ("land4", (182, 145, 109)),
    ("cloud", (218, 218, 255)),
    ("ice", (255, 255, 255)),
    ("sky0", (0, 0, 36)),
    ("sky1", (0, 0, 72)),
    ("sky2", (0, 36, 109)),
    ("sky3", (0, 72, 145)),
    ("star", (255, 255, 255)),
    ("star2", (218, 218, 255)),
    ("star3", (182, 182, 218)),
    ("grass0", (0, 36, 0)),
    ("grass1", (0, 72, 36)),
    ("grass2", (0, 109, 36)),
    ("grass3", (36, 109, 36)),
    ("flannel", (182, 0, 0)),
    ("flannel2", (109, 0, 0)),
    ("flannel3", (72, 0, 36)),
    ("jean", (0, 36, 109)),
    ("jean2", (0, 72, 145)),
    ("hskin", (218, 145, 109)),
    ("hskin2", (182, 109, 72)),
    ("hskin0", (145, 72, 36)),
    ("hhair", (36, 36, 72)),
    ("boot", (72, 36, 0)),
    ("boot2", (36, 36, 0)),
    ("rust", (145, 72, 36)),
    ("rust2", (109, 36, 0)),
    ("truck", (72, 109, 145)),
    ("truck2", (36, 72, 109)),
    ("tire", (36, 36, 36)),
    ("hub", (182, 182, 182)),
    ("saucer0", (36, 36, 72)),
    ("saucer1", (72, 72, 109)),
    ("saucer2", (109, 109, 145)),
    ("glint", (36, 255, 109)),  # saucer lamp, on
    ("glint0", (0, 72, 36)),  # saucer lamp, off
    ("button", (0, 255, 218)),  # PUSH ANY BUTTON only
    ("chair", (218, 218, 255)),
    ("chair2", (255, 255, 255)),
    ("chair3", (182, 182, 218)),
    ("chair4", (145, 145, 182)),
    ("dirt", (72, 72, 36)),
    ("dirt2", (109, 109, 72)),
    ("teal", (36, 109, 109)),
    ("teal2", (72, 145, 182)),
    ("lip2", (109, 72, 109)),
    ("warm", (218, 182, 145)),
    ("starw", (255, 218, 218)),
    ("violet", (72, 36, 109)),
    ("framec", (182, 218, 255)),
    ("screen3", (0, 182, 218)),
    ("bark", (109, 72, 36)),
    ("moss", (72, 109, 36)),
]


def _check(rgb: tuple[int, int, int]) -> None:
    if any(c not in LEVELS for c in rgb):
        raise ValueError(f"color {rgb} is outside the PC Engine lattice")


PAL_LIST: list[tuple[int, int, int]] = [(0, 0, 0)]  # 0 = transparent / black
NAME: dict[str, int] = {}
_rgb_index: dict[tuple[int, int, int], int] = {}

for _name, _rgb in _NAMED:
    _check(_rgb)
    if _rgb in _rgb_index and _name != "black":
        NAME[_name] = _rgb_index[_rgb]
        continue
    if _name == "black":
        # Distinct index from transparent even though both are (0, 0, 0).
        NAME["black"] = len(PAL_LIST)
        PAL_LIST.append(_rgb)
        continue
    _rgb_index[_rgb] = len(PAL_LIST)
    NAME[_name] = len(PAL_LIST)
    PAL_LIST.append(_rgb)

PAL = np.array(PAL_LIST, dtype=np.uint8)
N_COLORS = len(PAL_LIST)

# Convenience indices
C = NAME  # alias


def to_rgb(idx: np.ndarray) -> np.ndarray:
    return PAL[idx]


def unique_rgb_count(idx: np.ndarray) -> int:
    rgb = to_rgb(idx)
    flat = rgb.reshape(-1, 3)
    return int(np.unique(flat, axis=0).shape[0])


def assert_palette(idx: np.ndarray, limit: int = 128) -> int:
    rgb = to_rgb(idx)
    flat = rgb.reshape(-1, 3)
    uniq = np.unique(flat, axis=0)
    if len(uniq) > limit:
        raise AssertionError(f"{len(uniq)} colors exceeds {limit}")
    for r, g, b in uniq:
        if int(r) not in LEVELS or int(g) not in LEVELS or int(b) not in LEVELS:
            raise AssertionError(f"non-PCE color {(int(r), int(g), int(b))}")
    return int(len(uniq))


# 512-entry LUT: PCE lattice cell -> nearest master-palette index.
_LUT = np.zeros(512, dtype=np.uint8)
_pal_i = PAL.astype(np.int16)
for _r in range(8):
    for _g in range(8):
        for _b in range(8):
            target = np.array([LEVELS[_r], LEVELS[_g], LEVELS[_b]], dtype=np.int16)
            dist = ((_pal_i - target) ** 2).sum(axis=1)
            _LUT[_r * 64 + _g * 8 + _b] = int(dist.argmin())


def snap_mix(a_idx: np.ndarray, b_idx: np.ndarray, alpha: int) -> np.ndarray:
    """Palette-safe dissolve. alpha 0 keeps a, 255 keeps b."""
    if alpha <= 0:
        return a_idx
    if alpha >= 255:
        return b_idx
    rgb_a = PAL[a_idx].astype(np.int16)
    rgb_b = PAL[b_idx].astype(np.int16)
    mix = (rgb_a * (255 - alpha) + rgb_b * alpha + 127) // 255
    qi = np.clip(np.rint(mix * 7 / 255.0), 0, 7).astype(np.int32)
    return _LUT[qi[..., 0] * 64 + qi[..., 1] * 8 + qi[..., 2]]


def fade_black(idx: np.ndarray, alpha: int) -> np.ndarray:
    """alpha 0 = original, 255 = black."""
    if alpha <= 0:
        return idx
    black = np.zeros_like(idx)
    return snap_mix(idx, black, alpha)


LEVELS_U8 = np.array(LEVELS, dtype=np.uint8)


def snap_image(rgb: np.ndarray) -> np.ndarray:
    """Nearest PC Engine lattice color for every pixel. rgb is uint8 HxWx3."""
    qi = np.clip(np.rint(rgb.astype(np.float64) * 7.0 / 255.0), 0, 7).astype(np.int32)
    return LEVELS_U8[qi]


def fade_image(rgb: np.ndarray, alpha: int) -> np.ndarray:
    """Fade an RGB frame toward black the way the indexed card does.

    alpha 0 keeps the picture, 255 is black. The mix is snapped onto the
    9-bit lattice and then onto the master palette, matching fade_black.
    """
    if alpha <= 0:
        return rgb
    if alpha >= 255:
        return np.zeros_like(rgb)
    mix = (rgb.astype(np.int32) * (255 - int(alpha)) + 127) // 255
    qi = np.clip(np.rint(mix.astype(np.float64) * 7.0 / 255.0), 0, 7).astype(np.int32)
    return PAL[_LUT[qi[..., 0] * 64 + qi[..., 1] * 8 + qi[..., 2]]]
