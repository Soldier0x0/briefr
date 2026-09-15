# INVESTIGATE Smoothness Program — design spec

**Date:** 2026-09-15  
**Status:** Draft — approved for planning  
**Supersedes / extends:**  
- `docs/superpowers/specs/2026-08-20-investigate-obsidian-plus-design.md` (P1.5 + Obsidian+ engine — **mostly shipped**)  
- `docs/superpowers/specs/2026-08-20-investigate-canvas-ux-design.md` (camera/inspect mechanics — **shipped**)  
- `docs/plans/2026-08-13-investigation-platform-roadmap.md` (graph API contract — **frozen**)

**Goal:** Make INVESTIGATE feel Obsidian-smooth and Flowsint-resumable without graph databases, outbound enrich-on-expand, or breaking the frozen `GraphPage` contract.

---

## Executive summary

BRIEFR already shipped the Obsidian+ foundation: local-first layers, RAF force engine, camera controller, node drag, fly-to, related-CVE opt-in, and inspector pivots. Remaining roughness clusters in three areas:

| Wave | Theme | Primary pain | Outcome |
|------|-------|--------------|---------|
| **1** | Feel-first polish | Layout jump on expand; no session restore; truncation friction | Stable expand, local draft, canvas truncation hints |
| **2** | Render performance | SVG DOM churn at ~150+ nodes | Canvas edge layer + culling; optional cap raise |
| **3** | Investigation workspaces | Cannot resume a case | Postgres-backed saved cases |

**Explicit non-goals (all waves):** Neo4j / Apache AGE / Kùzu; live enrichment on graph click; KEV/EPSS on nodes; multi-user ACL / share links.

---

## What is already shipped (do not rebuild)

From `docs/PRODUCT_STATUS.md` and current `frontend/src/components/investigate/`:

- Frozen `GraphPage` APIs (`backend/investigations/`)
- `investigateGraphEngine.js` — alpha-decay force sim, ref-based frames
- `investigateCameraController.js` — fly-to, inertia, smoothed zoom
- `investigateGraphProjection.js` / `splitGraphLayers` — Core vs Related CVE vs Semantic
- Related CVEs **default OFF** + counted banner
- Client caps: **200 nodes / 300 edges**
- Inspector pivots (OPEN CVE, LOOKUP LIVE with IocKind, FORGE, advisories, pin thread)
- `aria-live` status region, mobile Graph | Inspector tabs

This program **extends** that stack; it does not replace it.

---

## Wave 1 — Feel-first polish

### 1.1 Incremental expand layout

**Problem:** `createGraphEngine().setTopology()` calls `seedPositions()` then `reheat(1)`, which re-integrates the whole graph. New neighbors can fling existing nodes.

**Design:**

- Add `seedExpandPositions(parentNode, newNodes, priorPositions, viewport)` in `investigateForceLayout.js`:
  - New nodes spawn on a small ring around the parent (radius ~80–120px world units, jitter ±20px).
  - Existing nodes keep prior `(x, y)` from `positionsRef`.
  - Root position never changes on expand.
- `investigateGraphEngine.js` gains `mergeTopology(existingNodes, addedNodes, edges, rootId, expandParentId)`:
  - Only reheat to `0.4` (not `1.0`) when `expandParentId` is set.
  - Full reheat remains for **resolve** (new root) and **filter/layer** changes.
- On expand merge, pass `expandParentId` from `InvestigateGraph.jsx` `expandNode()`.

**Success:** Double-click expand adds nodes locally without unrelated nodes crossing the canvas.

### 1.2 Expand camera policy

**Problem:** `onSettled` + `shouldRefitAfterStructuralChange` can auto-fit the **entire** visible graph after expand, disorienting the analyst.

**Design:**

- Split structural reasons: `resolve` | `expand` | `filter` | `load_more`.
- **Resolve:** auto-fit Core layer (existing behavior).
- **Expand:** `flyToNeighborhood(parentId, 1-hop bbox, padding 80px)` — do **not** full-graph fit.
- **Filter / layer toggle:** `flyToVisible(visibleNodes)` (existing spec).
- **Manual FIT GRAPH:** unchanged; always available.
- Update `investigateCameraPolicy.js` with `cameraActionForStructuralChange(reason)`.

### 1.3 Optimistic expand feedback

**Design:**

- On double-click / EXPAND: set `expandingId` immediately (already exists); add **pulsing ring** CSS class on node within 1 frame.
- If API fails: clear `expandingId`, toast via `notifyApiError`, no graph mutation.
- If API returns empty page: `aria-live` — "No further stored hops for this node."

### 1.4 Local draft restore (session continuity)

**Problem:** Tab switch or refresh loses graph state. Obsidian-plus deferred `sessionStorage` camera-only; analysts need full working state.

**Design:**

- New `frontend/src/utils/investigateDraftStorage.js`:
  - Key: `briefr:investigate:draft:v1`
  - Payload (JSON, max ~500KB): `{ savedAt, query, graph, positions, view, filters: { showRelatedCves, entityType, edgeClasses, isolate, includeSemantic } }`
  - Debounced write (500ms) on graph/positions/view/filter change.
  - On mount: if `initialQuery` empty and draft age < 24h, offer **Restore draft** banner (not auto-restore — avoids fighting `?tab=investigate&q=` deep links).
  - Clear draft on explicit new RESOLVE.
- Positions stored as `{ node_id, x, y }[]` only (not velocities).
- `prefers-reduced-motion`: skip restore animation; apply view immediately.

**Non-goal:** Cross-browser sync or multi-device — Wave 3 handles durable cases.

### 1.5 Truncation hints on canvas

**Problem:** `truncated` / `LOAD MORE` only obvious in inspector.

**Design:**

- When `graph.cursorsByNodeId[nodeId]` is set, render a small `+N` badge on that node (count from `truncated_count` if API adds it; else generic `+`).
- Badge click = same as inspector LOAD MORE (no new API in Wave 1).
- If backend does not return per-node counts, badge text is `+` with tooltip "More hops available — click to load".

**API note:** Wave 1 uses generic badge; optional `truncated_remaining` on `GraphPage` is Wave 1.5 if needed.

### 1.6 Wave 1 success criteria

1. Expand does not fling unrelated nodes (manual + unit test on `seedExpandPositions`).
2. Expand camera flies to parent neighborhood, not full-graph fit.
3. Draft restore banner appears after refresh when draft exists.
4. Expanding node shows feedback within 100ms.
5. Truncated nodes show on-canvas affordance.
6. No change to `GraphPage` contract required for Wave 1.
7. `prefers-reduced-motion` honored.

---

## Wave 2 — Render performance

### 2.1 Frame budget gate (prerequisite)

Before Canvas work, profile on a **200-node / 300-edge** synthetic graph (existing unit test fixtures + perf harness):

- Target: **≤12ms p95** per frame (sim + draw) on 4× CPU throttle.
- If SVG path meets budget: ship culling only; defer Canvas layer.

### 2.2 Hybrid Canvas edge layer

**Design (contingency from Obsidian+ spec):**

- New `investigateGraphCanvas.js`:
  - `<canvas>` under SVG node layer inside `#investigate-world`.
  - Draw edges each frame from `positionsRef` (lines, dashed for heuristic when layer on).
  - SVG retains nodes (a11y, focus rings, labels).
- `applyGraphDom` stops updating `<line>` elements when canvas mode on.
- Feature flag: `INVESTIGATE_CANVAS_EDGES=1` in `frontend/src/utils/investigateGraphGate.js` (default off until profile proves need).

### 2.3 Viewport culling

- `visibleInViewport(node, view, viewportRect)` — skip draw/sim forces for nodes outside viewport + 100px margin (sim still runs on visible + 1-hop neighbors only).
- Reduces work when graph is spread out.

### 2.4 Cap raise (conditional)

- Only after 2.2 shipped and profile green: raise `INVESTIGATE_GRAPH_MAX_NODES` to **400**, `INVESTIGATE_GRAPH_MAX_EDGES` to **500**.
- Update honesty copy in `InvestigateGraph.jsx`.
- Backend `limit` max stays 100 per page (unchanged); client accumulation cap rises.

### 2.5 Wave 2 success criteria

1. p95 frame time ≤12ms on 200-node stress graph OR documented Canvas path enabled.
2. No regression to keyboard focus / `aria-live`.
3. Caps raised only with culling + canvas path green in CI perf smoke (optional `npm run test:perf` script).

---

## Wave 3 — Investigation workspaces

### 3.1 Data model

New Postgres table `investigation_cases` (Alembic migration):

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `title` | TEXT NOT NULL | Default: root label + date |
| `owner_user_id` | INTEGER FK | Session user; single-operator |
| `root_node_id` | TEXT | `cve:CVE-…` etc. |
| `snapshot` | JSONB NOT NULL | Frozen `{ nodes, edges, positions, view, filters }` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

- `snapshot` is a **client workspace** — not a second intel SSOT. Intel truth remains mirrors + projection APIs.
- SQLite test path: same table via Alembic (JSON column as TEXT).

**Non-goals Wave 3:** share links, org ACL, collaborative editing, export format change.

### 3.2 API

Session-gated routes in `backend/routers/investigations.py` (or `investigation_cases.py`):

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/investigations/cases` | List cases for user (max 50, updated_at desc) |
| POST | `/api/investigations/cases` | Create from body `{ title?, snapshot }` |
| GET | `/api/investigations/cases/{id}` | Load one |
| PUT | `/api/investigations/cases/{id}` | Replace snapshot (save) |
| DELETE | `/api/investigations/cases/{id}` | Delete |

- Validate `snapshot.nodes[].node_id` shape; reject > 500 nodes / 600 edges server-side.
- No server-side expand merge in Wave 3 — client loads case, continues expand via existing relationship APIs, then PUT save.

### 3.3 UI

- INVESTIGATE toolbar: **SAVE CASE** (dialog title), **OPEN** (recent list dropdown).
- Deep link: `?tab=investigate&case={uuid}`.
- Opening a case hydrates graph state from snapshot; **Refresh from source** action re-fetches root relationships (optional, compares `knowledge_state`).
- Autosave: debounced PUT every 30s when case is open and dirty (banner "Saved" / "Unsaved changes").

### 3.4 Wave 3 success criteria

1. Analyst can save, close browser, reopen case from list.
2. Case survives backend restart (Postgres).
3. Expand after open still uses projection APIs (no stale-only trap).
4. `docs/PRODUCT_STATUS.md` updated: saved cases shipped; still no share links.

---

## Cross-wave constraints

1. **GraphPage contract frozen** — no new node fields without ADR.
2. **No outbound HTTP on expand** — enrichers stay on IOC LOOKUP / scheduler.
3. **Evidence honesty** — caps and truncation remain visible; raising caps does not hide truncation.
4. **Design system** — tokens only; `prefers-reduced-motion` + global motion toggle respected.
5. **Danger zone 1** — SQLite + Postgres both ways for Wave 3 migration and case APIs.

---

## Testing strategy

| Wave | Tests |
|------|-------|
| 1 | Unit: `seedExpandPositions`, `cameraActionForStructuralChange`, `investigateDraftStorage`; extend `investigateGraphEngine.test.js` |
| 2 | Perf smoke script; visual regression optional |
| 3 | `test_investigation_cases.py` — CRUD, auth, size limits, SQLite + Postgres |

Merge gate: `./scripts/verify-local.sh` green after each wave.

---

## Rollout order

1. **Wave 1** — ship alone (highest ROI, frontend-heavy).  
2. **Wave 2** — profile first; ship only if needed or cap raise blocked.  
3. **Wave 3** — after Wave 1 stable; backend migration required.

Waves are independently valuable; each wave merges as working software.

---

## Open decisions (locked in this spec)

| Decision | Choice |
|----------|--------|
| Related CVE default | OFF (unchanged) |
| Draft restore | Banner opt-in, not silent auto-restore |
| Expand camera | Neighborhood fly-to, not full fit |
| Graph DB | Rejected |
| Case sharing | Deferred past Wave 3 |

---

## References

- Flowsint comparison session (2026-09-15) — inspiration for workspace persistence, not architecture copy.
- `frontend/src/components/investigate/InvestigateGraph.jsx` — integration point all waves.
- `backend/investigations/projection.py` — read-only expand source of truth.
