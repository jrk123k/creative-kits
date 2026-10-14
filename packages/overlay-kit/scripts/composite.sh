#!/usr/bin/env bash
# Composite background + transparent overlay + song into a 1080p30 H.264 MP4.
#   scripts/composite.sh background.mp4 overlay.webm song.mp3 out.mp4
set -euo pipefail

BG="${1:?background video}"
OVERLAY="${2:?overlay video with alpha}"
AUDIO="${3:?song audio}"
OUT="${4:?output mp4}"

mkdir -p "$(dirname "$OUT")"

# VP8/VP9 alpha lives in a side channel. The native decoder drops it and the
# overlay paints black. libvpx keeps the alpha plane.
OVERLAY_CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$OVERLAY")"
OVERLAY_INPUT=(-i "$OVERLAY")
if [[ "$OVERLAY_CODEC" == "vp8" ]]; then
  OVERLAY_INPUT=(-c:v libvpx -i "$OVERLAY")
elif [[ "$OVERLAY_CODEC" == "vp9" ]]; then
  OVERLAY_INPUT=(-c:v libvpx-vp9 -i "$OVERLAY")
fi

ffmpeg -y \
  -i "$BG" \
  "${OVERLAY_INPUT[@]}" \
  -i "$AUDIO" \
  -filter_complex "\
    [0:v]scale=1920:1080:flags=lanczos,fps=30,format=yuv420p[bg];\
    [bg][1:v]overlay=0:0:format=auto:eof_action=pass[v]" \
  -map "[v]" \
  -map "2:a:0" \
  -c:v libx264 \
  -preset medium \
  -crf 20 \
  -pix_fmt yuv420p \
  -r 30 \
  -c:a aac \
  -b:a 192k \
  -ac 2 \
  -ar 48000 \
  -shortest \
  -movflags +faststart \
  "$OUT"

echo "Wrote $OUT"
ffprobe -hide_banner -show_entries format=duration,size -show_entries stream=codec_name,width,height,avg_frame_rate,pix_fmt -of default=nw=1 "$OUT"
