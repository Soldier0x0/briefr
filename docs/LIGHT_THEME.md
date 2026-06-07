# BRIEFR Light Theme Design System

**Version:** 1.1 · **Date:** 2026-06-07

Light mode uses a **newsprint terminal** palette: warm page ground (`#f0ece4`), white raised panels, ink-like text, and unchanged brand orange (`#e85533`). It is not a dark-theme invert.

## Token changes (dark → light)

| Token | Dark | Light | Purpose |
|-------|------|-------|---------|
| `--bg` | `#0a0a08` | `#f0ece4` | Page ground (newsprint) |
| `--bg2` | `#111110` | `#ffffff` | Raised panels / inputs |
| `--bg3` | `#1a1a17` | `#e8e4dc` | Sunken wells |
| `--border` | `#2a2a25` | `#c9c4bb` | Standard rules |
| `--border2` | `#333330` | `#b8b2a8` | Secondary rules |
| `--border-strong` | `#3d3d38` | `#9a948a` | **New** — panel edges, focus |
| `--text` | `#e8e6df` | `#1a1814` | Primary ink |
| `--text2` | `#9a9890` | `#3d3a36` | Body secondary |
| `--text3` | `#5a5850` | `#5c5852` | Labels / meta |
| `--red` | `#e85533` | `#e85533` | **Unchanged** brand orange |
| `--on-red` | `#ffffff` | `#ffffff` | **New** — text on orange buttons |
| `--red-dim` | `#3d1a12` | `#fdeae5` | KEV / tint backgrounds |
| `--amber` | `#d4860a` | `#9a5f00` | Severity (AA on white) |
| `--amber-dim` | `#2e1e04` | `#faf0dc` | Amber chip fill |
| `--green` | `#4a9e6a` | `#2a7044` | Positive states |
| `--green-dim` | `#0d2318` | `#d8ebe0` | Green chip fill |
| `--accent` | `#c8b88a` | `#c8b88a` | **Unchanged** gold accent |
| `--surface-page` | `var(--bg)` | `#f0ece4` | Page layer |
| `--surface-raised` | `var(--bg2)` | `#ffffff` | KPI band, header, cards |
| `--surface-sunken` | `var(--bg3)` | `#ebe7df` | Vendor strip, hover |
| `--input-bg` | `var(--bg2)` | `#ffffff` | Search fields |
| `--chip-bg` | `var(--bg2)` | `#ffffff` | Filter chips |
| `--chip-border` | `var(--border)` | `#b8b2a8` | Chip outline |
| `--chip-active-bg` | `var(--red-dim)` | `#fdeae5` | Active vendor chip |
| `--shadow-sm` | `none` | `0 1px 2px rgba(26,24,20,.06)` | Panel lift |
| `--shadow-md` | `none` | `0 2px 10px rgba(26,24,20,.1)` | Tooltips / modals |
| `--heatmap-0` | `#1a1a17` | `#ebe7df` | Empty cells |
| `--heatmap-1` | `#2d1a0e` | `#f5d0c4` | Low activity |
| `--heatmap-2` | `#7a3520` | `#e8a088` | Medium |
| `--heatmap-3` | `#b84a28` | `#e85533` | High |
| `--heatmap-4` | `#e85533` | `#c93d1a` | Peak |

## Component treatment (light only)

| Area | Treatment |
|------|-----------|
| KPI row (`stats-row`) | White band, strong border, subtle shadow |
| Filter bar | White sticky bar, inset search field |
| Filter chips | White fill; active = orange + white label |
| Vendor chips | White + shadow; active = rose tint + orange border |
| Heatmap | Theme tokens via `heatmapGrid.js`; empty cells bordered |
| Sidebar | White panel, left rule + shadow |
| CVE cards | White rows on newsprint page |

## Files

- `frontend/src/App.css` — token definitions
- `frontend/src/theme/light-theme.css` — surface overrides
- `frontend/src/utils/heatmapGrid.js` — heatmap scale tokens

## CSP note

Vite injects component CSS as inline `<style>` tags in development. The `Content-Security-Policy` in `frontend/index.html` must include `'unsafe-inline'` in `style-src` or the app renders as unstyled HTML (Times New Roman, default buttons, empty heatmap). Production builds use external `/assets/*.css` files and are unaffected, but README screenshots are captured from the dev server.

## Screenshots

Regenerate README (dark default):

```bash
cd frontend && npm run dev   # :5173
# backend on :8000
node ../scripts/capture_readme_screenshots.mjs
```

Theme audit (dark + light viewport):

```bash
node scripts/capture_theme_screenshots.mjs
# → screenshots/theme-audit/brief-dark.png, brief-light.png
```
