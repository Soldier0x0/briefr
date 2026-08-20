# INVESTIGATE Obsidian+ — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise INVESTIGATE from ~2/10 to Obsidian+-class UX: local-first graph, buttery camera, RAF decoupled simulation, fly-to Find, keyboard graph navigation, mobile graph tab.

**Architecture:** Keep SVG + `architectureGraphView.js` math. Add pure modules `investigateGraphProjection.js` (Core / Related / Semantic layers), `investigateCameraController.js` (lerp + fly-to + structural refit), `investigateGraphEngine.js` (RAF sim without per-frame React). `InvestigateGraph.jsx` becomes orchestrator; world transform on single `<g id="investigate-world">`.

**Tech Stack:** React 18, SVG, existing force layout (`investigateForceLayout.js`), Radix Checkbox, Node `node:test`, Playwright smoke optional, BrowserStack a11y scan.

**Design spec:** `docs/superpowers/specs/2026-08-20-investigate-obsidian-plus-design.md`

## Global Constraints

- Semantic tokens only — no raw hex in new CSS.
- GraphPage JSON unchanged; GraphNode `extra=forbid`; no live enrichment on canvas.
- Client caps 200 nodes / 300 edges; root preserved.
- Wheel zoom: native `{ passive: false }` + `preventDefault`.
- View model `{ x, y, scale }` shared with architecture graph.
- `prefers-reduced-motion`: no camera/sim tween; instant fit; ≤12 force ticks.
- Hit target ≥ 24px (`--hit-target-min`).
- Merge gate: `./scripts/verify-local.sh`.

---

## File map

| File | Responsibility |
|------|----------------|
| Create: `frontend/src/utils/investigateGraphProjection.js` | Core vs Related vs Semantic layer split |
| Create: `frontend/src/utils/investigateGraphProjection.test.js` | Layer counts, root always visible |
| Create: `frontend/src/utils/investigateCameraController.js` | lerp, flyToView, flyToNode, flyToBounds |
| Create: `frontend/src/utils/investigateCameraController.test.js` | easing reaches target, bounds math |
| Create: `frontend/src/utils/investigateGraphEngine.js` | RAF loop, ref positions, expand tween |
| Create: `frontend/src/utils/investigateGraphEngine.test.js` | settle detection, tween completion |
| Modify: `frontend/src/utils/investigateGraphFilters.js` | Integrate projection; export `buildVisibleGraph` |
| Modify: `frontend/src/utils/investigateGraphFilters.test.js` | Core default excludes heuristic-only nodes |
| Modify: `frontend/src/components/investigate/InvestigateGraph.jsx` | Wire engine + camera; remove per-frame setState |
| Modify: `frontend/src/components/investigate/InvestigateGraph.css` | dot grid, pulse, mobile tabs, sticky camera |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/USE.md` | Obsidian+ behavior |
| Modify: `docs/superpowers/specs/2026-08-20-investigate-canvas-ux-design.md` | Add superseded note at top |

**Do not add** Cytoscape/d3-force/sigma npm packages in this plan.

---

### Task 1: Local-first graph projection

**Files:**
- Create: `frontend/src/utils/investigateGraphProjection.js`
- Create: `frontend/src/utils/investigateGraphProjection.test.js`
- Modify: `frontend/src/utils/investigateGraphFilters.js`
- Modify: `frontend/src/utils/investigateGraphFilters.test.js`

**Interfaces:**
- Consumes: merged graph `{ nodes, edges, root_id }`
- Produces:
  - `splitGraphLayers(graph) → { core, related, semantic, counts }`
  - `applyGraphLayers(graph, { showRelatedCves, showSemantic, ...filters }) → visibleGraph`
  - `heuristicOnlyNodeIds(graph) → Set<string>`

- [ ] **Step 1: Write failing tests**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { splitGraphLayers, applyGraphLayers } from './investigateGraphProjection.js'

describe('splitGraphLayers', () => {
  it('puts heuristic CVE fan in related layer only', () => {
    const graph = {
      root_id: 'n-root',
      nodes: [
        { node_id: 'n-root', entity_type: 'cve', entity_id: 'CVE-1' },
        { node_id: 'n-ioc', entity_type: 'ioc', entity_id: 'ip:1.1.1.1' },
        { node_id: 'n-rel', entity_type: 'cve', entity_id: 'CVE-2' },
      ],
      edges: [
        { source_node_id: 'n-root', target_node_id: 'n-ioc', source_key: 'nvd', edge_class: 'direct_fact' },
        { source_node_id: 'n-root', target_node_id: 'n-rel', source_key: 'related_cve_heuristic', edge_class: 'derived' },
      ],
    }
    const { core, related, counts } = splitGraphLayers(graph)
    assert.equal(core.nodes.length, 2)
    assert.equal(related.nodes.length, 1)
    assert.equal(counts.relatedCves, 1)
  })
})

describe('applyGraphLayers', () => {
  it('defaults to core-only (related off)', () => {
    const graph = { /* same as above */ }
    const visible = applyGraphLayers(graph, { showRelatedCves: false, showSemantic: false })
    assert.ok(visible.nodes.some((n) => n.node_id === 'n-ioc'))
    assert.ok(!visible.nodes.some((n) => n.node_id === 'n-rel'))
  })
})
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && node --test src/utils/investigateGraphProjection.test.js`

- [ ] **Step 3: Implement projection module**

Core rule: edge in core iff `source_key !== 'related_cve_heuristic'`. Node in core if incident to any core edge or is root. Related layer = heuristic-only reachability. Semantic layer unchanged from existing filter.

- [ ] **Step 4: Wire `visibleGraph()` to projection; change default `showRelatedCves` to `false` in `InvestigateGraph.jsx`**

- [ ] **Step 5: Run tests — expect PASS**

Run: `cd frontend && node --test src/utils/investigateGraphProjection.test.js src/utils/investigateGraphFilters.test.js`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/investigateGraphProjection.js frontend/src/utils/investigateGraphProjection.test.js \
  frontend/src/utils/investigateGraphFilters.js frontend/src/utils/investigateGraphFilters.test.js \
  frontend/src/components/investigate/InvestigateGraph.jsx
git commit -m "feat(investigate): local-first core graph layer (related CVEs opt-in)"
```

---

### Task 2: Structural refit policy (fix black canvas)

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

**Interfaces:**
- Replace `userMovedRef` with `structuralVersion` state (number)
- Increment on: resolve, expand merge, showRelatedCves, entityType, edgeClasses, isolate
- On increment: clear camera lock + schedule refit

- [ ] **Step 1: Write failing test** (extract helper)

Create `frontend/src/utils/investigateCameraPolicy.js`:

```javascript
export function shouldRefitAfterStructuralChange({ structuralVersion, lastFitVersion }) {
  return structuralVersion !== lastFitVersion
}
```

Test in `investigateCameraPolicy.test.js`.

- [ ] **Step 2: Implement policy; remove filter-change refit blocked by userMovedRef**

Ensure effect at lines ~586–591 always calls `fitGraphToView()` when `structuralVersion` changes regardless of prior pan.

- [ ] **Step 3: Run unit tests + manual: toggle Related CVEs off/on never leaves blank canvas with selection**

- [ ] **Step 4: Commit**

```bash
git commit -m "fix(investigate): refit on structural filter changes (no black canvas)"
```

---

### Task 3: Camera controller with fly-to

**Files:**
- Create: `frontend/src/utils/investigateCameraController.js`
- Create: `frontend/src/utils/investigateCameraController.test.js`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

**Interfaces:**
- `createCameraController(initialView) → { getDisplayView, setTargetView, flyToView, flyToBounds, tick(dt), isAnimating }`
- `flyToBounds(bounds, viewportW, viewportH, paddingPx)` uses `computeFitView`

- [ ] **Step 1: Write failing tests for lerp completion and flyToBounds centering**

- [ ] **Step 2: Implement easeOutCubic over 280ms default**

- [ ] **Step 3: Integrate: Fit button → `flyToBounds`; filter refit → `flyToBounds(visible positions)`**

- [ ] **Step 4: Run tests**

Run: `cd frontend && node --test src/utils/investigateCameraController.test.js`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(investigate): animated camera controller with fly-to fit"
```

---

### Task 4: RAF graph engine (Obsidian-smooth sim)

**Files:**
- Create: `frontend/src/utils/investigateGraphEngine.js`
- Create: `frontend/src/utils/investigateGraphEngine.test.js`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

**Interfaces:**
- `createGraphEngine({ onSettled, prefersReducedMotion }) → { setTopology(nodes, edges, rootId), setPositions(map), start(), stop(), getPositionsRef }`
- Component applies `transform={`translate(${x},${y}) scale(${scale})`}` on `#investigate-world` from camera display view
- **Remove** `setPositions` inside force RAF loop (lines ~564–575)

- [ ] **Step 1: Write failing test — engine runs N ticks without calling callback more than once at settle**

- [ ] **Step 2: Implement engine with expand tween API: `tweenNodeIn(nodeId, fromX, fromY)`**

- [ ] **Step 3: Refactor InvestigateGraph to read positions from ref for SVG node cx/cy only on `engineVersion` bump (settled/throttled 30fps max for labels if needed)**

- [ ] **Step 4: Profile: confirm no React re-render storm in 10s sim (manual or test hook counting renders)**

- [ ] **Step 5: Commit**

```bash
git commit -m "perf(investigate): decouple force sim from React render loop"
```

---

### Task 5: Find fly-to + match UI

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

- [ ] **Step 1: Add `findMatches` memo — filter visible nodes by substring, max 20**

- [ ] **Step 2: On Enter in Find input — select first match, `camera.flyToNode`**

- [ ] **Step 3: Add `.investigate-node-find-match` pulse ring (respect reduced motion)**

- [ ] **Step 4: Manual test: type partial CVE id → camera animates, node selected**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(investigate): find fly-to and match highlight"
```

---

### Task 6: Keyboard roving + focus

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

- [ ] **Step 1: Add `focusedNodeId` state; roving tabindex on visible nodes**

- [ ] **Step 2: Keydown on canvas: Arrow* cycles `neighborIds(selected)`; Enter select; Shift+Enter expand; Escape clear**

- [ ] **Step 3: Ensure `aria-label` on each interactive node group**

- [ ] **Step 4: Run frontend unit tests; optional BrowserStack `startAccessibilityScan` on `/` investigate tab**

- [ ] **Step 5: Commit**

```bash
git commit -m "a11y(investigate): keyboard roving and focusable graph nodes"
```

---

### Task 7: Mobile graph tab + chrome polish

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

- [ ] **Step 1: Add `@media (max-width: 768px)` layout — `.investigate-mobile-tabs` Graph | Inspector**

- [ ] **Step 2: Camera overlay `position: absolute; bottom: 12px; left: 12px; z-index: 2` always visible**

- [ ] **Step 3: Collapse filter chips into Radix-style disclosure under 1024px**

- [ ] **Step 4: Manual test at 390px width — graph tab shows pannable canvas**

- [ ] **Step 5: Commit**

```bash
git commit -m "ui(investigate): mobile graph tab and sticky camera chrome"
```

---

### Task 8: Related CVE banner + docs

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `docs/PRODUCT_STATUS.md`
- Modify: `docs/USE.md`
- Modify: `docs/superpowers/specs/2026-08-20-investigate-canvas-ux-design.md`

- [ ] **Step 1: When `counts.relatedCves > 0 && !showRelatedCves`, show banner with count + button "Show related CVEs"**

- [ ] **Step 2: Update PRODUCT_STATUS / USE for local-first default**

- [ ] **Step 3: Add superseded banner to P1.5 spec**

- [ ] **Step 4: Run `./scripts/verify-local.sh`**

- [ ] **Step 5: Commit**

```bash
git commit -m "docs(investigate): Obsidian+ local-first UX and related-CVE banner"
```

---

### Task 9: Verification gate

- [ ] **Step 1: Unit:** `cd frontend && npm run test:unit`

- [ ] **Step 2: Build:** `cd frontend && npm run build`

- [ ] **Step 3: Dogfood:** invoke **ce-dogfood** on investigate branch — flows: resolve hub, inspect IOC neighbor, toggle related CVEs, find, keyboard tab-through

- [ ] **Step 4: Capture before/after screen recording for PR**

- [ ] **Step 5: `./scripts/verify-local.sh` green**

---

## Plan self-review (spec coverage)

| Spec requirement | Task |
|------------------|------|
| Core layer default | 1 |
| Related opt-in banner | 8 |
| Structural refit | 2 |
| Camera lerp / fly-to | 3 |
| RAF decoupled sim | 4 |
| Find fly-to | 5 |
| Keyboard a11y | 6 |
| Mobile layout | 7 |
| Success metrics tests | 1–6, 9 |

No placeholders remain. Types consistent across `applyGraphLayers` → `visibleGraph` → engine topology.

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-08-20-investigate-obsidian-plus-plan.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — same session, task-by-task with checkpoints

**Which approach?**

Also confirm: **Related CVEs default OFF** (local-first banner) vs **default ON with cap 8** — before Task 1 lands.
