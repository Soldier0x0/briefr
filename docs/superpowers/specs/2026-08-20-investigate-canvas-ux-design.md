# INVESTIGATE canvas UX — design spec

**Date:** 2026-08-20  
**Status:** Ready for implementation (P1.5 — canvas UX, not a new data plane)  
**Related:** `docs/plans/2026-08-13-investigation-platform-roadmap.md` (P0 APIs, P1 browser), `docs/PRODUCT_STATUS.md` Investigation graph

## Why this tab exists

INVESTIGATE is the analyst’s **spatial working memory** over intel BRIEFR already stores.

FEED is a ranked list. IOC LOOKUP is a live single-indicator check. The CVE drawer is a deep vertical on **one** CVE. FORGE is detection engineering. None of those answer: *“from this CVE, what else do I already know, and how is it connected?”*

The intended loop (roadmap P1, copy on the page today):

1. Search a CVE / hash / IP / domain / technique **once**.
2. See a graph of **stored** hops (technique, IOC, campaign, publication, Sigma, related CVE).
3. Click to **inspect**, then expand a chosen node to pivot — Obsidian-style, not a live enrichment spider.
4. Trust the picture: edges encode **evidence class**, not certainty; truncation is visible; no outbound fetch on each click.

If the canvas is an illegible clump, the tab fails its reason for existing. A list of neighbors would be more honest.

## Problem (production, 2026-08-20)

On `CVE-2026-68820` the API works (resolve + relationships 200, truncation honesty fires). The **browser** does not:

| Symptom | Why |
|---------|-----|
| Tiny star in a huge empty canvas | World coordinates are painted 1:1 on the SVG. There is **no camera** (no pan, no zoom, no fit). |
| Labels stacked and unreadable | Every node always draws a 28-char label at `--font-size-micro`. |
| No smooth zoom / pan | Wheel, pinch, drag-canvas, `+`/`−`, Fit are all absent. |
| Clicking a spoke “does something violent” | Node `onClick` calls `expandNode` (merge another GraphPage) **and** selects. Inspect vs expand are the same gesture. |
| “Truncated — more hops…” with no next action | `next_cursor` is returned by the API and **dropped** in `mergeGraphPage`. |
| Related-CVE flood | Default one-hop includes `related_cve_heuristic` (up to `limit`, default 50). Those CVEs are equal-weight orange/red dots around the root — the screenshot star. |
| Layout physics fights density | `CENTER` gravity + clamp to a 36px pad + `SPRING_LENGTH = 140`. If `nodes.length > 80`, **all pairwise repulsion is skipped** (`REPULSE_PAIR_CAP`). |

P0/P1 data-plane constraints still hold and are **not** the bug: no graph DB, no x/y from API, no live enrichment on expand, session-gated GETs.

## Goals

1. **Read the graph.** After resolve, the neighborhood is legible without fighting the canvas.
2. **Navigate like a map.** Pan, zoom around cursor, Fit, Reset; keyboard `+`/`−`/`0`; reduced-motion still works (instant camera, short layout).
3. **Inspect without widening.** Primary click selects; expand is explicit (inspector, double-click, or keyboard).
4. **LOD labels.** Root + selected + hovered always labeled; others appear above a zoom threshold.
5. **Honest density.** Related-CVE heuristic is visible but not allowed to drown intel hops; truncation has **Load more**.
6. **Stay BRIEFR.** Tokens only, no new graph library, no GraphPage schema change, no outbound APIs.

## Non-goals (this spec)

- Graph database, Cytoscape, d3-force, sigma.js, vis-network.
- Saved cases, shareable graph URLs, multi-user presence.
- Changing hop SQL / `IocKind` / email-mutex modeling (separate RCA, already on `main`).
- LLM-generated edges, semantic hops on by default.
- Minimap (defer unless Fit + pan still fail on 200-node caps).
- Replacing FORGE or the pin overlay (`InvestigationPanel`).

## Approaches considered

### A — Camera only

Add pan/zoom/Fit on the current force layout. Fastest. **Reject as sole fix:** physics still clumps; click still expands; related CVEs still dominate; cursor still unused.

### B — Camera + layout + interaction + density honesty (chosen)

Keep custom SVG. Separate **world layout** from **view camera**. Fix force (repulsion always, type-ring seed, no viewport clamp). Change gestures. Filter/weight related CVEs. Wire `next_cursor`.

**Pros:** Matches product intent; no new deps; unit-testable math; stays inside frozen GraphPage.  
**Cons:** More frontend work than A; force layout will still be “good enough,” not Gephi.

### C — Replace renderer with a graph library

**Reject:** new dependency, fights tokens/a11y/`prefers-reduced-motion`, harder to keep visual honesty (edge_class strokes, degraded copy). P1 already chose client-only force for that reason.

## Design

### 1. Camera (view) vs layout (world)

Layout writes unbounded world `x,y` on nodes. The SVG wraps nodes/edges in a `<g transform="translate(tx,ty) scale(k)">`.

- **Wheel** over canvas: zoom around cursor (`k' = clamp(k * 1.15^delta, 0.25, 4)`), keeping the world point under the cursor fixed.
- **Drag empty canvas:** pan (`tx, ty`).
- **Drag a node:** move that node in world space; pin `vx,vy = 0` while dragging (Obsidian-like).
- **Buttons** (canvas overlay, bottom-left): `−` `+` `FIT` `RESET`.
- **Keyboard** when canvas focused: `+`/`=` zoom in, `-` zoom out, `0` fit, arrows pan.
- **Fit:** bounding box of current positions → `k, tx, ty` with 48px padding. Run once after the force loop **settles** (or after 12 ticks when reduced-motion).
- **Reset:** camera identity + re-seed layout from current graph (does not clear the graph).
- **Reduced motion:** no RAF force loop beyond 12 ticks; camera jumps (no CSS transition on `transform`).

Do **not** clamp nodes to the SVG client box. Clamping is why the star sits in the middle of empty chrome.

### 2. Force layout

Keep `seedPositions` / `stepForce` in `investigateForceLayout.js` (API still has no x/y).

Changes:

- **Type-ring seed** around the root: techniques / Sigma inner ring; IOC / campaign / publication middle; `related_cve_heuristic` targets outer ring. Preserve prior positions on expand.
- **Spring rest length** scales with `sqrt(n)` (floor 160, ceiling 420) so 50-node stars are not 140px hairballs.
- **Repulsion always on.** If `n > 80`, use a grid neighborhood (cells ~ rest length) instead of skipping all pairs.
- **Center force** applies to the **root only** (weak), not every node.
- **No pad clamp** to `width/height`. Optional soft world bounds only to keep numerics finite (e.g. ±8000).

Root node is visually larger (`r` 12 vs 8) and uses `--accent-selected` fill while it is the resolve root, even if another node is selected (selected gets a second ring / thicker stroke).

### 3. Gestures and inspector

| Input | Action |
|-------|--------|
| Click node | Select only. Inspector shows type / id / knowledge / incident edges to neighbors. |
| Double-click node | Expand (existing GET + merge). |
| Inspector **EXPAND** | Expand selected. |
| Enter / Space on focused node | Select; **Shift+Enter** expands (avoid accidental widen). |
| Click canvas background | Clear selection (keep graph). |
| **PIN THREAD** / **OPEN CVE** | Unchanged. |

Click-to-expand is the P1 shortcut that made the canvas feel “broken” on a 50-CVE star. Explicit expand is the Obsidian analogue (open note vs follow link).

### 4. Labels (LOD)

- Always: root label; selected label; hovered label.
- If `k >= 1.25`: labels for nodes with degree ≥ 2 or non-`cve` types.
- If `k >= 2`: all labels, still truncated to 28 chars.
- Labels are `pointer-events: none`. Hover uses the hit circle only (`HIT_R` ≥ 12, scale **inversely** so hit targets stay ~24px on screen: `hitR = 12 / k` clamped).

Color/shape still encode type (below); labels are not the only signal (design-system §4).

### 5. Node glyphs by `entity_type`

Shape + stroke, not color alone:

| Type | Shape | Default fill |
|------|--------|----------------|
| `cve` (root) | Circle, larger | `--accent-selected` |
| `cve` (other) | Circle | `--surface-raised` |
| `ioc` | Diamond (rotated rect) | `--surface-raised` |
| `technique` | Square | `--surface-raised` |
| `campaign` | Hexagon (or square+dot) | `--surface-raised` |
| `publication` / `sigma_rule` | Small square | `--surface-raised` |

Edge strokes stay the existing `edge_class` map (direct_fact solid strong, reported accent, derived muted, assertion warning, semantic dashed).

### 6. Related-CVE density (honesty, not hiding)

`related_cve_heuristic` is **derived**, not a stored fact. It is allowed on the graph but must not be the default visual majority.

- Inspector: checkbox **Related CVEs** (default **on** so we do not hide data). Unchecked: hide nodes that are *only* reached via `related_cve_heuristic` (keep if also linked by OTX/technique/campaign/publication).
- Outer-ring seed + smaller radius (6) for those nodes when shown.
- Honesty line can say `N related CVEs (heuristic)` when any such edge is present.

Do **not** change backend ranking in this spec. If production still floods after client layout + filter, a follow-up can cap related CVE hops server-side (separate plan).

### 7. Truncation → Load more

`mergeGraphPage` must keep:

- `next_cursor` from the latest page for the **expanded** entity
- `cursorsByNodeId: { [nodeId]: cursor | null }`

Honesty row: if `truncated` and a cursor exists for the selected (or root) node, show **LOAD MORE** which GETs `.../relationships?cursor=&limit=`. Merge as today. If the client cap hits 200/300, keep existing capped copy (no load more).

### 8. Stage chrome

- Canvas `flex: 1` and fill remaining viewport below toolbar (P1: “full canvas”). Shrink hero copy; keep one-line hint.
- Overlay controls must not steal layout width from the graph (position absolute inside `.investigate-canvas`).
- Inspector stays 260px; on ≤960px stack below canvas (existing breakpoint).
- Tokens only. Hit targets ≥ 24px for overlay buttons.

### 9. Accessibility

- Canvas `tabIndex={0}`, `aria-label` includes selected node id when set.
- Overlay buttons have `aria-label` (“Zoom in”, “Fit graph”, …).
- `prefers-reduced-motion` and `data-motion` honored (design-system §12 / §23).
- Do not rely on wheel-only zoom — buttons required.

## Success criteria

An analyst on a 50-neighbor CVE (the screenshot class):

1. After resolve, **Fit** (automatic) shows the whole neighborhood using most of the canvas, not 10% in the center.
2. Wheel zoom is smooth (60fps on 200 nodes / 300 edges cap) and keeps the cursor’s world point stable.
3. Clicking a related CVE **does not** merge a new page; inspector updates; double-click or EXPAND merges.
4. At default zoom, labels do not form an unreadable pile; zooming in reveals more labels.
5. Unchecking Related CVEs leaves technique/IOC/campaign/publication hops visible.
6. Truncated graphs offer Load more when `next_cursor` is present.
7. `npm run test:unit` covers camera math, force finite coords + repulsion-on-for-n>80, merge cursor map, related-CVE filter.
8. No new npm graph library; GraphPage JSON unchanged.

## Risks

| Risk | Mitigation |
|------|------------|
| Force still ugly at 200 nodes | Camera + Fit + related-CVE filter; grid repulsion; accept “good enough” |
| Analysts liked click-to-expand | Keep EXPAND + double-click; hint copy updates once |
| Fit fights a still-running force loop | Fit after settle / after last tick; optional “layout lock” when user pans |
| Hit targets shrink when zoomed out | Inverse-scale hit radius in world space |
