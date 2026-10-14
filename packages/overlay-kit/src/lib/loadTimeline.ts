import {readFileSync} from "node:fs";
import {parseTimeline} from "./parseTimeline";
import {resolveTimeline} from "./resolveTimeline";
import type {Alignment, ResolvedTimeline} from "./types";

export function loadTimelineFile(yamlPath: string): ResolvedTimeline {
  const yamlText = readFileSync(yamlPath, "utf8");
  const config = parseTimeline(yamlText);
  const alignment = JSON.parse(readFileSync(config.alignment, "utf8")) as Alignment;
  return resolveTimeline(config, alignment);
}
