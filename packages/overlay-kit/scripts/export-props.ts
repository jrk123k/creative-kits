import {mkdirSync, writeFileSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {loadTimelineFile} from "../src/lib/loadTimeline";

const yamlPath = resolve(process.argv[2] ?? "timelines/seventh-observation.yaml");
const outPath = resolve(process.argv[3] ?? "out/props.json");
const timeline = loadTimelineFile(yamlPath);
mkdirSync(dirname(outPath), {recursive: true});
writeFileSync(outPath, JSON.stringify({timeline}));
console.log(
  `Wrote ${outPath} (${timeline.durationInFrames} frames, ${timeline.lines.length} lyric lines)`,
);
