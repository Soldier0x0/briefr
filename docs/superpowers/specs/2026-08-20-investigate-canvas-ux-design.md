# INVESTIGATE canvas UX — design spec

**Date:** 2026-08-20  
**Status:** Ready for implementation (P1.5 — canvas UX; reuse existing BRIEFR surfaces)  
**Related:** `docs/plans/2026-08-13-investigation-platform-roadmap.md`, `docs/PRODUCT_STATUS.md`, Admin **System Architecture** graph (`ArchitectureGraphSection.jsx`)

## Scroll / zoom — current evidence (does **not** work today)

INVESTIGATE **cannot** zoom or pan today. There is no wheel listener, no `+`/`−`, no FIT, no RESET.

| Control | INVESTIGATE today | Architecture graph (working) | This spec |
|---------|-------------------|------------------------------|-----------|
| Mouse wheel / trackpad | Scrolls the **page** | Cursor-anchored zoom | Copy architecture |
| `+` / `−` buttons | Missing | Missing there too | **Add** (laptops often have no wheel) |
| FIT GRAPH / RESET VIEW | Missing | Present; RESET = Fit | Copy labels + behavior |
| Drag pan | Missing | Pointer capture on empty canvas | Copy |
| Keyboard `+` `−` `0` arrows | Missing | Missing | Add when canvas is focused |

Working pattern — copy, do not rewrite (`ArchitectureGraphSection.jsx`):

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

`zoomAtCursor` keeps the graph point under the cursor fixed (`architectureGraphView.js`). Trackpad pinch typically arrives as `wheel` + `ctrlKey`; still use `deltaY` (same as architecture). **React `onWheel` is passive in browsers — it cannot `preventDefault`. Native listener is required.**

Also required (already on `.sa-graph-canvas`): `overflow: hidden; touch-action: none;` so the page does not steal the gesture.

RESET VIEW = Fit (architecture already does this). Identity scale-1 is what makes the production star tiny — never reset to that.

## Why this tab exists

An analyst asking “is this CVE in my world, and what else do I already know about it?” should not have to bounce FEED → drawer → IOC LOOKUP → FORGE and hold the graph in their head.

INVESTIGATE is the **spatial working memory** over intel BRIEFR **already stores**:

| Surface | Job |
|---------|-----|
| FEED | Ranked list / triage |
| CVE drawer | Deep vertical on **one** CVE (Intel / Detect / Related) — KEV, EPSS, CVSS, stack |
| IOC LOOKUP | **Live** enrichment of one indicator (VT / AbuseIPDB / GreyNoise / OTX) |
| FORGE | Detection coverage + ATT&CK navigator + campaigns |
| ADVISORIES | Publications / headlines (`tab=atlas`) |
| Pin overlay (`InvestigationPanel`) | Session thread + PDF export |
| Watchlist | Durable “track this CVE” |
| **INVESTIGATE** | Map of **stored** hops with honest `edge_class` |

If the map is an illegible clump, the tab has no product reason to exist.

## Architect / analyst decisions (locked)

These are product rules, not a wishlist. Each one is grounded in code that already exists.

### 1. Graph clicks never live-enrich

Expand = another stored `GET /api/investigations/entities/{type}/{id}/relationships`. Live vendor lookups stay on IOC LOOKUP. From a graph IOC node, **LOOKUP LIVE** is an explicit pivot — same contract as the drawer.

Heavy work never runs on the request path (`docs/CONTRIBUTOR_RULES.md`).

### 2. Do not clone product surfaces

Inspector actions call existing navigation:

| Node | Action | Existing hook | Notes |
|------|--------|----------------|-------|
| CVE | OPEN CVE | `onOpenCve` → `openCveById` | Already wired. KEV / EPSS / stack live **here**, not on the node. |
| CVE | PIN WATCHLIST | `handleWatchlistChange(id, 'pin')` | Second arg **must** be `'pin'` or the handler no-ops (`App.jsx`). |
| CVE / IOC / technique | PIN THREAD | `ensureCveInThread` / `recordIocPivot` / `recordItem` | Feeds existing PDF overlay. |
| CVE (visible set) | PIN VISIBLE CVEs | loop `ensureCveInThread` | IR packet without a new export format. |
| IOC | LOOKUP LIVE | `pivotToIoc(value, from, indicatorType)` | **Must pass IocKind.** `entity_id` is `kind:value` (`ip:` / `hash:` / `domain:` / `url:`). Today `pivotToIoc` hardcodes `type: 'ip'` — extend with a third arg. Do not pass `ip:1.1.1.1` as the lookup value. |
| Technique | OPEN IN FORGE | `pivotToTechnique` | Existing. |
| Campaign | OPEN CAMPAIGNS | `openForgeCampaigns` (`view=campaigns`) | Lives on `App.jsx`, **not** on InvestigationContext. GraphNode has no `members`, so do **not** call `pivotToCampaign` (that API needs a campaign object). |
| Publication | OPEN ADVISORIES | new `openAdvisories` in App: `tab=atlas&view=advisories` | Same pattern as `openForgeCampaigns`. |
| Any | COPY ID | `copyToClipboard` in `utils/report.js` | Not raw `navigator.clipboard` (HTTP fallback). |
| Any | COPY NEIGHBORHOOD | same helper + markdown of incident edges | Ticket paste. |

### 3. Camera is not a new invention

Reuse `{ x, y, scale }`, `zoomAtCursor`, `computeFitView` from `architectureGraphView.js`. Add `computePointCloudBounds` next to `computeGraphBounds` (rects vs circles). **Do not create `investigateCamera.js`.**

Do **not** copy architecture’s “draw edges only when a node is focused”. That graph is a generated topology. INVESTIGATE is an evidence map — all fetched edges stay visible; selection **dims** non-neighbors; an **Isolate** checkbox hides the rest.

Do **not** drag nodes in this spec. Pan empty canvas only. Node drag fights click-select and is not on the architecture graph.

### 4. GraphNode stays frozen (`extra=forbid`)

`backend/investigations/contracts.py` GraphNode fields: `node_id`, `entity_type`, `entity_id`, `label`, `knowledge_state`. **No KEV, EPSS, CVSS, stack, pin.** Related-CVE hops already drop cvss/epss from SQL.

Client overlays that do **not** change the contract:

- Watchlist: `watchlist.getState(entity_id) === 'pin'` → pin mark on CVE nodes.
- Thread: `investigation.isCveInThread(entity_id)` → ring on CVE nodes.
- Heuristic-only related CVEs: smaller radius (detected via `source_key === 'related_cve_heuristic'` on incident edges).

KEV / EPSS / “affects my stack” stay in the drawer. Fetching `/api/cves/{id}` for every painted node is an N+1 on the request path — rejected.

### 5. Honesty is the product

Edges already carry `edge_class`, `source_key`, `confidence`, `observed_at`, `fetched_at`. The inspector must list **incident** edges. The canvas already has an EDGE CLASS legend; make those classes **filters** as well (client-side on the merged graph).

`edge_class` vocabulary: `direct_fact` \| `reported` \| `derived` \| `analyst_assertion` \| `semantic`. Projection today emits the first three plus `semantic` when opted in. `analyst_assertion` stays in the legend (roadmap table); do not invent assertion writes.

Related CVEs (`source_key=related_cve_heuristic`, `edge_class=derived`) stay **visible by default**. Toggle to hide. Hiding them by default would lie about what the API returned.

### 6. Expand only valid roots

`GRAPH_ENTITY_TYPES` = `cve` \| `ioc` \| `technique` \| `campaign` \| `publication`. Sigma rule nodes appear as neighbors but **422** if used as expand root. Inspector hides EXPAND for `sigma_rule`.

### 7. Semantic hops are opt-in at the API

`include_semantic` defaults false on the backend. The frontend query helper **does not send it today** (`buildInvestigationRelationshipQuery` only knows `limit` / `depth` / `cursor`). This spec adds that query flag. Checking Semantic refetches the **current root** with `include_semantic=true` and merges. Unchecking hides `edge_class=semantic` client-side (do not wipe the canvas).

Do **not** refetch with API `edge_class=` to thin the map — that would drop other classes from the merge. Edge-class chips are **client filters** on already-fetched edges.

## Problem (production canvas)

| Symptom | RCA |
|---------|-----|
| Tiny star in empty canvas | No camera; 1:1 paint |
| Wheel does nothing useful | No non-passive wheel handler |
| No zoom buttons | Never built |
| Labels unreadable | Always-on 28-char labels |
| Click feels violent | `onClick` → `expandNode` (merge GraphPage) |
| Truncated with no next step | `next_cursor` dropped in `mergeGraphPage` |
| Related-CVE hairball | `related_cve_heuristic` up to `limit` (50) as equal-weight nodes |
| Physics clumps | Viewport pad clamp + `SPRING_LENGTH=140` + **repulsion off if n>80** |
| Inspector is thin | Type/id/knowledge only — ignores GraphEdge provenance |
| LOOKUP LIVE would mis-type hashes | `pivotToIoc` hardcodes `indicators: [{ type: 'ip' }]` |
| Semantic checkbox would no-op | Query builder omits `include_semantic` |
| No find / type / class filter | Architecture already has cluster tabs + node search |

## Goals

1. **Readable map** — Fit after layout; neighborhood uses the canvas.
2. **Map navigation** — wheel zoom at cursor, drag pan, `+`/`−`/FIT/RESET, keyboard.
3. **Inspect ≠ expand** — click select; double-click / EXPAND / Shift+Enter stored hops.
4. **LOD labels** + inverse-scaled hit targets + type glyphs.
5. **Evidence in the inspector** — incident edges with class, source, timestamps; copy markdown.
6. **Density honesty** — related-CVE toggle; type chips; edge-class chips; isolate; find-in-graph highlight.
7. **Pivot into existing BRIEFR** — drawer, live IOC (correct kind), Forge, campaigns, advisories, watchlist, thread PDF.
8. **Session marks** — watchlist + thread glyphs without changing GraphNode.
9. **Reuse architecture camera** — no second math library, no graph npm package.

## Non-goals (this spec)

- Graph database; Cytoscape / d3 / sigma / vis-network.
- Live enrichment on expand or hover.
- Saved cases / sharing (thread PDF already exists).
- Changing hop SQL / `IocKind` / email-mutex nodes / GraphNode fields.
- Minimap; PNG export; persisted camera; node drag; undo-expand stack.
- Painting KEV/EPSS/CVSS/stack on nodes.
- Sigma as an expand root.
- Replacing `InvestigationPanel` or FORGE.
- Hiding related CVEs by default.
- Architecture’s hide-all-edges-until-focus behavior.

## Approaches

**A — Camera only.** Reject as sole fix (clump + violent click + empty inspector remain).  
**B — Reuse architecture view + layout + inspect + density + inspector evidence + pivots + session marks.** Chosen.  
**C — New graph library + GraphNode decorations.** Rejected (YAGNI, frozen contract, extra package).

## Design

### 1. Camera (reuse)

View state: `{ x, y, scale }` from `architectureGraphView.js` (`DEFAULT_VIEW`, `MIN_SCALE=0.15`, `MAX_SCALE=4`, `FIT_MIN_SCALE=0.08`).

- Wheel: copy architecture handler (`preventDefault`, cursor in **canvas CSS pixels**, `zoomAtCursor`).
- Drag empty canvas: copy architecture pointer pan (`origin.x + dx`). Ignore `[data-node-id]`.
- FIT: `computeFitView(computePointCloudBounds(positions), width, height)`.
- After force **settles**, auto-Fit unless the user has already pan/zoomed.
- Filter / isolate / type-chip change: Fit (architecture refits on cluster change).
- RESET: Fit again.
- Overlay bottom-left: `+` `−` FIT GRAPH RESET VIEW. Hit target ≥ `--hit-target-min` (24px).
- Keyboard when canvas focused (`tabIndex=0`): `+`/`=` zoom in, `-` zoom out, `0` Fit, arrows pan 40px. Do not bind globally (FEED owns `/` and `f`).

### 2. Force layout (world, unbounded)

Keep `investigateForceLayout.js`. Remove viewport pad clamp. Grid repulsion always. Spring length scales with `sqrt(n)`. Center force on **root only**. Type-ring seed (root at center; techniques inner; IOC/campaign/publication mid; other CVEs outer). `stepForce(..., rootId)`.

`prefers-reduced-motion`: force ≤ 12 ticks; camera jumps (no animated Fit).

### 3. Gestures

| Input | Action |
|-------|--------|
| Wheel / pinch-as-wheel | Zoom at cursor |
| Drag empty canvas | Pan |
| Click node | Select (inspector) |
| Click selected node | Deselect (architecture pattern) |
| Double-click / inspector EXPAND / Shift+Enter | Stored expand if `canExpandEntityType` |
| Click background | Clear selection |
| `+` `-` `0` arrows | Zoom / Fit / pan |

### 4. Labels (LOD) + glyphs + session marks

Always label: root, selected, hovered, find-match. `scale >= 1.25`: non-CVE types. `scale >= 2`: all. Use existing `truncateNodeLabel`. Hit radius `clamp(8, 12/scale, 24)` in **world** space.

Shapes: CVE circle, IOC diamond, technique/sigma/publication rounded square, campaign hex; root larger; heuristic-only CVEs r=6.

Marks (client overlay): watchlist pin tick; thread ring. Semantic tokens only.

### 5. Inspector (analyst evidence)

Show selected node + **incident edges** (`source_node_id` or `target_node_id` === selected):

- `edge_class`, `source_key`, `confidence`, `observed_at`, `fetched_at`
- Neighbor id (click selects neighbor)

Actions (only those that apply): EXPAND (if expandable), OPEN CVE / LOOKUP LIVE / OPEN IN FORGE / OPEN CAMPAIGNS / OPEN ADVISORIES, PIN THREAD / PIN WATCHLIST / PIN VISIBLE CVEs, COPY ID, COPY NEIGHBORHOOD.

Keep the EDGE CLASS legend under the incident list.

### 6. Density filters (client-first)

- **Related CVEs** Radix `Checkbox`, default on — hide nodes **only** reached via `related_cve_heuristic`.
- **Type chips** (architecture `sa-type-tabs`): ALL / CVE / IOC / TECHNIQUE / CAMPAIGN / PUB — hide others; **never hide root**; Fit on change.
- **Edge-class chips**: FACT / REPORTED / DERIVED / ASSERTION / SEMANTIC — client filter; default all **except** SEMANTIC until the Semantic checkbox is on.
- **Isolate** checkbox: visible = selected (or root) + 1-hop neighbors.
- **Find** input: highlight matches (`sa-graph-node-match` analogue); **do not hide** topology. Enter pans camera to first match.
- **Semantic** checkbox: refetch root with `include_semantic=1`; uncheck hides semantic edges client-side.
- Hover/select: dim non-neighbors; emphasize incident edges.

### 7. Load more

`mergeGraphPage` keeps `cursorsByNodeId`. Honesty **LOAD MORE** when selected/root has a cursor and canvas not capped.

### 8. Deep link

`?tab=investigate&q=CVE-2026-68820` hydrates the search box and runs resolve. Leaving the tab drops `q` in `buildAppTabSearchParams` when `nextTab !== 'investigate'`. Analyst-shell `q` is unused today (admin `q` is a different route).

### 9. Chrome

Canvas `flex: 1`, `overflow: hidden`, `touch-action: none`. Overlay tools bottom-left. Inspector 260px. Shrink hero to one title line. Hint: `Scroll to zoom · drag to pan · click to inspect · double-click to expand`.

## What an analyst would want that we are **not** building here

Grounded rejection — not “later maybe” filler.

| Want | Why not this spec |
|------|-------------------|
| KEV / EPSS / CVSS on every CVE node | GraphNode `extra=forbid`; related hop already drops scores; N+1 `GET /cves` is a danger zone. OPEN CVE. |
| “Affects my stack” on the map | Stack match is a dedicated POST + feed sort, not a graph field. |
| Live VT on hover | That **is** IOC LOOKUP. LOOKUP LIVE pivots. |
| Sigma expand | API 422; not in `GRAPH_ENTITY_TYPES`. |
| Email / mutex nodes | Skipped since #859; needs a new entity type. |
| Time slider on `observed_at` | Often null; thin signal. |
| STIX / PNG / minimap | Thread PDF is the IR artifact; camera Fit replaces minimap. |
| Undo last expand | Inspect≠expand removes the violent click; snapshots are extra state. |
| Saved investigations | Roadmap; overlay PDF already exists. |
| Graph DB / elkjs | Frozen GraphPage; client layout. |
| Hide edges until focus | Architecture pattern; wrong for an evidence map. |
| Node drag | Fights inspect vs expand. |

P2 (after this ships, still reuse-only): source_key chips if edge-class is not enough; optional KEV tick **only** when the CVE is already in the feed cache (no fetch); persisted camera per root id in `sessionStorage`.

## Success criteria

1. Wheel over canvas zooms at cursor; **page does not scroll** (non-passive listener).
2. `+`/`−`/FIT GRAPH/RESET VIEW work without a wheel.
3. After resolve of a 50-neighbor CVE, auto-Fit fills the canvas.
4. Click inspects; node count unchanged; double-click expands; Sigma has no EXPAND.
5. Inspector lists incident `source_key` / `edge_class`; COPY NEIGHBORHOOD uses `copyToClipboard`.
6. LOOKUP LIVE on `hash:` / `domain:` / `url:` prefills IOC LOOKUP with that **kind**, not `ip`.
7. OPEN CVE / OPEN IN FORGE / OPEN CAMPAIGNS / PIN WATCHLIST call existing hooks (no new HTTP APIs except sending already-documented `include_semantic` / `cursor`).
8. Related-CVE toggle, type chips, edge-class chips, Isolate, and Find change what is visible; Find does not hide topology.
9. Truncated + cursor → LOAD MORE.
10. Watchlist/thread marks appear without GraphNode schema changes.
11. Unit tests: `zoomAtCursor` (existing) + point-cloud Fit; force n>80; merge cursors + `include_semantic` query; related-CVE / isolate / parseIocEntityId filters.
12. No new graph npm package; GraphPage JSON unchanged.

## Explicitly deferred

Server-side related-CVE cap; minimap; email/mutex entity types; persisted camera; PNG export; GraphNode decorations; sigma expand roots; node drag; live enrichment on the canvas.
