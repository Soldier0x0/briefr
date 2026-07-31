# Showcase UI polish & layout fixes — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make showcase card layout the default, fix layout/behavior bugs, complete CSS coverage, and improve IOC quota readability.

**Architecture:** CSS-first showcase expansion in `pitch-variant.css`; structural fixes in `FilterBar.jsx` and `BriefCharts.css`; global Switch fix in `ui.css`; default flip in `displayPrefsCore.js` + backend defaults + Admin copy; remove UserMenu toggle.

**Tech Stack:** React/Vite frontend, CSS tokens, existing `ui_variant` preference API.

## Global Constraints

- Use semantic tokens only (`--surface-*`, `--text-*`, `--radius-*`, `--space-*`) — no raw hex in components.
- Native checkbox/radio/select prohibited — keep Radix primitives.
- API values remain `default` | `pitch`; only labels and defaults change.
- Minimize scope — no dynamic vendors API in this plan.

---

### Task 1: Switch hover bug (global)

**Files:**
- Modify: `frontend/src/components/ui/ui.css` (~523–536)

- [ ] Add checked+hover rule after `.ui-switch[data-state='checked']`
- [ ] Verify in Admin Display toggles and UserMenu (before removal)

---

### Task 2: Brief charts layout RCA fix

**Files:**
- Modify: `frontend/src/components/BriefCharts.css` (`.brief-charts-grid`, `.brief-chart-canvas-wrap`)
- Modify: `frontend/src/components/BriefCharts.jsx` (`EpssMoversTable` empty state class)

- [ ] Set `.brief-charts-grid { align-items: start; }`
- [ ] Change `.brief-chart-canvas-wrap` to `flex: 0 0 auto` (remove shrink)
- [ ] Empty EPSS: use `brief-chart-empty` with `min-height: 280px`
- [ ] Add `.brief-charts-empty` styles or consolidate to `.brief-chart-empty`

---

### Task 3: Heatmap column size bump

**Files:**
- Modify: `frontend/src/components/TimelineHeatmap.jsx` (`cellSize` desktop 12→14)
- Modify: `frontend/src/App.css` (`.brief-intel-row > .timeline-heatmap` flex-basis comment + value)

- [ ] Recompute flex-basis: labels 12 + gap 6 + 14×14 + 13×2 = 244px

---

### Task 4: Common vendors always visible

**Files:**
- Modify: `frontend/src/components/FilterBar.jsx` (~554)

- [ ] Remove conditional `{(active === 'all' || selectedVendors.length > 0) && (...)}` — always render vendor block
- [ ] Smoke: click KEV — vendors still visible; select Microsoft + KEV — feed narrows correctly

---

### Task 5: IOC quota typography

**Files:**
- Modify: `frontend/src/components/IOCLookup.css` (`.ioc-quota-*` font sizes)

- [ ] Bump `.ioc-quota-asof`, `.ioc-quota-loading`, panel body to `var(--font-size-sm)` / `var(--type-meta)`
- [ ] Chip labels to `var(--type-meta)` minimum; keep mono for quotas numbers if needed

---

### Task 6: Showcase CSS coverage

**Files:**
- Modify: `frontend/src/styles/pitch-variant.css`

- [ ] Add feed: `.filter-btn`, `.filter-search`, `.export-btn`, `.filter-toolbar`
- [ ] Add vendors: `.vendor-filter-block`, `.vendor-btn` (+ active)
- [ ] Add sidebar: `.technique-row`, `.technique-row-active`
- [ ] Add IOC: `.ioc-quota-panel`, `.ioc-quota-chip`, `.ioc-quota-retry-btn`
- [ ] Remove/replace dead `.quick-filter-chip`, `.feed-filter-toolbar`
- [ ] Brief chart cards: `.brief-chart-card`, `.brief-chart-filter-chip`

---

### Task 7: Flip default + Admin copy + remove UserMenu toggle

**Files:**
- Modify: `frontend/src/utils/displayPrefsCore.js` — `DISPLAY_DEFAULTS.uiVariant: 'pitch'`
- Modify: `backend/preferences/display_validate.py` — `DEFAULT_DISPLAY_PREFS["ui_variant"]: "pitch"`
- Modify: `frontend/src/pages/admin/DisplayPage.jsx` — Newspaper Style toggle copy
- Modify: `frontend/src/components/UserMenu.jsx` — remove showcase Switch block + Sparkles import
- Modify: `frontend/src/components/UserMenu.css` — remove toggle row styles if unused
- Test: `frontend/src/utils/displayPrefsCore.test.js`, `backend/tests/test_display_ui_variant.py`, `backend/tests/test_me_preferences.py`

- [ ] Admin label: "Newspaper Style" (on = `default`, off = `pitch`)
- [ ] Instance default button copy updated
- [ ] Tests expect default `pitch`

---

### Task 8: Docs

**Files:**
- Modify: `docs/PRODUCT_STATUS.md`

- [ ] Showcase default; newspaper opt-in via Admin → Display

---

### Task 9: Verify

- [ ] `cd frontend && npm run test:unit`
- [ ] `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_display_ui_variant.py tests/test_me_preferences.py -q`
- [ ] `cd frontend && npm run build`
