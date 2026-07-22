# Background Sync portal + Forge ATT&CK navigator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop clipping the Background Sync dropdown and fix Forge ATT&CK coverage so empty/tall columns do not read as a solid black band.

**Architecture:** Rebuild `ApiQueueIndicator` panel on the shared Radix Dropdown/Popover portal pattern used by `UserMenu`. Adjust Forge navigator column min-height / empty-state / contrast so techniques remain readable without inventing a light theme.

**Tech Stack:** React, Radix DropdownMenu or Popover (already approved), `Forge.css`, design tokens.

**Spec SSOT:** [`../specs/2026-07-22-ux-ops-rca-collection-design.md`](../specs/2026-07-22-ux-ops-rca-collection-design.md) Program C.

## Global Constraints

- Portaled + collision-aware overlays (design-system §23).
- z-index from `--z-dropdown` / `--z-popover` — no hardcoded `400`.
- Animate only opacity/transform; honor reduced motion.
- Dark terminal identity preserved (`--bg`, `--bg2`, `--text-*`).
- Merge gate: `./scripts/verify-local.sh`.

---

### Task 1: Portaled Background Sync panel

**Files:**
- Modify: `frontend/src/components/ApiQueueIndicator.jsx`
- Modify: `frontend/src/components/ApiQueueIndicator.css`
- Reference: `frontend/src/components/UserMenu.jsx` (portal pattern)
- Reference: `frontend/src/components/ui/DropdownMenu.jsx` (or Popover primitive if that is what UserMenu uses — follow existing export)
- Test: `frontend/src/components/ApiQueueIndicator.test.js` (create — assert DropdownMenu/Popover import and no absolute `.api-queue-dropdown` positioning as sole strategy)

**Interfaces:**
- Consumes: `apiQueue` prop (unchanged)
- Produces: same operator copy (“Background sync”), portaled content

- [ ] **Step 1: Write structural gate test**

```js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const dir = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(dir, 'ApiQueueIndicator.jsx'), 'utf8')
const css = readFileSync(join(dir, 'ApiQueueIndicator.css'), 'utf8')

describe('ApiQueueIndicator portal', () => {
  it('uses Radix dropdown/popover content', () => {
    assert.match(src, /DropdownMenuContent|Popover\.Content|PopoverContent/)
  })
  it('does not rely on position:absolute panel as only overlay', () => {
    // Allow absolute inside portaled content; forbid old top-level absolute dropdown pattern without portal
    assert.match(src, /DropdownMenu|Popover/)
  })
  it('uses token z-index not raw 400', () => {
    assert.doesNotMatch(css, /z-index:\s*400/)
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && node --test src/components/ApiQueueIndicator.test.js`

- [ ] **Step 3: Implement**

Mirror `UserMenu`:

```jsx
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from './ui/DropdownMenu.jsx' // adjust to real path

export default function ApiQueueIndicator({ apiQueue, className = '' }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={`api-queue-trigger ${className}`} aria-label="Background sync">
          {/* existing clock/badge chrome */}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="api-queue-dropdown"
        align="end"
        sideOffset={6}
        collisionPadding={8}
      >
        <div className="api-queue-dropdown-title">Background sync</div>
        {/* existing list; keep max-height + overflow on inner list only */}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

Move max-height to the scrollable list; ensure portaled content can use full viewport height without `html/body overflow-x: hidden` clipping.

- [ ] **Step 4: CSS cleanup** — remove fixed `z-index: 400`; use portal defaults / `--z-popover`.

- [ ] **Step 5: Tests + commit**

```bash
cd frontend && node --test src/components/ApiQueueIndicator.test.js && npm run build
git add frontend/src/components/ApiQueueIndicator.jsx frontend/src/components/ApiQueueIndicator.css frontend/src/components/ApiQueueIndicator.test.js
git commit -m "fix(ui): portal Background Sync queue popover"
```

---

### Task 2: Forge ATT&CK navigator empty / black-band layout

**Files:**
- Modify: `frontend/src/components/Forge.css` (`.fg-tactic-col-wrap`, `.fg-tactic-col`, empty technique styles)
- Modify: `frontend/src/components/forge/CoverageView.jsx` (empty state per tactic or global empty)
- Test: `frontend/src/utils/forgeMitreNavigatorGate.test.js` (extend)

**Interfaces:**
- Consumes: coverage map from Forge API
- Produces: columns that do not force `min-height: min(70vh, 640px)` empty black slab when data is sparse; show EmptyState when whole coverage is empty

- [ ] **Step 1: Extend gate test for empty-friendly layout**

```js
it('avoids forcing huge empty tactic columns', () => {
  const css = readFileSync(/* Forge.css */, 'utf8')
  // After fix: min-height should be modest or content-driven, not min(70vh, 640px) alone
  assert.doesNotMatch(css, /\.fg-tactic-col\s*\{[^}]*min-height:\s*min\(70vh,\s*640px\)/)
})
```

- [ ] **Step 2: Run — expect FAIL on current CSS**

- [ ] **Step 3: Implement layout fix**

- Lower or remove forced min-height on empty columns; use `min-height` only when techniques exist, or use a smaller floor (`--space-*` based).
- Ensure technique tiles use `--surface-*` / `--text-*` with sufficient contrast vs column background.
- When `coverage` has zero techniques overall, render shared `EmptyState` instead of a row of empty tactic shells.
- Keep sticky Forge subnav under header: if `.fg-nav { top: 0; z-index }` competes with app header, set `top` to header height token / existing shell offset.

- [ ] **Step 4: Build + commit**

```bash
cd frontend && node --test src/utils/forgeMitreNavigatorGate.test.js && npm run build
git add frontend/src/components/Forge.css frontend/src/components/forge/CoverageView.jsx frontend/src/utils/forgeMitreNavigatorGate.test.js
git commit -m "fix(forge): tame ATT&CK navigator empty black-band layout"
```

---

### Task 3: Docs + verify

**Files:** `docs/HANDOVER.md`, `docs/PRODUCT_STATUS.md` (only if operator-visible behavior noted)

- [ ] **Step 1:** Prepend HANDOVER with S5/S6 RCA + portal/navigator fix.
- [ ] **Step 2:** `./scripts/verify-local.sh`
- [ ] **Step 3:** Commit docs.

---

## Self-review

| Spec item | Task |
|-----------|------|
| Portaled Background Sync | Task 1 |
| Token z-index | Task 1 |
| ATT&CK black band | Task 2 |
| Optional other header menus | Out of scope unless leftover time |
