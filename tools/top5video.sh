#!/bin/sh
# Silent 1080x1920 ~12s clip from og/top5-<lang>.png.
# Blurred cover background, the card kept sharp and centered, slow zoom that
# stays inside the card's margin. crf 28, no audio. Needs ffmpeg.
# Usage: tools/top5video.sh zh|en|ko
set -eu
lang=${1:?lang zh|en|ko}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
png="$root/og/top5-${lang}.png"
out="$root/og/top5-${lang}.mp4"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg missing; skip $out" >&2
  exit 0
fi
if [ ! -f "$png" ]; then
  echo "missing $png; skip" >&2
  exit 0
fi
# 288 frames at 24 fps = 12s. Zoom 1 -> ~1.043, centered, so a 1000px-wide card
# on a 1080x1920 frame is not cropped. One input frame; zoompan holds it for d frames.
ffmpeg -y -i "$png" \
  -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=24[bg];[0:v]scale=1000:-2:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p,zoompan=z='min(1+0.00015*on,1.045)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=288:s=1080x1920:fps=24" \
  -an -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -movflags +faststart \
  "$out"
echo "wrote $out"
