# UI polarity, toggles, and chip deselect — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix context-blind PATCHES delta coloring, oversized Your Filters toggle, and sticky chips that claim `aria-pressed` without allowing deselect (Catch-up presets + sibling sweep).

**Architecture:** Teach `StatCell` a delta polarity (`worse-up` vs `better-up`). Replace Sidebar custom `Toggle` with shared `Switch` (or square checkbox if maintainer prefers same-size box). Add a small `toggleOrSet` helper for optional chips; apply to Catch-up first, then listed siblings.

**Tech Stack:** React 19 JSX/CSS, Radix `Switch`, design tokens, existing admin `filter-chip` / `Pill` patterns.

**Spec SSOT:** [`../specs/2026-07-22-ux-ops-rca-collection-design.md`](../specs/2026-07-22-ux-ops-rca-collection-design.md) Program B.

## Global Constraints

- Never hardcode colors — use `--severity-*` / `--status-*` / `--text-*` / existing `.stat-delta--*` tokens; if new classes needed, define with semantic tokens in CSS.
- Red only for worse/destructive — not for “more patches.”
- Prefer shared `Switch` over a new toggle primitive.
- Interactive targets ≥ 24px.
- Merge gate: `./scripts/verify-local.sh`; frontend unit tests for helpers.

---

### Task 1: Context-aware stat deltas (PATCHES)

**Files:**
- Modify: `frontend/src/components/StatsRow.jsx`
- Modify: `frontend/src/components/StatsRow.css` (only if new class names)
- Test: `frontend/src/components/StatsRow.test.js` (create)

**Interfaces:**
- Consumes: `delta` number on `StatCell`
- Produces: `deltaPolarity?: 'worse-up' | 'better-up'` (default `'worse-up'` for CRITICAL/HIGH/KEV/EPSS)

- [ ] **Step 1: Write failing unit test**

```js
// frontend/src/components/StatsRow.test.js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { deltaToneClass } from './StatsRow.jsx' // export the helper

describe('deltaToneClass', () => {
  it('treats positive PATCHES (better-up) as good', () => {
    assert.equal(deltaToneClass(3, 'better-up'), 'stat-delta--down') // green in current CSS
    // OR if renaming: 'stat-delta--good'
  })
  it('treats positive CRITICAL (worse-up) as bad', () => {
    assert.equal(deltaToneClass(3, 'worse-up'), 'stat-delta--up')
  })
  it('treats negative better-up as bad', () => {
    assert.equal(deltaToneClass(-2, 'better-up'), 'stat-delta--up')
  })
})
```

Prefer renaming CSS to `--good` / `--bad` if clearer; if so, migrate all three classes in the same PR and update tests accordingly.

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && node --test src/components/StatsRow.test.js`

- [ ] **Step 3: Implement helper + wire PATCHES**

```js
export function deltaToneClass(delta, polarity = 'worse-up') {
  if (delta == null || delta === 0) return null
  const upIsBad = polarity !== 'better-up'
  const isUp = delta > 0
  const bad = upIsBad ? isUp : !isUp
  return bad ? 'stat-delta--up' : 'stat-delta--down'
}
```

Pass `deltaPolarity="better-up"` only on PATCHES AVAILABLE. Keep tooltip honest: “Change in publications vs prior 24h” is fine for publication deltas; for patches keep the same window copy unless PRODUCT_STATUS defines otherwise.

- [ ] **Step 4: Run test — PASS; commit**

```bash
cd frontend && node --test src/components/StatsRow.test.js
git add frontend/src/components/StatsRow.jsx frontend/src/components/StatsRow.css frontend/src/components/StatsRow.test.js
git commit -m "fix(ui): context-aware polarity for PATCHES stat deltas"
```

---

### Task 2: Your Filters toggle sizing via shared Switch

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx` (remove local `Toggle`, use `Switch`)
- Modify: `frontend/src/components/Sidebar.css` (delete oversized custom toggle rules if unused)
- Modify: `frontend/src/components/ui/ui.css` only if Switch thumb/track ratio needs a density variant — prefer adjusting shared `.ui-switch` / `.ui-switch-thumb` once with design-system tokens
- Test: visual gate optional; unit: assert Sidebar imports Switch

**Interfaces:**
- Consumes: `frontend/src/components/ui/Switch.jsx`
- Produces: Sidebar filters use `Switch` with `label` + hint via existing HelpTip/ControlTooltip pattern

- [ ] **Step 1: Confirm current defect sizes**

In `Sidebar.css`, custom toggle track uses `--hit-target-min` (36×24) with ~10px thumb. Shared `.ui-switch` is closer but still track > thumb (expected for switches). Maintainer locked decision: prefer shared Switch; if they insist on identical box/thumb, use `Checkbox` instead for those rows.

- [ ] **Step 2: Replace Toggle**

```jsx
import Switch from './ui/Switch.jsx'

// inside Your Filters section
<Switch
  id="filter-kev"
  checked={!!filters.kev_only}
  onCheckedChange={(v) => onChange({ ...filters, kev_only: v })}
  label="KEV only"
/>
```

Remove the local `function Toggle(...)` and its CSS.

- [ ] **Step 3: If Switch thumb still feels tiny, bump shared tokens once**

In `ui.css`, scale thumb relative to track (e.g. thumb ~60% of track height) using `--space-*` / fixed rem already used by `.ui-switch`. Do not invent page-local focus rings.

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/components/Sidebar.jsx frontend/src/components/Sidebar.css frontend/src/components/ui/ui.css
git commit -m "fix(ui): use shared Switch for Your Filters toggles"
```

---

### Task 3: Optional chip deselect (Catch-up + sweep)

**Files:**
- Create: `frontend/src/utils/toggleChipSelection.js`
- Create: `frontend/src/utils/toggleChipSelection.test.js`
- Modify: `frontend/src/pages/admin/CatchupCard.jsx` (`selectPreset`)
- Modify (sweep, same PR if small): `frontend/src/components/WhatChangedPanel.jsx`, `frontend/src/components/MorningBrief.jsx`, `frontend/src/components/FilterBar.jsx` (quick filters that use `aria-pressed` without off-path), admin chip bars that are optional filters — **do not** force deselect on exclusive status radios that require a value (e.g. Audit “All” vs prefix may stay sticky for All)

**Interfaces:**
- Produces:

```js
/** If clicking the active value, clear to `cleared`; else set `next`. */
export function toggleChipSelection(current, next, cleared = null) {
  return current === next ? cleared : next
}
```

- [ ] **Step 1: Failing tests for helper**

```js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { toggleChipSelection } from './toggleChipSelection.js'

describe('toggleChipSelection', () => {
  it('selects when inactive', () => {
    assert.equal(toggleChipSelection(null, 6), 6)
  })
  it('clears when re-clicking active', () => {
    assert.equal(toggleChipSelection(6, 6, null), null)
  })
})
```

- [ ] **Step 2: Implement helper + Catch-up**

```js
function selectPreset(hours) {
  setSelectedHours((prev) => {
    const next = toggleChipSelection(prev, hours, null)
    if (next == null) {
      // keep a sensible default for Start — use 6h default from design, or disable Start until chosen
      return null
    }
    return next
  })
  setCustomEnd('')
}
```

Product rule (locked here): re-click clears preset highlight; if `selectedHours == null` and no custom end, **Start Catch-up** stays disabled (already likely). Default on first open remains 6h from existing card state — only clear after explicit re-click.

- [ ] **Step 3: Sibling sweep checklist** (tick in PR description)

| Surface | Deselect on re-click? |
|---------|----------------------|
| CatchupCard 2h/6h/8h | Yes |
| WhatChanged field/since chips | Yes if optional |
| MorningBrief reason chips | Yes (`all` may be sticky) |
| FilterBar quick filters | Yes where mutually exclusive optional |
| Watchlist/Scheduler/Audit chips | Only if optional filter; keep required status |

- [ ] **Step 4: Unit tests + verify-local + commit**

```bash
cd frontend && npm run test:unit
./scripts/verify-local.sh
git add frontend/src/utils/toggleChipSelection.js frontend/src/utils/toggleChipSelection.test.js frontend/src/pages/admin/CatchupCard.jsx
# plus swept files
git commit -m "fix(ui): allow re-click deselect on optional filter chips"
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| PATCHES polarity | Task 1 |
| Your Filters sizing / shared Switch | Task 2 |
| Chip deselect + Catch-up exemplar | Task 3 |
| No new toggle primitive | Task 2 |
