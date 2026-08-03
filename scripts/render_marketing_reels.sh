#!/usr/bin/env bash
# Render all BRIEFR marketing reels via HyperFrames.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/docs/marketing/reels"
HF="npx --yes hyperframes@0.7.86"
FPS=30
QUALITY=high

mkdir -p "$OUT_DIR"

render_cut() {
  local cut_dir="$1"
  local output="$2"
  echo "==> Rendering $(basename "$cut_dir") -> $(basename "$output")"
  cd "$cut_dir"
  $HF render . -o "$output" --fps "$FPS" --quality "$QUALITY"
  ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$output"
}

render_cut "$ROOT/briefer-reel/cuts/cut1-product-hook" \
  "$OUT_DIR/briefr-cut1-product-hook-54s.mp4"

render_cut "$ROOT/briefer-reel/cuts/cut2-scoring-correlation" \
  "$OUT_DIR/briefr-cut2-scoring-correlation-90s.mp4"

render_cut "$ROOT/briefer-reel/cuts/cut3-data-deploy" \
  "$OUT_DIR/briefr-cut3-data-deploy-90s.mp4"

render_cut "$ROOT/briefer-reel/cuts/cut4-linkedin" \
  "$OUT_DIR/briefr-cut4-linkedin-60s.mp4"

echo "All reels rendered to $OUT_DIR"
ls -lh "$OUT_DIR"/*.mp4
