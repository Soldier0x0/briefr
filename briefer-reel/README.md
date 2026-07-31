# BRIEFR Instagram Reel

30-second portrait motion-graphics pitch video for BRIEFR, built with [HyperFrames](https://hyperframes.heygen.com/).

## Output

- **Rendered video:** `renders/briefer-instagram-reel.mp4`
- **Format:** 1080×1920 (9:16), 30 fps, 30 seconds — ready for Instagram Reels

## Scenes

1. **0–4s** — Logo intro + tagline
2. **4–8s** — Value prop: "One dashboard. Every signal."
3. **8–13s** — BRIEF tab: morning brief, stats, heatmap
4. **13–18s** — FEED: prioritized CVE cards (KEV, EPSS, P1)
5. **18–23s** — Risk scoring + IOC enrichment
6. **23–26s** — FORGE: ATT&CK navigator, hunt packs
7. **26–30s** — CTA: self-hosted, demo URL

## Commands

```bash
npm run dev      # live preview
npm run check    # lint + runtime validation
npm run render   # re-render MP4
```

Re-render with custom output:

```bash
hyperframes render . -o renders/briefer-instagram-reel.mp4 --fps 30 --quality high
```

Add music in Instagram before posting, or extend the composition with an `<audio>` track.
