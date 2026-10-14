#!/usr/bin/env bash
# Render the transparent HUD.
#   scripts/render-overlay.sh webm out/overlay.webm [extra remotion args...]
#   scripts/render-overlay.sh prores out/overlay.mov [extra remotion args...]
#   TIMELINE=timelines/demo-cut.yaml scripts/render-overlay.sh webm out/nova.webm
set -euo pipefail
cd "$(dirname "$0")/.."

FORMAT="${1:?format: webm or prores}"
OUT="${2:?output path}"
shift 2

TIMELINE="${TIMELINE:-timelines/seventh-observation.yaml}"

mkdir -p out public/audio "$(dirname "$OUT")"
cp -f assets/audio/The_Seventh_Observation.mp3 public/audio/The_Seventh_Observation.mp3

npx tsx scripts/export-props.ts "$TIMELINE" out/props.json

COMMON=(
  --props=out/props.json
  --concurrency=2
  --image-format=png
  --muted
)

if [[ "$FORMAT" == "webm" ]]; then
  npx remotion render src/index.ts Overlay "$OUT" \
    "${COMMON[@]}" \
    --codec=vp8 \
    --pixel-format=yuva420p \
    "$@"
elif [[ "$FORMAT" == "prores" ]]; then
  npx remotion render src/index.ts Overlay "$OUT" \
    "${COMMON[@]}" \
    --codec=prores \
    --prores-profile=4444 \
    --pixel-format=yuva444p10le \
    "$@"
else
  echo "Unknown format: $FORMAT (use webm or prores)" >&2
  exit 1
fi
