# INVESTIGATE canvas — Obsidian+ design spec

**Date:** 2026-08-20  
**Status:** Draft — supersedes UX *quality bar* in `2026-08-20-investigate-canvas-ux-design.md` (P1.5 mechanics remain; product defaults and motion model change)  
**Benchmark:** Obsidian Graph view (smooth pan/zoom, local-first readability) — **target: measurably better for CVE intel workflow**

## Executive summary

P1.5 fixed “no camera” (wheel zoom, Fit, inspect vs expand). Hands-on testing and production feedback show the tab is still **~2/10** for analysts: first paint is a **related-CVE star** that pushes IOCs/techniques off the canvas, filters can leave a **black graph** while the inspector still shows a node, Find does not **fly-to**, keyboard focus on SVG nodes is broken, and motion feels **stepwise** (React re-render per force tick) rather than **Obsidian-smooth**.

This spec defines **Obsidian+**: local-first stored-intel map, buttery camera, progressive disclosure of heuristic bulk, and BRIEFR-only advantages (evidence edges, pivots, watchlist/thread marks) — without cloning Obsidian’s note-graph semantics.

---

## Obsidian benchmark (what “smooth” means)

| Dimension | Obsidian Graph | INVESTIGATE today | Obsidian+ target |
|-----------|----------------|-------------------|------------------|
| **First paint** | Local neighborhood around active note | Up to 50 `related_cve_heuristic` nodes as equal citizens | **Hub + 1-hop incident** only; heuristic CVEs opt-in |
| **Pan/zoom** | GPU transform, continuous, cursor-anchored | Cursor-anchored but stateful jumps; no inertia/lerp | **RAF-interpolated view**; optional pan inertia |
| **Simulation** | Continuous low-energy forces; pause control | 180 ticks then freeze; `setState` every frame | **Decoupled sim loop**; settle + gentle idle or static + expand tween |
| **Search** | Highlights + centers camera | Weak label LOD only | **Select + pulse + fly-to** |
| **Filters** | Groups/tags hide classes | Toggle can empty canvas without refit | **Always refit visible set**; never empty-with-selection |
| **Text** | Size scales with zoom smoothly | Step LOD thresholds | **Continuous opacity/size** by zoom |
| **Keyboard** | Arrow between linked notes | Tab does not enter graph | **Roving tabindex** on nodes; Enter/Space/Shift+Enter |
| **Mobile** | Usable (app) | Graph tab empty / stacked | **Full-viewport graph + bottom-sheet inspector** |
| **Evidence** | None (links only) | `edge_class`, `source_key` (underused visually) | **Edge styling + inspector** as differentiator |

**Beat Obsidian on:** provenance-aware edges, pivot to drawer/IOC/Forge/advisories, session marks, honest derived vs fact — on a canvas that feels *at least* as fluid.

---

## Root cause (why P1.5 ≠ 10/10)

1. **Data-on-canvas policy** — API returns up to 50 related CVEs; client merges all; force layout places them in an outer ring → **orange star** dominates viewport and caps hide IOC/technique nodes (50-node page limit).
2. **Camera policy conflict** — `userMovedRef` blocks auto-Fit after filter changes; spec said “Fit on filter change” but user pan/zoom poisons later refits → **black canvas**.
3. **Render architecture** — force loop calls `setPositions` every RAF → full React+SVG reconcile → **jank vs Obsidian’s transform-only pipeline**.
4. **Find/keyboard incomplete** — no `flyToNode`, no focusable `<g role="button">` / roving grid.
5. **Chrome density** — controls compete with canvas; camera overlay not always visible.

---

## Product principles (locked for Obsidian+)

1. **Local-first, honest-second** — Default view shows **stored incident neighborhood** (root + edges that are not `related_cve_heuristic`). Heuristic bulk is **available, labeled, counted**, but not painted until the analyst opts in. This is not hiding data: inspector + “Show N related CVEs” banner state what the API returned.
2. **Camera never lies** — If nodes are visible in the merged graph, the camera **frames them** after any filter/layer/resolve/expand. User manual zoom/pan is preserved only until the next **structural** change (filter, resolve, expand, find fly-to).
3. **Motion is a feature** — Pan/zoom/fit use **eased interpolation** (respect `prefers-reduced-motion`: instant jump).
4. **Inspect ≠ expand** (unchanged) — click select; double-click / EXPAND / Shift+Enter stored hops only.
5. **No live enrichment on canvas** (unchanged).
6. **GraphPage contract frozen** (unchanged) — client-side projection/filter only unless a separate API proposal is approved.

---

## Approaches

### A — Polish P1.5 (defaults + refit + find only)

Fix related-CVE default off, force refit on filters, implement fly-to, sticky camera chrome.  
**Pros:** Small diff, fast. **Cons:** SVG+React sim loop still caps smoothness ~**7/10**.  
**Reject as sole path.**

### B — Obsidian+ render engine (recommended)

Keep SVG + existing camera math; add **`investigateGraphEngine.js`**: refs for view/positions, single RAF driver, `transform` on one `<g>`, React renders structure only when topology/selection changes. Add **local-first projection** in `investigateGraphFilters.js`.  
**Pros:** No new npm graph lib; hits **9/10** smoothness; aligns with architecture camera reuse. **Cons:** Medium refactor of `InvestigateGraph.jsx`.

### C — Canvas/WebGL library (sigma.js / Pixi)

**Pros:** Best perf at 500+ nodes. **Cons:** New dependency, a11y harder, diverges from architecture SVG patterns.  
**Defer** unless profiling proves B insufficient at 200-node cap.

**Recommendation:** **B**, with A’s product fixes as Phase 1 inside B.

---

## Design

### 1. Graph scopes (layers)

Three **client layers** applied in order:

| Layer | Default | Source |
|-------|---------|--------|
| **Core** | ON | Root + all nodes/edges **except** edges with `source_key === 'related_cve_heuristic'` |
| **Related CVEs** | OFF | Nodes/edges only reachable via heuristic edges |
| **Semantic** | OFF | `edge_class === 'semantic'` (unchanged opt-in refetch) |

**First resolve** paints Core only, auto-Fits, shows banner:  
`47 related CVEs available · Show related CVEs` (count from API).

Type chips, edge-class chips, Isolate, Find operate on **visible layer union**.

### 2. Camera engine

Reuse `architectureGraphView.js` (`zoomAtCursor`, `computeFitView`, `computePointCloudBounds`).

New **`investigateCameraController.js`**:

- State: `view` (target), `viewAnimated` (display), `animating: boolean`
- `flyToView(target, { durationMs: 280, ease: 'easeOutCubic' })`
- `flyToNode(nodeId, positions, viewport)` — Fit padding 80px around node + 1-hop bbox
- `flyToVisible(visibleNodes, viewport)` — filter/resolve/expand refit
- Wheel: update target immediately; display lerps (optional 1-frame lag max)
- **`structuralVersion` counter** — increment on filter/resolve/expand; resets “user moved” lock and triggers refit

Replace `userMovedRef` boolean with:

- `userCameraLockUntilStructuralChange` — pan/zoom wheel sets lock; **any structural change clears lock and refits**

### 3. Simulation engine

New **`investigateGraphEngine.js`**:

- Holds `positionsRef`, `velocitiesRef`
- RAF loop:
  - Phase **simulate** (force ticks while `energy > epsilon` or max 240 ticks on load)
  - Phase **idle** (0–2 ticks/frame optional micro-settle)
  - Phase **expand tween** — new nodes lerp from parent position over 300ms
- **No React setState per frame** — mutate refs; write `transform` attribute on `#investigate-world`
- React re-render on: selection, hover, topology change, filter change, sim **settled** (once)

`prefers-reduced-motion`: 12 ticks, no tween, instant fit.

### 4. Visual system (BRIEFR tokens, Obsidian clarity)

- **Background:** `--surface-base` subtle dot grid (CSS on canvas, parallax optional off)
- **Edges:** incident edges 1.5px; non-incident dimmed 40%; heuristic dashed when layer on
- **Nodes:** type glyphs unchanged; **root glow** ring; selected **pulse** (CSS `@keyframes` on `<circle>` only when reduced-motion off)
- **Labels:** opacity = `clamp((scale - 0.4) * 1.2, 0, 1)`; always on for root/selected/find-match
- **Hover:** 1-hop highlight (Obsidian-style local focus)

### 5. Find

- Debounced match list (max 20)
- Enter / click match → `selectNode` + `flyToNode`
- `/` focuses Find when canvas focused (not global FEED `/`)

### 6. Keyboard & a11y

- Canvas `tabIndex={0}`; roving `tabIndex={0}` on visible nodes
- Arrow keys: cycle neighbors by incident edge order
- Enter: select; Space: toggle select; Shift+Enter: expand
- Escape: clear selection
- Every node: `role="button"`, `aria-label={`${type} ${label}`}`

BrowserStack **`scan-and-fix-accessibility`** gate before merge.

### 7. Layout / chrome

- **Desktop:** graph flex-1 min-height 480px; inspector 280px sticky; camera **floating** bottom-left always visible
- **Mobile ≤768px:** tabs `Graph | Inspector`; graph full viewport; inspector bottom sheet
- Collapse filter row into **“Filters”** disclosure when width < 1024px

### 8. Expand behavior

- Double-click expand merges page → **expand tween** from parent
- After merge: if Core layer, Fit **new neighborhood** not full heuristic cloud
- **Load more** unchanged

### 9. Success metrics (10/10 definition)

| # | Criterion |
|---|-----------|
| 1 | Resolve CVE hub: **≤12 nodes** on first paint (Core), IOC/technique visible without scrolling Fit |
| 2 | Pan/zoom **≥55fps** median on 100-node graph (Chrome perf trace, no setState in sim loop) |
| 3 | Toggle Related CVEs ON → graph refits within **300ms**; never blank while inspector shows selection |
| 4 | Find → camera flies to node; selected ring visible |
| 5 | Tab into graph → focus visible node; arrow keys move |
| 6 | 390px: graph tab shows interactive canvas |
| 7 | `prefers-reduced-motion`: no tween; instant fit |
| 8 | Unit tests: local-first filter, flyTo bounds, structural refit lock |
| 9 | Playwright smoke: resolve → inspect → filter → find |
| 10 | Analyst dogfood: **ce-dogfood** report ≥ “experiential pass” on investigate flows |

---

## Non-goals (this spec)

- Graph DB / server-side layout
- Live VT on hover
- Node drag reposition persist
- KEV/EPSS on nodes (drawer only)
- Replacing InvestigationPanel

## Deferred (P2)

- Minimap (Obsidian parity)
- Force sliders (repulsion/link distance)
- `sessionStorage` camera per root id
- Canvas/WebGL if >200 nodes becomes normal

---

## Open product decision (needs your call)

**Default Related CVE layer:** This spec sets **OFF** (local-first). P1.5 locked **ON** for “honesty.” Obsidian+ treats honesty as **banner + one-click reveal**, not **paint everything**.

If you prefer default ON with **cap (e.g. 8)** instead of OFF, say so before implementation — it changes first-paint layout only, not engine work.
