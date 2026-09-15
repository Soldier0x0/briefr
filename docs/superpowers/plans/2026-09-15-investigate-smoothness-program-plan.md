# INVESTIGATE Smoothness Program — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three waves of INVESTIGATE graph smoothness — stable expand feel, optional canvas perf path, and saved investigation cases — without graph databases or enrich-on-expand.

**Architecture:** Extend the shipped Obsidian+ stack (`investigateGraphEngine`, `investigateCameraController`, `InvestigateGraph.jsx`). Wave 1 is frontend-only polish. Wave 2 adds optional Canvas edge rendering after profiling. Wave 3 adds `investigation_cases` Postgres table + CRUD APIs.

**Tech Stack:** React 19, vanilla JS utils, FastAPI, Alembic, pytest, `node:test` frontend unit tests.

**Design spec:** `docs/superpowers/specs/2026-09-15-investigate-smoothness-program-design.md`

## Global Constraints

- Frozen `GraphPage` contract — no new `GraphNode` fields without ADR.
- No outbound HTTP on graph expand; IOC live lookup stays explicit pivot.
- No Neo4j / Apache AGE / Kùzu / Redis.
- Semantic tokens only in UI (`frontend/src/styles/tokens.css`); respect `prefers-reduced-motion` and `data-motion` on `<html>`.
- Postgres production; SQLite test fallback for backend (danger zone 1 — test both ways for Wave 3).
- Merge gate: `./scripts/verify-local.sh` green after each wave.
- Update `docs/PRODUCT_STATUS.md` when operator-visible behavior changes (Wave 1: camera on expand, layout stability, expand feedback, truncation badges, draft restore; Wave 3: saved cases).

---

## File map

| File | Wave | Responsibility |
|------|------|----------------|
| `frontend/src/utils/investigateForceLayout.js` | 1 | `seedExpandPositions` for parent-ring spawn |
| `frontend/src/utils/investigateGraphEngine.js` | 1 | `mergeTopology` partial reheat |
| `frontend/src/utils/investigateCameraPolicy.js` | 1 | Structural change → camera action |
| `frontend/src/utils/investigateDraftStorage.js` | 1 | localStorage draft read/write |
| `frontend/src/components/investigate/InvestigateGraph.jsx` | 1–3 | Wire expand camera, draft, badges, case UI |
| `frontend/src/components/investigate/InvestigateGraph.css` | 1 | Expanding pulse, truncation badge |
| `frontend/src/utils/investigateGraphCanvas.js` | 2 | Canvas edge layer |
| `frontend/src/utils/investigateGraphGate.js` | 2 | `canvasEdgesEnabled()` flag |
| `frontend/src/utils/investigateGraphMerge.js` | 2 | Raised caps constants |
| `backend/alembic/versions/045_investigation_cases.py` | 3 | Migration |
| `backend/investigations/cases.py` | 3 | CRUD repo |
| `backend/routers/investigation_cases.py` | 3 | API routes |
| `backend/tests/test_investigation_cases.py` | 3 | Auth + limits |
| `frontend/src/api.js` | 3 | Case fetch helpers |

---

# Wave 1 — Feel-first polish

### Task 1: `seedExpandPositions` layout helper

**Files:**
- Modify: `frontend/src/utils/investigateForceLayout.js`
- Create: `frontend/src/utils/investigateForceLayout.test.js`

**Interfaces:**
- Produces: `export function seedExpandPositions(parent, newNodes, priorMap, { width, height })` → `Array<{ node_id, x, y, vx, vy, ...node }>`

- [ ] **Step 1: Write the failing test**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { seedExpandPositions } from './investigateForceLayout.js'

describe('seedExpandPositions', () => {
  it('places new nodes near parent and preserves existing positions', () => {
    const parent = { node_id: 'cve:CVE-2024-1', entity_type: 'cve', x: 400, y: 300 }
    const newNodes = [
      { node_id: 'ioc:ip:1.1.1.1', entity_type: 'ioc' },
      { node_id: 'ioc:ip:2.2.2.2', entity_type: 'ioc' },
    ]
    const prior = new Map([
      ['cve:CVE-2024-1', { x: 400, y: 300, vx: 0, vy: 0 }],
      ['technique:T1059', { x: 100, y: 200, vx: 0, vy: 0 }],
    ])
    const out = seedExpandPositions(parent, newNodes, prior, { width: 800, height: 600 })
    const kept = out.find((n) => n.node_id === 'technique:T1059')
    const spawned = out.find((n) => n.node_id === 'ioc:ip:1.1.1.1')
    assert.equal(kept.x, 100)
    assert.equal(kept.y, 200)
    const dx = spawned.x - parent.x
    const dy = spawned.y - parent.y
    const dist = Math.hypot(dx, dy)
    assert.ok(dist >= 60 && dist <= 160)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- investigateForceLayout.test.js`  
Expected: FAIL — `seedExpandPositions` not exported

- [ ] **Step 3: Implement `seedExpandPositions`**

Add to `investigateForceLayout.js`:

```javascript
const EXPAND_RING_MIN = 80
const EXPAND_RING_MAX = 140

export function seedExpandPositions(parent, newNodes, priorMap, { width, height }) {
  const px = parent?.x ?? width / 2
  const py = parent?.y ?? height / 2
  const existingIds = new Set()
  const result = []
  for (const [nodeId, pos] of priorMap.entries()) {
    existingIds.add(nodeId)
    result.push({ node_id: nodeId, x: pos.x, y: pos.y, vx: pos.vx || 0, vy: pos.vy || 0 })
  }
  const count = Math.max(newNodes.length, 1)
  newNodes.forEach((node, index) => {
    if (existingIds.has(node.node_id)) return
    const angle = (index / count) * Math.PI * 2
    const radius = EXPAND_RING_MIN + (index % 3) * 20
    const jitter = (index % 2 === 0 ? 1 : -1) * 12
    result.push({
      ...node,
      x: px + Math.cos(angle) * radius + jitter,
      y: py + Math.sin(angle) * radius - jitter,
      vx: 0,
      vy: 0,
    })
  })
  return result
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- investigateForceLayout.test.js`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateForceLayout.js frontend/src/utils/investigateForceLayout.test.js
git commit -m "feat(investigate): add seedExpandPositions for stable expand layout"
```

---

### Task 2: `mergeTopology` on graph engine

**Files:**
- Modify: `frontend/src/utils/investigateGraphEngine.js`
- Modify: `frontend/src/utils/investigateGraphEngine.test.js`

**Interfaces:**
- Consumes: `seedExpandPositions` from Task 1
- Produces: `mergeTopology(allNodes, edges, rootId, { expandParentId, parentPosition })` on engine API (options object; `allNodes` is the full merged node list after expand)

- [ ] **Step 1: Write failing test**

```javascript
it('mergeTopology reheat is weaker than full setTopology', () => {
  const engine = createGraphEngine()
  engine.setSize(800, 600)
  engine.setTopology(nodes, edges, 'root')
  while (engine.tick()) { /* settle */ }
  engine.mergeTopology(
    [...nodes, { node_id: 'c', entity_type: 'ioc' }],
    [...edges, { source_node_id: 'root', target_node_id: 'c' }],
    'root',
    { expandParentId: 'root', parentPosition: { x: 400, y: 300 } },
  )
  assert.ok(engine.alpha() <= 0.5)
  assert.ok(engine.alpha() >= 0.35)
})
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm run test:unit -- investigateGraphEngine.test.js`

- [ ] **Step 3: Implement `mergeTopology`**

In `createGraphEngine` return object, add:

```javascript
mergeTopology(nodes, nextEdges, nextRootId, { expandParentId = null, parentPosition = null } = {}) {
  const prior = new Map(positions.map((n) => [n.node_id, n]))
  edges = nextEdges || []
  rootId = nextRootId
  if (expandParentId && parentPosition) {
    const parentNode = { node_id: expandParentId, x: parentPosition.x, y: parentPosition.y }
    const existing = (nodes || []).filter((n) => prior.has(n.node_id))
    const added = (nodes || []).filter((n) => !prior.has(n.node_id))
    const merged = seedExpandPositions(parentNode, added, prior, { width, height })
    positions = merged.map((n) => {
      const meta = (nodes || []).find((x) => x.node_id === n.node_id) || n
      return { ...meta, x: n.x, y: n.y, vx: n.vx || 0, vy: n.vy || 0 }
    })
    this.reheat(0.4)
  } else {
    positions = seedPositions(nodes, width, height, prior, rootId)
    this.reheat(1)
  }
  notifyFrame()
},
```

Import `seedExpandPositions` at top of file.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(investigate): add mergeTopology with partial reheat on expand"
```

---

### Task 3: Structural camera policy

**Files:**
- Modify: `frontend/src/utils/investigateCameraPolicy.js`
- Create: `frontend/src/utils/investigateCameraPolicy.test.js`

**Interfaces:**
- Produces: `export function cameraActionForStructuralChange(reason)` → `'fit_all' | 'fit_visible' | 'fly_neighborhood' | 'none'`

- [ ] **Step 1: Write failing test**

```javascript
import { cameraActionForStructuralChange } from './investigateCameraPolicy.js'
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

describe('cameraActionForStructuralChange', () => {
  it('maps expand to fly_neighborhood', () => {
    assert.equal(cameraActionForStructuralChange('expand'), 'fly_neighborhood')
  })
  it('maps resolve to fit_all', () => {
    assert.equal(cameraActionForStructuralChange('resolve'), 'fit_all')
  })
})
```

- [ ] **Step 2–4: Implement and pass**

```javascript
export function cameraActionForStructuralChange(reason) {
  switch (reason) {
    case 'resolve':
      return 'fit_all'
    case 'expand':
    case 'load_more':
      return 'fly_neighborhood'
    case 'filter':
    case 'layer':
      return 'fit_visible'
    default:
      return 'none'
  }
}
```

- [ ] **Step 5: Commit**

---

### Task 4: Wire expand + camera in `InvestigateGraph.jsx`

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

**Interfaces:**
- Consumes: `cameraActionForStructuralChange`, engine `mergeTopology`
- Track `structuralReasonRef` = `'resolve' | 'expand' | 'filter' | ...`

- [ ] **Step 1: Add `structuralReasonRef` and set on resolve/expand/filter**

In `runSearch`: set `structuralReasonRef.current = 'resolve'` before merge.  
In `expandNode`: set `'expand'` (or `'load_more'` when `params.cursor` is present).  
In filter toggles: set `'filter'`.

- [ ] **Step 1b: Integration test for load_more camera policy**

Add `frontend/src/utils/investigateCameraPolicy.test.js` case: `load_more` → `fly_neighborhood`.  
Add `investigateGraphEngine.test.js` or policy test asserting LOAD MORE path sets `structuralReasonRef` to `'load_more'` (extract helper `structuralReasonForExpand(params)` if needed).

- [ ] **Step 2: On graph merge after expand, call `engine.mergeTopology` instead of `setTopology`**

Pass `expandParentId: node.node_id` and parent position from `positionsRef`.

- [ ] **Step 3: Update `onSettled` camera branch**

```javascript
const action = cameraActionForStructuralChange(structuralReasonRef.current)
if (action === 'fit_all') fitGraphToViewRef.current?.()
else if (action === 'fit_visible') flyToVisibleRef.current?.()
else if (action === 'fly_neighborhood') flyToNeighborhoodRef.current?.(lastExpandParentRef.current)
```

Implement `flyToNeighborhood` using `computePointCloudBounds` on parent + 1-hop neighbors (reuse `investigateCameraController.flyToView`).

- [ ] **Step 4: Manual smoke**

Run: `cd frontend && npm run dev` — resolve CVE, expand IOC, confirm camera stays near parent.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(investigate): neighborhood camera on expand, partial layout merge"
```

---

### Task 5: Local draft storage

**Files:**
- Create: `frontend/src/utils/investigateDraftStorage.js`
- Create: `frontend/src/utils/investigateDraftStorage.test.js`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

**Interfaces:**
- Produces: `loadInvestigateDraft()`, `saveInvestigateDraft(payload)`, `clearInvestigateDraft()`, `hasInvestigateDraft()`

- [ ] **Step 1: Write failing tests** (round-trip, 24h expiry, clear)

- [ ] **Step 2–4: Implement with key `briefr:investigate:draft:v1`, debounce 500ms**

- [ ] **Step 5: Add restore banner in InvestigateGraph** — "Restore previous graph?" with RESTORE / DISMISS; clear on new RESOLVE

- [ ] **Step 6: Commit**

---

### Task 6: Truncation badge on canvas

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

- [ ] **Step 1: Render `+` badge when `graph.cursorsByNodeId[node.node_id]`**

Position badge at node offset; `aria-label="More hops available"`. Click triggers same handler as LOAD MORE.

- [ ] **Step 2: Add `.investigate-truncation-badge` styles** (mono, `--text-muted`, min 24px hit target)

- [ ] **Step 3: Commit**

---

### Task 7: Wave 1 verification

- [ ] Run: `cd frontend && npm run test:unit`
- [ ] Run: `cd frontend && npm run build`
- [ ] Run: `./scripts/verify-local.sh`
- [ ] Commit any fixes

**Wave 1 gate:** All Wave 1 success criteria in design spec §1.6 met.

---

# Wave 2 — Render performance

> **Start only after Wave 1 merged.** Profile first; skip Canvas if SVG meets ≤12ms p95.

### Task 8: Perf harness

**Files:**
- Create: `frontend/scripts/investigate-graph-perf.mjs`

- [ ] Generate 200-node / 300-edge fixture; run 60 frames of sim + `applyGraphDom`; print p95 ms.

Run: `node frontend/scripts/investigate-graph-perf.mjs`

---

### Task 9: Canvas edge layer (if profile fails)

**Files:**
- Create: `frontend/src/utils/investigateGraphCanvas.js`
- Create: `frontend/src/utils/investigateGraphGate.js`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

- [ ] Canvas under SVG; draw edges in `onFrame`; gate with `canvasEdgesEnabled()` default false until profile proves need.

---

### Task 10: Viewport culling

**Files:**
- Create: `frontend/src/utils/investigateViewportCull.js`
- Modify: `investigateGraphEngine.js` — optional cull pass on force pairs

---

### Task 11: Raise caps (conditional)

**Files:**
- Modify: `frontend/src/utils/investigateGraphMerge.js` — `INVESTIGATE_GRAPH_MAX_NODES = 400`, `MAX_EDGES = 500`
- Modify: `InvestigateGraph.jsx` honesty copy

Only if Task 8–9 green.

---

# Wave 3 — Investigation workspaces

> **Start only after Wave 1 merged.** Wave 2 optional parallel.

### Task 12: Alembic migration `045_investigation_cases`

**Files:**
- Create: `backend/alembic/versions/045_investigation_cases.py`

```python
from sqlalchemy.dialects import postgresql

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        id_type = postgresql.UUID(as_uuid=False)
        snapshot_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        id_type = sa.String(36)
        snapshot_type = sa.Text()

    op.create_table(
        "investigation_cases",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("root_node_id", sa.Text(), nullable=False),
        sa.Column("snapshot", snapshot_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_investigation_cases_owner_updated", "investigation_cases", ["owner_user_id", "updated_at"])
```

- [ ] Run migration on SQLite (`DATABASE_URL=""`) and Postgres (`./scripts/postgres-dev.sh start` + `DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr`) test paths.

---

### Task 13: Cases repository

**Files:**
- Create: `backend/investigations/cases.py`

**Interfaces:**
- `async def list_cases(db, user_id, limit=50)`
- `async def create_case(db, user_id, snapshot, title=None) -> str` — derives `root_node_id` from `snapshot.root_id` or first `snapshot.nodes` match; default title `{root_label} · {UTC date}` when `title` omitted
- `async def get_case(db, user_id, case_id)`
- `async def update_case(db, user_id, case_id, snapshot, title=None)`
- `async def delete_case(db, user_id, case_id)`
- `validate_snapshot(snapshot) -> None` raises `ValueError` for: >500 nodes, >600 edges, malformed `nodes[].node_id` (must match `^(cve|ioc|technique|campaign|publication|sigma_rule):.+`)

---

### Task 14: API routes + tests

**Files:**
- Create: `backend/routers/investigation_cases.py`
- Modify: `backend/main.py` — include router
- Create: `backend/tests/test_investigation_cases.py`

- [ ] TDD: 401 without session, 404 wrong owner, CRUD happy path, oversize snapshot 422, malformed `node_id` 422.

Run (SQLite path): `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_investigation_cases.py -q`

Run (Postgres path, required in Task 16): `cd backend && BRIEFR_REQUIRE_POSTGRES=1 DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr pytest tests/test_investigation_cases.py -q` — fails if Postgres unreachable.

---

### Task 15: Frontend case UI

**Files:**
- Modify: `frontend/src/api.js` — `fetchInvestigationCases`, `saveInvestigationCase`, etc.
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx` — SAVE CASE dialog, OPEN dropdown, `?case=` hydration
- Modify: `docs/PRODUCT_STATUS.md` — saved cases shipped

- [ ] Debounced autosave PUT every 30s when dirty.

---

### Task 16: Wave 3 verification

- [ ] SQLite: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_investigation_cases.py -q`
- [ ] Postgres (required): start `./scripts/postgres-dev.sh start`, then `cd backend && BRIEFR_REQUIRE_POSTGRES=1 DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr pytest tests/test_investigation_cases.py -q`
- [ ] `./scripts/verify-local.sh`
- [ ] Commit

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Incremental expand layout | 1, 2, 4 |
| Expand camera neighborhood | 3, 4 |
| Optimistic expand feedback | 4 (expandingId pulse CSS in Task 6) |
| Local draft restore | 5 |
| Truncation canvas badge | 6 |
| Frame budget / Canvas | 8, 9 |
| Cap raise | 11 |
| investigation_cases table | 12 |
| Case CRUD API | 13, 14 |
| Case UI + deep link | 15 |
| No graph DB | Global constraints |
| PRODUCT_STATUS update | 7 (Wave 1), 15 (Wave 3) |
| load_more camera policy | 3, 4 |
| node_id validation | 13, 14 |
| Postgres case tests | 16 |

No TBD placeholders remain.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-15-investigate-smoothness-program-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with executing-plans checkpoints

**Recommended start:** Wave 1 Task 1 only; merge before Wave 2 profiling.

Which approach?
