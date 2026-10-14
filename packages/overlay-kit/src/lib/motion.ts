import type {LayerKey, Scene} from "./types";

export type LayerMotion = {
  visible: boolean;
  opacity: number;
  glitch: number;
  jitterX: number;
  jitterY: number;
};

const HIDDEN: LayerMotion = {
  visible: false,
  opacity: 0,
  glitch: 0,
  jitterX: 0,
  jitterY: 0,
};

function easeOut(p: number): number {
  const clamped = Math.min(1, Math.max(0, p));
  return 1 - (1 - clamped) ** 2;
}

export function sceneIndexAt(scenes: Scene[], timeSec: number): number {
  return scenes.findIndex((scene) => timeSec >= scene.in && timeSec < scene.out);
}

export function sceneAt(scenes: Scene[], timeSec: number): Scene | null {
  const index = sceneIndexAt(scenes, timeSec);
  return index < 0 ? null : scenes[index];
}

/** 0–1 glitch intensity during a scene's glitch entrance. */
export function sceneGlitch(scenes: Scene[], timeSec: number): number {
  const scene = sceneAt(scenes, timeSec);
  if (!scene || scene.transition !== "glitch") return 0;
  const duration = scene.transitionFrames / 30;
  const local = timeSec - scene.in;
  if (local < 0 || local >= duration) return 0;
  return 1 - local / duration;
}

export function layerMotion(
  scenes: Scene[],
  timeSec: number,
  layer: LayerKey,
  frame: number,
): LayerMotion {
  const index = sceneIndexAt(scenes, timeSec);
  if (index < 0) return HIDDEN;
  const scene = scenes[index];
  if (!scene.layers[layer]) return HIDDEN;

  const previous = index > 0 ? scenes[index - 1] : null;
  const wasOn = previous ? previous.layers[layer] : false;
  const entering = !wasOn;
  const duration = scene.transitionFrames / 30;
  const local = timeSec - scene.in;
  const inWindow = local < duration;
  const progress = duration <= 0 ? 1 : easeOut(local / duration);

  if (!inWindow) {
    return {visible: true, opacity: 1, glitch: 0, jitterX: 0, jitterY: 0};
  }

  if (scene.transition === "fade") {
    const opacity = entering ? progress : 0.45 + 0.55 * progress;
    return {visible: opacity > 0.01, opacity, glitch: 0, jitterX: 0, jitterY: 0};
  }

  const glitch = 1 - Math.min(1, Math.max(0, local / duration));
  const sign = frame % 2 === 0 ? 1 : -1;
  const opacity = entering
    ? frame % 2 === 0
      ? Math.max(progress, 0.35)
      : 0.15
    : frame % 3 === 0
      ? 0.45
      : 1;
  return {
    visible: true,
    opacity,
    glitch,
    jitterX: sign * glitch * 14,
    jitterY: ((frame % 3) - 1) * glitch * 5,
  };
}
