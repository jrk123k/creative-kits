#!/usr/bin/env bash
# Slow-panning dark sci-fi plate. 1080p30, no audio.
#   scripts/generate-background.sh [duration_sec] [output]
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-117.2}"
OUT="${2:-out/background.mp4}"
mkdir -p out "$(dirname "$OUT")"
PLATE="out/plate.ppm"

python3 - "$PLATE" << 'PY'
import sys
import numpy as np

path = sys.argv[1]
w, h = 3400, 1912
ys, xs = np.mgrid[0:h, 0:w]
nx = xs / w
ny = ys / h

r = 3 + 10 * np.sin(nx * 2.4) + 8 * ny
g = 8 + 22 * (1 - ny) + 8 * np.sin(nx * 1.7 + 0.6)
b = 16 + 42 * (1 - ny) + 14 * np.cos(nx * 1.3)

ridge_y = 0.62 + 0.045 * np.sin(nx * 6.5) + 0.02 * np.sin(nx * 17)
ridge = np.exp(-((ny - ridge_y) / 0.035) ** 2)
r = r + 78 * ridge
g = g + 36 * ridge
b = b + 14 * ridge

glow = np.exp(-((nx - 0.78) ** 2) / 0.06 - ((ny - 0.48) ** 2) / 0.1)
b = b + 36 * glow
g = g + 14 * glow

rng = np.random.default_rng(11)
stars = rng.random((h, w))
bright = stars > 0.9994
dim = (stars > 0.9978) & ~bright
r = r + dim * 70 + bright * 170
g = g + dim * 90 + bright * 190
b = b + dim * 120 + bright * 210

img = np.clip(np.dstack([r, g, b]), 0, 255).astype(np.uint8)
with open(path, "wb") as handle:
    handle.write(f"P6\n{w} {h}\n255\n".encode())
    handle.write(img.tobytes())
print(f"wrote {path} {w}x{h}")
PY

ffmpeg -y \
  -loop 1 -i "$PLATE" \
  -f lavfi -i "color=c=0x02040a:s=1920x1080:r=30:d=${DURATION}" \
  -filter_complex "\
    [0:v]format=rgb24,scale=3400:1912[plate];\
    [1:v][plate]overlay=x='-780-360*sin(t/11)':y='-460-150*cos(t/15)':shortest=1,\
    eq=saturation=0.92:contrast=1.06:brightness=-0.03,\
    vignette=angle=PI/4:mode=forward,\
    fps=30,format=yuv420p[v]" \
  -map "[v]" -an \
  -t "$DURATION" -r 30 \
  -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$OUT"

echo "Wrote $OUT"
ffprobe -hide_banner -show_entries stream=width,height,avg_frame_rate,nb_frames,duration -of default=nw=1 "$OUT"
