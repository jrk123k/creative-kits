#!/usr/bin/env bash
# 1920s silent-film finishing filter (pure ffmpeg). Usage:
#   ./silentfilm.sh [-p light|standard|heavy] [-v 0|1] [-f FPS] IN_DIR_OR_FILE OUT_DIR
set -euo pipefail
PRESET=standard; VIG=1; FPS_OVR=""
while getopts "p:v:f:" o; do case $o in p) PRESET=$OPTARG;; v) VIG=$OPTARG;; f) FPS_OVR=$OPTARG;; *) exit 1;; esac; done
shift $((OPTIND-1)); IN=${1:?input}; OUT=${2:?outdir}; mkdir -p "$OUT"
# knobs: FPS GRAIN SAT FLICK WEAVE JIT SCR DUST TINT
case $PRESET in
  light)    FPS=18; GRAIN=8;  SAT=0.75; FLICK=0.02; WEAVE=1.5; JIT=1; SCR=0.15; DUST=0.25; TINT=0.6;;
  standard) FPS=17; GRAIN=14; SAT=0.6;  FLICK=0.04; WEAVE=3;   JIT=2; SCR=0.25; DUST=0.45; TINT=0.8;;
  heavy)    FPS=16; GRAIN=22; SAT=0.45; FLICK=0.07; WEAVE=5;   JIT=4; SCR=0.4;  DUST=0.7;  TINT=1.0;;
  *) echo "unknown preset $PRESET"; exit 1;;
esac
[ -n "$FPS_OVR" ] && FPS=$FPS_OVR
K=1-$TINT
VF="fps=$FPS,scale=1344:756,crop=1280:720:x='32+$WEAVE*sin(2*PI*t*0.7)+$JIT*(random(1)-0.5)':y='18+$WEAVE*0.6*sin(2*PI*t*1.3)+$JIT*(random(2)-0.5)'"
VF+=",eq=saturation=$SAT:contrast=1.08:brightness='$FLICK*(random(3)-0.5)':eval=frame"
# warm pastel hand-tint: blend toward sepia matrix by TINT
VF+=",colorchannelmixer=rr=$K+$TINT*0.45:rg=$TINT*0.45:rb=$TINT*0.12:gr=$TINT*0.30:gg=$K+$TINT*0.55:gb=$TINT*0.12:br=$TINT*0.22:bg=$TINT*0.38:bb=$K+$TINT*0.30"
VF+=",curves=all='0/0.06 0.5/0.52 1/0.94'"
VF+=",noise=alls=$GRAIN:allf=t+u"
VF+=",drawbox=x='mod(trunc(t*$FPS)*397,iw)':y=0:w=1:h=ih:color=white@$SCR:t=fill:enable='lt(mod(n*7,19),3)'"
VF+=",drawbox=x='mod(trunc(t*$FPS)*613+200,iw)':y=0:w=2:h=ih:color=black@$SCR:t=fill:enable='lt(mod(n*11,29),2)'"
VF+=",drawbox=x='mod(trunc(t*$FPS)*271,iw)':y='mod(trunc(t*$FPS)*173,ih)':w=4:h=3:color=black@$DUST:t=fill:enable='lt(mod(n*5,7),3)'"
VF+=",drawbox=x='mod(trunc(t*$FPS)*829+90,iw)':y='mod(trunc(t*$FPS)*331+40,ih)':w=3:h=5:color=white@$DUST:t=fill:enable='lt(mod(n*3,11),3)'"
[ "$VIG" = 1 ] && VF+=",vignette=angle=PI/4.5"
VF+=",setsar=1,format=yuv420p"
shopt -s nullglob nocaseglob
if [ -d "$IN" ]; then FILES=("$IN"/*.mp4); else FILES=("$IN"); fi
for f in "${FILES[@]}"; do
  b=$(basename "${f%.*}"); o="$OUT/${b}_silent_${PRESET}.mp4"
  echo ">> $f -> $o"
  ffmpeg -hide_banner -loglevel error -y -i "$f" -an -vf "$VF" -c:v libx264 -preset medium -crf 18 -r $FPS -movflags +faststart "$o"
done
