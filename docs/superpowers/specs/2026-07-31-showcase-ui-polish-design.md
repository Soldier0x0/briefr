# Showcase UI polish & layout fixes — design spec

**Date:** 2026-07-31  
**Status:** Draft — awaiting operator approval

## Problem

The optional "Showcase card style" (`ui_variant: pitch`) improved CVE cards and brief rows, but coverage is incomplete, several behaviors are wrong (vendors hidden on filter, chart height coupling), shared Switch hover is broken, and the product should treat showcase as the default with "Newspaper Style" as the opt-out.

## Goals

1. **Full showcase coverage** — common vendors, sidebar techniques, feed filter chips, IOC quota panel, and other square/dense controls match the card aesthetic when showcase is active.
2. **Common vendors always visible** — KEV/CRITICAL/etc. quick filters must not hide the vendor chip row; vendor selection composes with quick filters.
3. **IOC quota readability** — helper copy and labels use design-system body/meta sizes (AA contrast), not 10px mono.
4. **Layout stability** — analyst chart columns and similar grid pairs do not shrink when a sibling is empty; heatmap column can grow modestly on desktop.
5. **Switch hover fix** — checked toggles keep accent fill on hover (global `ui-switch` fix).
6. **Default flip** — showcase becomes default for new users; Admin → Display offers "Newspaper Style" to restore classic layout; remove showcase toggle from account dropdown.

## Non-goals

- Dynamic common-vendors API (list stays frontend constant; operator refreshes via SQL + code edit).
- Renaming API enum values (`default` / `pitch`) — internal tokens unchanged; labels only.
- Migrating existing users who explicitly saved `ui_variant: default` — they keep newspaper until they change prefs.

## Architecture

### Visual variants (unchanged mechanism)

- `html[data-ui-variant="pitch"]` activates showcase CSS (`pitch-variant.css`).
- `default` = newspaper/classic (no attribute).
- **Change:** `DISPLAY_DEFAULTS.uiVariant` and instance default become `'pitch'`. `applyDisplayPrefs` / repo decode unchanged.

### Showcase CSS expansion

Extend `pitch-variant.css` with real selectors (fix dead `.quick-filter-chip` / `.feed-filter-toolbar`):

| Area | Selectors |
|------|-----------|
| Feed filters | `.filter-btn`, `.filter-search`, `.export-btn`, `.filter-toolbar` |
| Common vendors | `.vendor-filter-block`, `.vendor-btn` |
| Sidebar | `.technique-row`, `.technique-row-active`, `.active-stack` chips |
| IOC quota | `.ioc-quota-panel`, `.ioc-quota-chip`, `.ioc-quota-asof`, `.ioc-quota-retry-btn` |
| Brief charts | `.brief-chart-card`, `.brief-chart-filter-chip` (showcase radii) |

### Behavior fixes

**Common vendors visibility** (`FilterBar.jsx`):

- Remove gate `(active === 'all' || selectedVendors.length > 0)`.
- Always render `vendor-filter-block`; vendor chips remain independent of quick-filter `active` state (already composes in `filters.vendors` → API).

**Brief charts height coupling** (`BriefCharts.css` + `BriefCharts.jsx`):

- **RCA:** `.brief-charts-grid` uses default `align-items: stretch`. Right column (EPSS) sets row height. When empty, row collapses to `min-height: 200px`. Left column `.brief-chart-canvas-wrap { flex: 1 }` shrinks below `ChartShell` fixed height → clipping via `.chart-shell { overflow: hidden }`.
- **Fix:** `align-items: start` on grid; remove `flex: 1` from canvas wrap (height from chart only); empty EPSS state uses `.brief-chart-empty` with `min-height` matching populated table (~280px).

**Heatmap size** (`App.css` + `TimelineHeatmap.jsx`):

- Desktop: increase `cellSize` 12→14 and `brief-intel-row > .timeline-heatmap` flex-basis accordingly (212px → ~244px for 90 days).

**Switch hover** (`ui.css`):

```css
.ui-switch[data-state='checked']:hover:not(:disabled) {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
}
```

### Admin / prefs copy

| Internal | User label |
|----------|------------|
| `pitch` | Showcase (default) — description: rounded cards, calmer spacing |
| `default` | Newspaper Style — dense terminal layout, original BRIEFR |

Admin toggle: **"Newspaper Style"** (on = classic). Off = showcase (default).  
Remove `UserMenu` showcase `Switch` row entirely.

### Common vendors data

List is hardcoded `VENDORS` in `FilterBar.jsx`. Operator runs Postgres query against `cves.affected_products` (90-day window) and edits the constant. Optional follow-up: script `scripts/suggest_common_vendors.py` (out of scope for v1).

## Testing

- `displayPrefsCore.test.js` — default `uiVariant` is `'pitch'`.
- `backend/tests/test_display_ui_variant.py` — instance default `'pitch'`.
- Manual: FEED filters + vendors, Brief charts empty EPSS, Switch hover, Admin newspaper toggle.

## Docs

- `docs/PRODUCT_STATUS.md` — showcase default, newspaper opt-in.
- `docs/TROUBLESHOOTING.md` — optional note on visual style prefs.
