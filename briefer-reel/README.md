# BRIEFR Instagram Reel

Portrait marketing video for BRIEFR with **real UI screen capture**, animated cursor, scene labels, and AI voiceover.

## Outputs

| File | Description |
|------|-------------|
| `renders/briefer-walkthrough-reel.mp4` | **Recommended** — 58s real product walkthrough + voiceover (1080×1920) |
| `renders/briefer-instagram-reel.mp4` | Earlier motion-graphics concept (stylized mock UI) |

## Walkthrough video (v2)

Recorded from a live local BRIEFR instance with Playwright, then composited in HyperFrames.

**Scenes (~58s):**

1. **BRIEF** — morning brief, stats, heatmap
2. **FEED** — stack-filtered CVE stream
3. **CVE detail drawer** — operational priority, threat score, tabs
4. **IOC LOOKUP** — indicator enrichment
5. **FORGE** — ATT&CK navigator / detection engineering
6. **CTA** — self-hosted, open source, demo URL

**Voiceover:** Generated with `hyperframes tts` (Kokoro, `am_adam` voice).

## Regenerate from scratch

### 1. Start BRIEFR

```bash
# Terminal 1 — backend
cd backend && source .venv/bin/activate
DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev

# Seed data (once)
python3 scripts/seed_screenshot_data.py
# Create admin if needed: POST /api/auth/setup
```

### 2. Record UI walkthrough

```bash
SCREENSHOT_USERNAME=admin SCREENSHOT_PASSWORD='your-password' \
  node scripts/capture_reel_walkthrough.mjs
```

Produces `briefer-reel/assets/capture/walkthrough.webm` (~61s).

Convert to MP4 (HyperFrames renders MP4 more reliably):

```bash
ffmpeg -y -i briefer-reel/assets/capture/walkthrough.webm \
  -c:v libx264 -pix_fmt yuv420p -an briefer-reel/assets/capture/walkthrough.mp4
```

### 3. Generate voiceover (optional — edit `assets/voiceover/script.txt` first)

```bash
pip install kokoro-onnx soundfile
hyperframes tts --text-file briefer-reel/assets/voiceover/script.txt \
  -o briefer-reel/assets/voiceover/narration.wav -v am_adam -s 0.95
```

### 4. Render final reel

```bash
cd briefer-reel
npm run check
hyperframes render . -o renders/briefer-walkthrough-reel.mp4 --fps 30 --quality high --video-frame-format png
```

Add trending music in Instagram before posting if desired.
