# BRIEFR Light Theme Design System

> **Deprecated (2026-06):** Light mode was removed from the product UI. BRIEFR ships **dark mode only**. This document is kept for historical reference if light theme is reintroduced.

**Version:** 1.1 · **Date:** 2026-06-07

Light mode used a **newsprint terminal** palette: warm page ground (`#f0ece4`), white raised panels, ink-like text, and unchanged brand orange (`#e85533`). It was not a dark-theme invert.

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

## Files (archived)

- `frontend/src/theme/light-theme.css` — surface overrides (no longer imported)
- Toggle lived in `Header.jsx` (removed)

## Current default

Dark tokens are defined in `frontend/src/App.css` under `:root`. No `data-theme` attribute is set on `<html>`.
