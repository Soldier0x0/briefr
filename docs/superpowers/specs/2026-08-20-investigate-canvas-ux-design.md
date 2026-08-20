# INVESTIGATE canvas UX — design spec

**Date:** 2026-08-20  
**Status:** Ready for implementation (P1.5 — canvas UX; reuse existing BRIEFR surfaces)  
**Related:** `docs/plans/2026-08-13-investigation-platform-roadmap.md`, `docs/PRODUCT_STATUS.md`, Admin **System Architecture** graph (`ArchitectureGraphSection.jsx`)

## Why this tab exists

An analyst asking “is this CVE in my world, and what else do I already know about it?” should not have to bounce FEED → drawer → IOC LOOKUP → FORGE and hold the graph in their head.

INVESTIGATE is the **spatial working memory** over intel BRIEFR **already stores**:

| Surface | Job |
|---------|-----|
| FEED | Ranked list / triage |
| CVE drawer | Deep vertical on **one** CVE (Intel / Detect / Related) |
| IOC LOOKUP | **Live** enrichment of one indicator (VT / AbuseIPDB / GreyNoise / OTX) |
| FORGE | Detection coverage + ATT&CK navigator + campaigns |
| ADVISORIES | Publications / headlines |
| Pin overlay (`InvestigationPanel`) | Session thread + PDF export |
| Watchlist | Durable “track this CVE” |
| **INVESTIGATE** | Map of **stored** hops (technique, IOC, campaign, publication, Sigma, related CVE) with honest `edge_class` |

If the map is an illegible clump, the tab has no product reason to exist.

## Architect / analyst decision (locked)

**Graph clicks never live-enrich.** Expand = another stored `GET .../relationships`. Live vendor lookups stay on IOC LOOKUP. From a graph IOC node, **LOOKUP LIVE** is an explicit pivot (`InvestigationContext.pivotToIoc`) — same contract as the drawer.

**Do not clone product surfaces.** Inspector actions call existing navigation:

| Node | Action | Existing hook |
|------|--------|----------------|
| CVE | OPEN CVE | `onOpenCve` → `openCveById` (already wired) |
| CVE | PIN WATCHLIST | `useWatchlist.togglePin` (pass from `App.jsx` like the drawer) |
| CVE / IOC / technique | PIN THREAD | `ensureCveInThread` / `recordIocPivot` / `recordItem` (already wired) |
| IOC | LOOKUP LIVE | `pivotToIoc(value)` → tab `ioc` + prefill |
| Technique | OPEN IN FORGE | `pivotToTechnique` → `openForgeTechnique` |
| Campaign | OPEN CAMPAIGNS | `openForgeCampaigns` (`view=campaigns`) |
| Publication | OPEN ADVISORIES | `setActiveTab('atlas')` + existing publication cards (CVE chips already open drawer) |

**Camera is not a new invention.** Admin System Architecture already ships cursor-anchored wheel zoom, drag pan, FIT GRAPH, RESET VIEW, `touch-action: none`, and `{ passive: false }` wheel listeners (`architectureGraphView.js` + `ArchitectureGraphSection.jsx`). INVESTIGATE must **reuse that view model** `{ x, y, scale }` and `zoomAtCursor` — not a second `{ k, tx, ty }` camera module.

## Scroll / wheel — current evidence (does **not** work today)

`InvestigateGraph.jsx` has **no** `wheel` listener, **no** pan, **no** Fit. Wheel over the canvas scrolls the **page**.

The working pattern (copy, do not rewrite):

```123:136:frontend/src/pages/security-architecture/sections/ArchitectureGraphSection.jsx
  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const handler = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const cursorX = e.clientX - rect.left
      const cursorY = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      setView(v => zoomAtCursor(v, cursorX, cursorY, factor))
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [graph])
```

`zoomAtCursor` keeps the **graph point under the cursor** fixed (`architectureGraphView.js`). Trackpad pinch typically arrives as `wheel` + `ctrlKey`; still use `deltaY` (same as architecture). **React `onWheel` is passive in browsers — it cannot `preventDefault`. Native listener is required.**

Also required (already on `.sa-graph-canvas`): `overflow: hidden; touch-action: none;` so the page does not steal the gesture.

Buttons are not optional: `+` / `−` / FIT / RESET (architecture has FIT + RESET; INVESTIGATE adds `+`/`−` because analysts on a laptop often lack a wheel). Keyboard when canvas focused: `+`/`=` zoom in, `-` zoom out, `0` Fit, arrows pan.

## Problem (production canvas)

| Symptom | RCA |
|---------|-----|
| Tiny star in empty canvas | No camera; 1:1 paint |
| Wheel does nothing useful | No non-passive wheel handler |
| Labels unreadable | Always-on 28-char labels |
| Click feels violent | `onClick` → `expandNode` (merge GraphPage) |
| Truncated with no next step | `next_cursor` dropped in `mergeGraphPage` |
| Related-CVE hairball | `related_cve_heuristic` up to `limit` (50) as equal-weight nodes |
| Physics clumps | Viewport pad clamp + `SPRING_LENGTH=140` + **repulsion off if n>80** |
| Inspector is thin | Type/id/knowledge only — **ignores** `source_key`, `edge_class`, `observed_at`, `fetched_at`, `confidence` already on `GraphEdge` |
| No find / type filter | Architecture graph already has cluster tabs + node search |

## Goals

1. **Readable map** — Fit after layout; neighborhood uses the canvas.
2. **Map navigation** — wheel zoom at cursor, drag pan, `+`/`−`/FIT/RESET, keyboard.
3. **Inspect ≠ expand** — click select; double-click / EXPAND pivot stored hops.
4. **LOD labels** + inverse-scaled hit targets.
5. **Evidence in the inspector** — incident edges with class, source, timestamps.
6. **Density honesty** — related-CVE toggle; type chips; find-in-graph highlight.
7. **Pivot into existing BRIEFR** — drawer, live IOC, Forge, watchlist, thread PDF.
8. **Reuse architecture camera** — no second math library, no graph npm package.

## Non-goals

- Graph database; Cytoscape / d3 / sigma / vis-network.
- Live enrichment on expand or hover.
- Saved cases / sharing (thread PDF already exists).
- Changing hop SQL / `IocKind` / email-mutex nodes.
- Minimap (defer).
- Replacing `InvestigationPanel` or FORGE.
- Hiding related CVEs by default (honesty: default **on**, toggle to thin the star).

## Approaches

**A — Camera only.** Reject as sole fix.  
**B — Reuse architecture view + layout + inspect + density + inspector evidence + pivots.** Chosen.  
**C — New graph library.** Rejected.

## Design

### 1. Camera (reuse)

View state: `{ x, y, scale }` from `architectureGraphView.js` (`DEFAULT_VIEW`, `MIN_SCALE=0.15`, `MAX_SCALE=4`, `FIT_MIN_SCALE=0.08`).

- Wheel: copy architecture handler (`preventDefault`, cursor in **canvas CSS pixels**, `zoomAtCursor`).
- Drag empty canvas: copy architecture pointer pan (`origin.x + dx`).
- Drag node: move world `x,y`, `vx=vy=0` (architecture does not drag nodes; this is INVESTIGATE-only).
- FIT: `computeFitView(computePointCloudBounds(positions), width, height)` — add `computePointCloudBounds` next to existing `computeGraphBounds` (rects vs circles).
- After force **settles**, auto-Fit unless the user has already pan/zoomed.
- RESET: Fit again (architecture `resetView` = Fit), not identity scale-1 (identity is what makes the star tiny).

### 2. Force layout (world, unbounded)

Keep `investigateForceLayout.js`. Remove viewport pad clamp. Grid repulsion always. Spring length scales with `sqrt(n)`. Center force on **root only**. Type-ring seed (root at center; techniques inner; IOC/campaign/publication mid; other CVEs outer). `stepForce(..., rootId)`.

### 3. Gestures

| Input | Action |
|-------|--------|
| Wheel / pinch-as-wheel | Zoom at cursor |
| Drag canvas | Pan |
| Drag node | Reposition |
| Click node | Select (inspector) |
| Click selected node | Deselect (architecture pattern) |
| Double-click / inspector EXPAND / Shift+Enter | Stored expand |
| Click background | Clear selection |
| `+` `-` `0` arrows | Zoom / Fit / pan |

### 4. Labels (LOD) + glyphs

Always: root, selected, hovered, find-match. `scale >= 1.25`: non-CVE types. `scale >= 2`: all. Use existing `truncateNodeLabel`. Hit radius `clamp(8, 12/scale, 24)` in **world** space. Shapes: CVE circle, IOC diamond, technique/sigma/publication square, campaign hex; root larger; heuristic-only CVEs r=6.

### 5. Inspector (analyst evidence)

Show selected node + **incident edges** (`source_node_id` or `target_node_id` === selected):

- `edge_class`, `source_key`, `confidence`, `observed_at`, `fetched_at`
- Neighbor id (click selects neighbor)

Actions (only those that apply):

- EXPAND (stored)
- OPEN CVE / LOOKUP LIVE / OPEN IN FORGE / OPEN CAMPAIGNS
- PIN THREAD / PIN WATCHLIST
- COPY ID
- PIN VISIBLE CVEs (loop `ensureCveInThread` on currently visible CVE nodes — feeds existing PDF)

### 6. Density filters (client-first)

API already has `edge_class`, `include_semantic`, `cursor`. Do **not** add backend ranking in this spec.

- **Related CVEs** Radix checkbox, default on — hide nodes **only** reached via `related_cve_heuristic`.
- **Type chips** (architecture cluster tabs pattern): ALL / CVE / IOC / TECHNIQUE / CAMPAIGN / PUB — hide others; Fit on change.
- **Find** input: highlight matches (`sa-graph-node-match` analogue); **do not hide** topology (unlike architecture search). Enter pans camera to first match.
- **Semantic** checkbox: refetch relationships with `include_semantic=1` (API default false).
- Hover/select: dim non-neighbors; emphasize incident edges (architecture `connectedEdgeIds`).

### 7. Load more

`mergeGraphPage` keeps `cursorsByNodeId`. Honesty **LOAD MORE** when selected/root has a cursor and canvas not capped.

### 8. Deep link

`?tab=investigate&q=CVE-2026-68820` hydrates the search box and runs resolve (pushContext). Leaving the tab may drop `q` in `buildAppTabSearchParams` when `nextTab !== 'investigate'`.

### 9. Chrome

Canvas `flex: 1`, `overflow: hidden`, `touch-action: none` (copy `.sa-graph-canvas`). Overlay tools bottom-left. Inspector 260px. Shrink hero to one title line.

## Success criteria

1. Wheel over canvas zooms at cursor; **page does not scroll** (non-passive listener).
2. `+`/`−`/FIT/RESET work without a wheel.
3. After resolve of a 50-neighbor CVE, auto-Fit fills the canvas.
4. Click inspects; node count unchanged; double-click expands.
5. Inspector lists incident `source_key` / `edge_class`.
6. LOOKUP LIVE / OPEN CVE / OPEN IN FORGE / PIN WATCHLIST call existing hooks (no new APIs).
7. Related-CVE toggle and type chips change the visible graph; Find highlights without hiding.
8. Truncated + cursor → LOAD MORE.
9. Unit tests: `zoomAtCursor` (existing) + point-cloud Fit; force n>80; merge cursors; related-CVE filter.
10. No new graph npm package; GraphPage JSON unchanged.

## Explicitly deferred

Server-side related-CVE cap; minimap; email/mutex entity types; persisted camera; PNG export (thread PDF is the IR artifact).
