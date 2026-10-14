"""Draw one 256x224 frame from a loaded project."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from introkit.font import Overlay, apply_sheen, draw_logo, draw_small, logo_width, small_width
from introkit.motion import cycle_index, round_pos, sample_xy
from introkit.palette import fade_image, snap_image
from introkit.project import Project, Scene, Sprite, mouth_at, scene_at

W = 256
H = 224


def _rgba(path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _rgb_array(path) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8))


class Film:
    def __init__(self, project: Project):
        self.project = project
        self._images: dict = {}
        self._plates: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._prepare_mouths()

    def scene_at(self, frame: int) -> Scene:
        return scene_at(self.project, frame)

    def mouth_at(self, frame: int) -> str:
        return mouth_at(self.project, frame)

    def render(self, frame: int) -> np.ndarray:
        if not 0 <= frame < self.project.total_frames:
            raise IndexError(frame)
        scene = self.scene_at(frame)
        if scene.type == "still":
            rgb = self._still(scene, frame)
        elif scene.type == "scroll":
            rgb = self._scroll(scene, frame)
        elif scene.type == "stack":
            rgb = self._stack(scene, frame)
        elif scene.type == "title":
            rgb = self._title(scene, frame)
        else:
            raise RuntimeError(scene.type)
        if self.project.palette == "tg16":
            rgb = snap_image(rgb)
        if rgb.shape != (H, W, 3) or rgb.dtype != np.uint8:
            raise RuntimeError(f"bad frame {rgb.shape} {rgb.dtype}")
        return np.ascontiguousarray(rgb)

    def _image(self, path) -> Image.Image:
        key = str(path)
        hit = self._images.get(key)
        if hit is None:
            hit = _rgba(path)
            self._images[key] = hit
        return hit

    def _prepare_mouths(self) -> None:
        for plate in self.project.mouths.values():
            closed = _rgb_array(plate.closed)
            if plate.patch is not None:
                patch = _rgb_array(plate.patch.image)
                opened = closed.copy()
                ph, pw = patch.shape[:2]
                x, y = plate.patch.x, plate.patch.y
                opened[y : y + ph, x : x + pw] = patch
            else:
                opened = _rgb_array(plate.open_path)
            self._plates[plate.id] = (closed, opened)

    def _rgb(self, path) -> np.ndarray:
        key = ("rgb", str(path))
        hit = self._images.get(key)
        if hit is None:
            hit = _rgb_array(path)
            self._images[key] = hit
        return hit

    def _still(self, scene: Scene, frame: int) -> np.ndarray:
        state = self.mouth_at(frame)
        if scene.mouth and state == "open":
            if scene.image is None or self.project.mouths[scene.mouth].patch is None:
                return self._plates[scene.mouth][1]
            base = self._rgb(scene.image).copy()
            plate = self.project.mouths[scene.mouth]
            patch = self._rgb(plate.patch.image)
            ph, pw = patch.shape[:2]
            x, y = plate.patch.x, plate.patch.y
            base[y : y + ph, x : x + pw] = patch
            return base
        if scene.image is not None:
            return self._rgb(scene.image)
        return self._plates[scene.mouth][0]

    def _scroll(self, scene: Scene, frame: int) -> np.ndarray:
        scroll = scene.scroll
        assert scroll is not None
        tile = self._image(scroll.tile)
        t = frame / self.project.fps
        signed = scroll.speed if scroll.direction == "left" else -scroll.speed
        shift = int(t * signed) % scroll.tile_w
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        x = -shift
        while x < W:
            canvas.paste(tile, (x, 0))
            x += scroll.tile_w
        canvas.paste(tile, (-shift - scroll.tile_w, 0))
        if scroll.sprite is not None:
            sp = scroll.sprite
            bob = 0
            if sp.bob_hz:
                bob = int(round(sp.bob_px * math.sin(2 * math.pi * sp.bob_hz * t)))
            sprite = self._sprite_image(sp, frame, scene)
            self._composite(canvas, sprite, int(round(sp.x)), int(round(sp.y)) + bob)
        return np.asarray(canvas.convert("RGB"), dtype=np.uint8)

    def _stack(self, scene: Scene, frame: int) -> np.ndarray:
        sprites = [layer.sprite for layer in scene.layers if layer.sprite is not None]
        by_id = {sp.id: sp for sp in sprites if sp.id}
        memo: dict[str, tuple[int, int]] = {}

        def position(sp: Sprite) -> tuple[int, int]:
            if sp.id and sp.id in memo:
                return memo[sp.id]
            if sp.parent:
                px, py = position(by_id[sp.parent])
                x, y = px + sp.ox, py + sp.oy
            else:
                x, y = round_pos(*sample_xy(frame, sp.keys, sp.x, sp.y))
            if sp.bob_hz:
                t = frame / self.project.fps
                y += int(round(sp.bob_px * math.sin(2 * math.pi * sp.bob_hz * t)))
            if sp.id:
                memo[sp.id] = (x, y)
            return x, y

        for sp in sprites:
            position(sp)

        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        pending: list[tuple[str, Image.Image, tuple[int, int]]] = []
        started = False
        for layer in scene.layers:
            if layer.kind == "image":
                assert layer.image is not None
                im = self._image(layer.image.image)
                if not started and layer.image.x == 0 and layer.image.y == 0 and im.size == (W, H):
                    canvas = im.copy()
                    started = True
                else:
                    self._composite(canvas, im, layer.image.x, layer.image.y)
                    started = True
            elif layer.kind == "sprite":
                assert layer.sprite is not None
                sp = layer.sprite
                if sp.show is not None and not (sp.show[0] <= frame < sp.show[1]):
                    pass
                elif sp.pop is not None and sp.show is not None and sp.show[1] - sp.pop.frames <= frame < sp.show[1]:
                    pop_im = self._pop_image(sp)
                    x, y = position(sp)
                    if sp.pop.y is not None:
                        y = sp.pop.y
                    if sp.pop.above:
                        pending.append((sp.pop.above, pop_im, (x, y)))
                    else:
                        self._composite(canvas, pop_im, x, y)
                else:
                    im = self._sprite_image(sp, frame, scene)
                    x, y = position(sp)
                    self._composite(canvas, im, x, y)
                started = True
            if layer.sprite is not None and layer.sprite.id:
                still = []
                for above, im, xy in pending:
                    if above == layer.sprite.id:
                        self._composite(canvas, im, xy[0], xy[1])
                    else:
                        still.append((above, im, xy))
                pending = still
        for _above, im, xy in pending:
            self._composite(canvas, im, xy[0], xy[1])
        return np.asarray(canvas.convert("RGB"), dtype=np.uint8)

    def _sprite_image(self, sp: Sprite, frame: int, scene: Scene) -> Image.Image:
        paths = sp.frames or ([sp.image] if sp.image is not None else [])
        if sp.cycle is None or len(paths) <= 1:
            return self._recolored(paths[0], sp.recolor)
        local = frame - sp.cycle.start_frame
        span = (sp.cycle.end_frame - sp.cycle.start_frame) - sp.cycle.skip_last
        index = cycle_index(local, len(paths), sp.cycle.mode, span, sp.cycle.hold)
        return self._recolored(paths[index], sp.recolor)

    def _recolored(self, path, pairs) -> Image.Image:
        key = (str(path), tuple(pairs))
        hit = self._images.get(key)
        if hit is not None:
            return hit
        im = self._image(path)
        if not pairs:
            self._images[key] = im
            return im
        arr = np.array(im)
        out = arr.copy()
        for src, dst in pairs:
            src_a = np.array(src, dtype=np.uint8)
            if src_a.shape[0] == 3:
                src_a = np.array([*src[:3], 255], dtype=np.uint8)
            mask = np.all(arr == src_a, axis=-1)
            if not mask.any():
                raise RuntimeError(f"recolor {tuple(src)} matched no pixels in {path}")
            out[mask] = np.array(dst, dtype=np.uint8)
        painted = Image.fromarray(out, "RGBA")
        self._images[key] = painted
        return painted

    def _pop_image(self, sp: Sprite) -> Image.Image:
        assert sp.pop is not None
        key = ("pop", sp.id, id(sp))
        hit = self._images.get(key)
        if hit is not None:
            return hit
        if sp.pop.image is not None:
            im = self._image(sp.pop.image)
            self._images[key] = im
            return im
        paths = sp.frames or ([sp.image] if sp.image is not None else [])
        src = self._recolored(paths[-1], sp.recolor)
        flat = src.resize((src.width, sp.pop.squash_h), Image.Resampling.NEAREST)
        im = Image.new("RGBA", (src.width, sp.pop.canvas_h), (0, 0, 0, 0))
        im.paste(flat, (0, sp.pop.paste_y), flat)
        if sp.pop.flash is not None:
            fl = sp.pop.flash
            px = im.load()
            for y in range(fl.y, fl.y + fl.h):
                for x in range(fl.x, fl.x + fl.w):
                    if 0 <= x < im.width and 0 <= y < im.height:
                        px[x, y] = fl.color
        self._images[key] = im
        return im

    def _composite(self, canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
        x, y = int(x), int(y)
        if sprite.mode != "RGBA":
            sprite = sprite.convert("RGBA")
        if x >= canvas.width or y >= canvas.height or x + sprite.width <= 0 or y + sprite.height <= 0:
            return
        if x < 0 or y < 0 or x + sprite.width > canvas.width or y + sprite.height > canvas.height:
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            layer.paste(sprite, (x, y), sprite)
            canvas.alpha_composite(layer)
            return
        canvas.alpha_composite(sprite, (x, y))

    def _title(self, scene: Scene, frame: int) -> np.ndarray:
        base, mask = self._title_base(scene)
        rgba = base.copy()
        for text in scene.texts:
            if text.sheen:
                apply_sheen(rgba, mask, frame, text.sheen)
                break
        if scene.prompt and self._prompt_on(scene, frame):
            self._over(rgba, self._prompt_layer(scene))
        rgb = rgba[:, :, :3]
        local = frame - scene.start_frame
        if scene.fade_in and local < scene.fade_in:
            alpha = 255 - int(local / scene.fade_in * 255)
            rgb = fade_image(rgb, alpha)
        return np.ascontiguousarray(rgb)

    def _prompt_on(self, scene: Scene, frame: int) -> bool:
        assert scene.prompt is not None
        on = max(1, int(round(scene.prompt.on * self.project.fps)))
        off = max(1, int(round(scene.prompt.off * self.project.fps)))
        local = frame - scene.start_frame
        return (local % (on + off)) < on

    def _title_base(self, scene: Scene):
        key = ("title-base", scene.id)
        hit = self._images.get(key)
        if hit is not None:
            return hit
        if scene.background_image is not None:
            rgba = np.array(self._image(scene.background_image))
        else:
            color = scene.background_color or (0, 0, 0, 255)
            rgba = np.zeros((H, W, 4), dtype=np.uint8)
            rgba[:, :] = color
        mask = np.zeros((H, W), dtype=bool)
        for text in scene.texts:
            layer, text_mask = self._text_layer(text)
            self._over(rgba, layer)
            mask |= text_mask
        packed = (rgba, mask)
        self._images[key] = packed
        return packed

    def _prompt_layer(self, scene: Scene) -> np.ndarray:
        key = ("prompt", scene.id)
        hit = self._images.get(key)
        if hit is not None:
            return hit
        assert scene.prompt is not None
        layer, _mask = self._text_layer(
            scene.prompt,
            outline_first=True,
        )
        self._images[key] = layer
        return layer

    def _text_layer(self, text, outline_first: bool = False):
        overlay = Overlay(W, H)
        mask = np.zeros((H, W), dtype=bool)
        if text.font == "logo":
            tw = logo_width(text.text, text.scale, text.gap)
            x = (W - tw) // 2 if text.align == "center" else int(text.x)
            mask = draw_logo(overlay, text.text, x, text.y, text.scale, text.gap)
        else:
            tw = small_width(text.text, text.scale, text.gap)
            x = (W - tw) // 2 if text.align == "center" else int(text.x)
            if outline_first and text.outline is not None:
                for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    draw_small(overlay, text.text, x + ox, text.y + oy, text.outline, text.scale, text.gap)
            elif text.outline is not None and not outline_first:
                for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    draw_small(overlay, text.text, x + ox, text.y + oy, text.outline, text.scale, text.gap)
            draw_small(overlay, text.text, x, text.y, text.color, text.scale, text.gap)
        return overlay.px, mask

    @staticmethod
    def _over(dst: np.ndarray, src: np.ndarray) -> None:
        """Binary source-over. Text pixels are fully opaque or fully clear."""
        mask = src[:, :, 3] == 255
        dst[mask] = src[mask]
