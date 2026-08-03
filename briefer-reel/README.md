# BRIEFR Marketing Reels

Portrait motion-graphics marketing videos (1080×1920, 9:16) for Instagram Reels and LinkedIn, built with [HyperFrames](https://hyperframes.heygen.com/) and GSAP.

Inspired by the original PR #799 composition (`8a79141a`) — stylized mock UI shells, animated grid/glow backgrounds, smooth GSAP timelines. **No screen captures or login forms.**

## Cuts

| File | Duration | Narrative |
|------|----------|-----------|
| `briefr-cut1-product-hook-54s.mp4` | 54s | Product hook with logo bookends — dense content, vertically centered |
| `briefr-cut2-scoring-correlation-90s.mp4` | 90s | Six-factor risk weights, stack matching, correlation engine, embeddings |
| `briefr-cut3-data-deploy-90s.mp4` | 90s | Feed ingestion, PostgreSQL 16 + pgvector, docker compose deploy |
| `briefr-cut4-linkedin-60s.mp4` | 60s | Fast montage + free/self-hosted CTA |

Rendered output: `docs/marketing/reels/`

## Commands

```bash
# Preview a cut locally
cd briefer-reel/cuts/cut1-product-hook && npm run dev  # or npx hyperframes preview

# Validate composition
cd briefer-reel/cuts/cut1-product-hook && npx hyperframes check .

# Render all cuts
./scripts/render_marketing_reels.sh
```

## Voiceover

F5 TTS scripts: `docs/marketing/reel-f5-tts-speak-only.txt` and `docs/marketing/reel-f5-tts-transcripts.txt`

## Brand assets

Official logos copied from `briefr-maintainer` into `docs/marketing/brand/` and `briefer-reel/assets/`.
