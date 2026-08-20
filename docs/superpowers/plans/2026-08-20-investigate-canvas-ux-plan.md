# INVESTIGATE canvas UX — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make INVESTIGATE a readable stored-intel map: architecture-graph wheel zoom (page must not scroll), Fit/pan, inspect vs expand, evidence inspector, and pivots into drawer / IOC LOOKUP / Forge / watchlist / thread PDF.

**Architecture:** Reuse `{ x, y, scale }` + `zoomAtCursor` / `computeFitView` from `architectureGraphView.js` (do **not** add `investigateCamera.js`). World layout stays in `investigateForceLayout.js` (unbounded). Filters and cursor merge stay pure functions. `InvestigateGraph.jsx` copies the architecture wheel/pan listeners and wires existing `InvestigationContext` + `useWatchlist` + `onOpenCve`.

**Tech Stack:** React/Vite, existing SVG + architecture camera, Radix `Checkbox`, Node `node:test`. No new graph libraries.

## Global Constraints

- Semantic tokens only — no raw hex.
- GraphPage JSON unchanged; no graph DB; **no live enrichment on expand**.
- Client caps 200 nodes / 300 edges; root preserved.
- Wheel zoom **must** use `addEventListener('wheel', handler, { passive: false })` and `preventDefault` (React `onWheel` cannot stop page scroll).
- View model is `{ x, y, scale }` — same as System Architecture.
- `prefers-reduced-motion`: force ≤ 12 ticks; camera jumps.
- Overlay controls `aria-label`; hit target ≥ 24px.
- Merge gate: `cd frontend && npm run test:unit` && `npm run build`; `./scripts/verify-local.sh`.

## File map

| File | Responsibility |
|------|----------------|
| Modify: `frontend/src/utils/architectureGraphView.js` | `computePointCloudBounds` for circular nodes |
| Modify: `frontend/src/utils/architectureGraphView.test.js` | Fit tests for point clouds |
| Modify: `frontend/src/utils/investigateForceLayout.js` | Rings, grid repulsion, no pad clamp, `rootId` |
| Modify: `frontend/src/utils/investigateForceLayout.test.js` | n>80 spread |
| Modify: `frontend/src/utils/investigateGraphMerge.js` | `cursorsByNodeId` |
| Modify: `frontend/src/utils/investigateGraphMerge.test.js` | Cursor tests |
| Create: `frontend/src/utils/investigateGraphFilters.js` | Related-CVE + type filter + incident edges |
| Create: `frontend/src/utils/investigateGraphFilters.test.js` | Filter tests |
| Modify: `frontend/src/components/investigate/InvestigateGraph.jsx` | Camera, wheel, inspector, pivots |
| Modify: `frontend/src/components/investigate/InvestigateGraph.css` | `.sa-graph-canvas` analogue |
| Modify: `frontend/src/App.jsx` | Pass watchlist; optional `q` deep-link |
| Modify: `frontend/src/utils/shellUrlState.js` | Preserve/drop `q` with investigate tab |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/USE.md` | Shipped UX |

**Do not create** `investigateCamera.js` — that would fork the architecture camera.

---

### Task 1: Point-cloud bounds on the shared camera

**Files:**
- Modify: `frontend/src/utils/architectureGraphView.js`
- Test: `frontend/src/utils/architectureGraphView.test.js`

**Interfaces:**
- Consumes: existing `computeFitView(bounds, w, h)`, `zoomAtCursor(view, cursorX, cursorY, factor)`
- Produces: `computePointCloudBounds(positions, radius = 12, padding = 48)` → `{ minX, minY, maxX, maxY }`

- [ ] **Step 1: Write the failing test** (append)

```javascript
import { computePointCloudBounds, computeFitView } from './architectureGraphView.js'

describe('computePointCloudBounds', () => {
  it('pads circular nodes so Fit can frame force-layout dots', () => {
    const positions = [
      { x: 100, y: 100 },
      { x: 300, y: 180 },
    ]
    const bounds = computePointCloudBounds(positions, 12, 10)
    assert.equal(bounds.minX, 78)
    assert.equal(bounds.minY, 78)
    assert.equal(bounds.maxX, 322)
    assert.equal(bounds.maxY, 202)
  })

  it('fits a compact clump into a large viewport (scale > 1)', () => {
    const bounds = computePointCloudBounds(
      [{ x: 400, y: 300 }, { x: 420, y: 310 }],
      8,
      20,
    )
    const fit = computeFitView(bounds, 800, 600)
    assert.ok(fit.scale > 1)
    const cx = (bounds.minX + bounds.maxX) / 2
    const cy = (bounds.minY + bounds.maxY) / 2
    assert.ok(Math.abs(fit.x + cx * fit.scale - 400) < 2)
    assert.ok(Math.abs(fit.y + cy * fit.scale - 300) < 2)
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && node --test src/utils/architectureGraphView.test.js`

Expected: FAIL (`computePointCloudBounds` not exported)

- [ ] **Step 3: Implement**

Add to `architectureGraphView.js`:

```javascript
/** Bounding box for force-layout dots (cx, cy) rather than architecture rects. */
export function computePointCloudBounds(positions, radius = 12, padding = 48) {
  if (!positions?.length) {
    return { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of positions) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) continue
    minX = Math.min(minX, node.x - radius)
    minY = Math.min(minY, node.y - radius)
    maxX = Math.max(maxX, node.x + radius)
    maxY = Math.max(maxY, node.y + radius)
  }
  if (!Number.isFinite(minX)) {
    return { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  }
  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  }
}
```

Do **not** change `zoomAtCursor` — INVESTIGATE will call it with canvas-relative CSS pixels, same as architecture.

- [ ] **Step 4: Run — expect PASS** (existing zoom/fit tests still green)

Run: `cd frontend && node --test src/utils/architectureGraphView.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/architectureGraphView.js frontend/src/utils/architectureGraphView.test.js
git commit -m "feat(graph): point-cloud bounds for INVESTIGATE Fit"
```

---

### Task 2: Force layout without viewport clamp

**Files:**
- Modify: `frontend/src/utils/investigateForceLayout.js`
- Test: `frontend/src/utils/investigateForceLayout.test.js`

**Interfaces:**
- Produces: `seedPositions(nodes, width, height, prior, rootId)` and `stepForce(positions, edges, width, height, rootId)` — world coords may leave the SVG; camera frames them.

- [ ] **Step 1: Add tests**

```javascript
  it('spreads a 90-node star (repulsion not skipped)', () => {
    const nodes = Array.from({ length: 90 }, (_, i) => ({
      node_id: `n${i}`,
      entity_type: 'cve',
      label: `n${i}`,
    }))
    const edges = nodes.slice(1).map((node) => ({
      source_node_id: 'n0',
      target_node_id: node.node_id,
    }))
    let positions = seedPositions(nodes, 800, 600, new Map(), 'n0')
    for (let i = 0; i < 40; i += 1) {
      positions = stepForce(positions, edges, 800, 600, 'n0')
    }
    const xs = positions.map((p) => p.x)
    const span = Math.max(...xs) - Math.min(...xs)
    assert.ok(span > 200, `expected spread, got ${span}`)
  })

  it('does not clamp a node to a 36px viewport pad', () => {
    const nodes = [
      { node_id: 'a', entity_type: 'cve' },
      { node_id: 'b', entity_type: 'ioc' },
    ]
    const positions = seedPositions(nodes, 400, 400, new Map(), 'a')
    positions[1].x = -80
    positions[1].y = -80
    positions[1].vx = 0
    positions[1].vy = 0
    const next = stepForce(positions, [], 400, 400, 'a')
    const b = next.find((n) => n.node_id === 'b')
    assert.ok(b.x < 36, `expected no pad clamp, got x=${b.x}`)
  })
```

Keep the existing finite-coords test; pass `rootId` optionally (default first node).

- [ ] **Step 2: Run — expect FAIL** on spread/clamp

Run: `cd frontend && node --test src/utils/investigateForceLayout.test.js`

- [ ] **Step 3: Implement**

Replace `investigateForceLayout.js` with:

```javascript
/** Client-only force layout for INVESTIGATE. API GraphPage has no x/y. */

const REPULSE = 2800
const SPRING = 0.035
const SPRING_LENGTH_MIN = 160
const SPRING_LENGTH_MAX = 420
const ROOT_CENTER = 0.008
const DAMPING = 0.86
const WORLD_LIMIT = 8000
const GRID_REPULSE_MAX = 24

function springLength(count) {
  return Math.min(
    SPRING_LENGTH_MAX,
    SPRING_LENGTH_MIN + Math.sqrt(Math.max(count, 1)) * 18,
  )
}

function ringRadiusForType(entityType, isRoot) {
  if (isRoot) return 0
  if (entityType === 'technique' || entityType === 'sigma_rule') return 0.42
  if (entityType === 'ioc' || entityType === 'campaign' || entityType === 'publication') {
    return 0.68
  }
  if (entityType === 'cve') return 1
  return 0.85
}

export function seedPositions(nodes, width, height, prior = new Map(), rootId = null) {
  const cx = width / 2
  const cy = height / 2
  const base = Math.min(width, height) * 0.42
  const root = rootId || nodes[0]?.node_id
  const buckets = new Map()
  for (const node of nodes) {
    const key = node.entity_type || 'other'
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push(node)
  }
  return nodes.map((node) => {
    const kept = prior.get(node.node_id)
    if (kept && Number.isFinite(kept.x) && Number.isFinite(kept.y)) {
      return { ...node, x: kept.x, y: kept.y, vx: kept.vx || 0, vy: kept.vy || 0 }
    }
    if (node.node_id === root) {
      return { ...node, x: cx, y: cy, vx: 0, vy: 0 }
    }
    const group = buckets.get(node.entity_type || 'other') || []
    const gi = Math.max(0, group.findIndex((item) => item.node_id === node.node_id))
    const angle = (gi / Math.max(group.length, 1)) * Math.PI * 2
    const radius = base * ringRadiusForType(node.entity_type, false)
    return {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    }
  })
}

function applyRepulsion(next) {
  const n = next.length
  const cell = springLength(n)
  const buckets = new Map()
  const keyOf = (x, y) => `${Math.floor(x / cell)}:${Math.floor(y / cell)}`
  next.forEach((node, i) => {
    const k = keyOf(node.x, node.y)
    if (!buckets.has(k)) buckets.set(k, [])
    buckets.get(k).push(i)
  })
  for (let i = 0; i < n; i += 1) {
    const a = next[i]
    const gx = Math.floor(a.x / cell)
    const gy = Math.floor(a.y / cell)
    let considered = 0
    for (let ox = -1; ox <= 1; ox += 1) {
      for (let oy = -1; oy <= 1; oy += 1) {
        const neighbors = buckets.get(`${gx + ox}:${gy + oy}`)
        if (!neighbors) continue
        for (const j of neighbors) {
          if (j <= i) continue
          const b = next[j]
          let dx = a.x - b.x
          let dy = a.y - b.y
          let distSq = dx * dx + dy * dy
          if (distSq < 16) {
            dx = ((i + j) % 5) - 2 || 0.5
            dy = ((i * 3 + j) % 5) - 2 || 0.5
            distSq = dx * dx + dy * dy
          }
          const dist = Math.sqrt(distSq)
          const force = REPULSE / distSq
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          a.vx += fx
          a.vy += fy
          b.vx -= fx
          b.vy -= fy
          considered += 1
          if (considered >= GRID_REPULSE_MAX) break
        }
      }
    }
  }
}

function applySprings(next, edges, byId) {
  const rest = springLength(next.length)
  for (const edge of edges) {
    const a = byId.get(edge.source_node_id)
    const b = byId.get(edge.target_node_id)
    if (!a || !b) continue
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
    const stretch = dist - rest
    a.vx += (dx / dist) * stretch * SPRING
    a.vy += (dy / dist) * stretch * SPRING
    b.vx -= (dx / dist) * stretch * SPRING
    b.vy -= (dy / dist) * stretch * SPRING
  }
}

export function stepForce(positions, edges, width, height, rootId = null) {
  const next = positions.map((node) => ({ ...node }))
  const byId = new Map(next.map((node) => [node.node_id, node]))
  const root = rootId || next[0]?.node_id
  applyRepulsion(next)
  applySprings(next, edges, byId)
  const cx = width / 2
  const cy = height / 2
  for (const node of next) {
    if (node.node_id === root) {
      node.vx += (cx - node.x) * ROOT_CENTER
      node.vy += (cy - node.y) * ROOT_CENTER
    }
    node.vx *= DAMPING
    node.vy *= DAMPING
    node.x += node.vx
    node.y += node.vy
    node.x = Math.min(WORLD_LIMIT, Math.max(-WORLD_LIMIT, node.x))
    node.y = Math.min(WORLD_LIMIT, Math.max(-WORLD_LIMIT, node.y))
  }
  return next
}
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd frontend && node --test src/utils/investigateForceLayout.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateForceLayout.js frontend/src/utils/investigateForceLayout.test.js
git commit -m "fix(investigate): spread force layout without viewport clamp"
```

---

### Task 3: Persist `next_cursor`

**Files:**
- Modify: `frontend/src/utils/investigateGraphMerge.js`
- Test: `frontend/src/utils/investigateGraphMerge.test.js`

- [ ] **Step 1: Failing test**

```javascript
  it('stores next_cursor per expanded root id', () => {
    const page = {
      root: { node_id: 'cve:CVE-1', entity_type: 'cve', entity_id: 'CVE-1', label: 'CVE-1' },
      nodes: [{ node_id: 'cve:CVE-1', entity_type: 'cve', entity_id: 'CVE-1', label: 'CVE-1' }],
      edges: [],
      truncated: true,
      next_cursor: 'abc',
      source_status: 'ok',
      knowledge_state: 'partial',
    }
    const first = mergeGraphPage(emptyGraphState(), page)
    assert.equal(first.cursorsByNodeId['cve:CVE-1'], 'abc')
    const second = mergeGraphPage(first, {
      ...page,
      root: { node_id: 'cve:CVE-2', entity_type: 'cve', entity_id: 'CVE-2', label: 'CVE-2' },
      nodes: [{ node_id: 'cve:CVE-2', entity_type: 'cve', entity_id: 'CVE-2', label: 'CVE-2' }],
      truncated: false,
      next_cursor: null,
    })
    assert.equal(second.cursorsByNodeId['cve:CVE-1'], 'abc')
    assert.equal(second.cursorsByNodeId['cve:CVE-2'], null)
  })
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && node --test src/utils/investigateGraphMerge.test.js`

- [ ] **Step 3: Implement**

`emptyGraphState()` adds `next_cursor: null`, `cursorsByNodeId: {}`.

`mergeGraphPage` return:

```javascript
  const expandedId = page.root?.node_id
  const cursorsByNodeId = { ...(prior.cursorsByNodeId || {}) }
  if (expandedId) {
    cursorsByNodeId[expandedId] = page.next_cursor || null
  }
  return {
    nodes: trimmed.nodes,
    edges: trimmed.edges,
    truncated: Boolean(prior.truncated || page.truncated || trimmed.capped),
    capped: Boolean(prior.capped || trimmed.capped),
    knowledge_state: page.knowledge_state || prior.knowledge_state,
    source_status: degraded ? 'degraded' : (page.source_status || prior.source_status || 'ok'),
    root_id: rootId,
    next_cursor: page.next_cursor ?? prior.next_cursor ?? null,
    cursorsByNodeId,
  }
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphMerge.js frontend/src/utils/investigateGraphMerge.test.js
git commit -m "feat(investigate): keep relationship next_cursor per node"
```

---

### Task 4: Visible-graph filters + incident edges

**Files:**
- Create: `frontend/src/utils/investigateGraphFilters.js`
- Test: `frontend/src/utils/investigateGraphFilters.test.js`

**Interfaces:**
- Produces: `visibleGraph(graph, { showRelatedCves, entityType })`, `incidentEdges(graph, nodeId)`, `relatedCveCount(graph)`, `neighborIds(graph, nodeId)`

- [ ] **Step 1: Failing tests**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  visibleGraph,
  incidentEdges,
  relatedCveCount,
  neighborIds,
} from './investigateGraphFilters.js'

const root = { node_id: 'cve:ROOT', entity_type: 'cve', entity_id: 'ROOT', label: 'ROOT' }
const ioc = { node_id: 'ioc:ip:1.1.1.1', entity_type: 'ioc', entity_id: 'ip:1.1.1.1', label: '1.1.1.1' }
const rel = { node_id: 'cve:REL', entity_type: 'cve', entity_id: 'REL', label: 'REL' }
const graph = {
  root_id: 'cve:ROOT',
  nodes: [root, ioc, rel],
  edges: [
    {
      edge_id: 'e-ioc',
      source_node_id: 'cve:ROOT',
      target_node_id: 'ioc:ip:1.1.1.1',
      source_key: 'otx',
      edge_class: 'reported',
      observed_at: '2024-01-01T00:00:00Z',
    },
    {
      edge_id: 'e-rel',
      source_node_id: 'cve:ROOT',
      target_node_id: 'cve:REL',
      source_key: 'related_cve_heuristic',
      edge_class: 'derived',
    },
  ],
}

describe('visibleGraph', () => {
  it('hides heuristic-only CVEs when showRelatedCves is false', () => {
    const out = visibleGraph(graph, { showRelatedCves: false })
    assert.deepEqual(out.nodes.map((n) => n.node_id).sort(), ['cve:ROOT', 'ioc:ip:1.1.1.1'])
  })

  it('filters to IOC type chips without dropping the root', () => {
    const out = visibleGraph(graph, { showRelatedCves: true, entityType: 'ioc' })
    assert.ok(out.nodes.some((n) => n.node_id === 'cve:ROOT'))
    assert.ok(out.nodes.every((n) => n.entity_type === 'ioc' || n.node_id === 'cve:ROOT'))
  })
})

describe('incidentEdges', () => {
  it('returns edges touching the selected node with source_key', () => {
    const rows = incidentEdges(graph, 'cve:ROOT')
    assert.equal(rows.length, 2)
    assert.equal(rows[0].source_key, 'otx')
  })
})

describe('neighborIds', () => {
  it('lists adjacent node ids', () => {
    const ids = neighborIds(graph, 'cve:ROOT')
    assert.ok(ids.has('ioc:ip:1.1.1.1'))
    assert.ok(ids.has('cve:REL'))
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```javascript
export function relatedCveCount(graph) {
  return (graph.edges || []).filter((e) => e.source_key === 'related_cve_heuristic').length
}

export function incidentEdges(graph, nodeId) {
  if (!nodeId) return []
  return (graph.edges || []).filter(
    (e) => e.source_node_id === nodeId || e.target_node_id === nodeId,
  )
}

export function neighborIds(graph, nodeId) {
  const ids = new Set()
  for (const e of incidentEdges(graph, nodeId)) {
    ids.add(e.source_node_id === nodeId ? e.target_node_id : e.source_node_id)
  }
  return ids
}

export function visibleGraph(graph, { showRelatedCves = true, entityType = 'all' } = {}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  let justified = new Set(nodes.map((n) => n.node_id))
  if (!showRelatedCves) {
    justified = new Set()
    if (rootId) justified.add(rootId)
    for (const edge of edges) {
      if (edge.source_key === 'related_cve_heuristic') continue
      justified.add(edge.source_node_id)
      justified.add(edge.target_node_id)
    }
  }
  let visibleNodes = nodes.filter((n) => justified.has(n.node_id))
  if (entityType && entityType !== 'all') {
    visibleNodes = visibleNodes.filter(
      (n) => n.node_id === rootId || n.entity_type === entityType,
    )
  }
  const ids = new Set(visibleNodes.map((n) => n.node_id))
  const visibleEdges = edges.filter(
    (e) => ids.has(e.source_node_id) && ids.has(e.target_node_id)
      && (showRelatedCves || e.source_key !== 'related_cve_heuristic'),
  )
  return { nodes: visibleNodes, edges: visibleEdges }
}

export function otherNodeId(edge, nodeId) {
  return edge.source_node_id === nodeId ? edge.target_node_id : edge.source_node_id
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphFilters.js frontend/src/utils/investigateGraphFilters.test.js
git commit -m "feat(investigate): client filters and incident-edge helpers"
```

---

### Task 5: Canvas — wheel zoom, Fit, inspect, inspector, pivots

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`
- Modify: `frontend/src/App.jsx` (watchlist props)

**Interfaces:**
- Consumes: Task 1 camera, Task 2 layout, Task 3 cursors, Task 4 filters, `InvestigationContext`, `onOpenCve`, `watchlist`
- Produces: analyst canvas per spec

- [ ] **Step 1: Props from App**

`App.jsx` around the INVESTIGATE panel:

```jsx
<InvestigateGraph
  isActive={activeTab === 'investigate'}
  onOpenCve={openCveById}
  watchlist={watchlist}
  onWatchlistChange={handleWatchlistChange}
/>
```

Use the same `handleWatchlistChange` / `watchlist.getState` already passed to `DetailDrawer`.

- [ ] **Step 2: View state + non-passive wheel (required for scroll zoom)**

Copy architecture — do **not** use React `onWheel`:

```javascript
import {
  DEFAULT_VIEW,
  computeFitView,
  computePointCloudBounds,
  truncateNodeLabel,
  zoomAtCursor,
} from '../../utils/architectureGraphView.js'

const [view, setView] = useState(() => ({ ...DEFAULT_VIEW }))
const viewRef = useRef(view)
viewRef.current = view
const userMovedRef = useRef(false)

useEffect(() => {
  const el = canvasRef.current
  if (!el) return undefined
  const handler = (e) => {
    e.preventDefault()
    userMovedRef.current = true
    const rect = el.getBoundingClientRect()
    const cursorX = e.clientX - rect.left
    const cursorY = e.clientY - rect.top
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
    setView((v) => zoomAtCursor(v, cursorX, cursorY, factor))
  }
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [graph.root_id])
```

Pan: copy `ArchitectureGraphSection` `onPointerDown` / `Move` / `Up` (ignore `[data-node-id]` for pan; node pointer = drag node or click-select).

Fit:

```javascript
const fitGraphToView = useCallback(() => {
  const el = canvasRef.current
  if (!el || !positions.length) return
  const bounds = computePointCloudBounds(positions, 12, 48)
  setView(computeFitView(bounds, el.clientWidth, el.clientHeight))
}, [positions])
```

After force `ticks === maxTicks` and `!userMovedRef.current`, call `fitGraphToView()`. RESET = Fit (not scale 1). Overlay `+`/`−` zoom at canvas center via `zoomAtCursor(view, width/2, height/2, 1.1)`.

SVG: `<g transform={\`translate(${view.x} ${view.y}) scale(${view.scale})\`}>`.

- [ ] **Step 3: Click = select; double-click = expand**

Remove `onClick={() => expandNode(node)}`. Click sets `selectedId`; click selected deselects. `onDoubleClick` → `expandNode`. Inspector EXPAND stays.

- [ ] **Step 4: Inspector evidence + pivots**

Incident list from `incidentEdges(graph, selectedId)`. Actions:

```javascript
const investigation = useInvestigationOptional()

// LOOKUP LIVE — stored graph must not enrich; this pivots to IOC LOOKUP
if (selected.entity_type === 'ioc') {
  <button type="button" onClick={() => investigation.pivotToIoc(selected.label || selected.entity_id.split(':').slice(1).join(':'))}>
    LOOKUP LIVE
  </button>
}
if (selected.entity_type === 'technique') {
  <button type="button" onClick={() => investigation.pivotToTechnique(selected.entity_id, selected.label)}>
    OPEN IN FORGE
  </button>
}
if (selected.entity_type === 'cve' && watchlist) {
  <button type="button" onClick={() => onWatchlistChange(selected.entity_id, 'pin')}>
    {watchlist.getState(selected.entity_id) === 'pin' ? 'UNPIN WATCHLIST' : 'PIN WATCHLIST'}
  </button>
}
```

COPY ID: `navigator.clipboard.writeText(selected.entity_id)`.

PIN VISIBLE CVEs: `view.nodes.filter(n => n.entity_type === 'cve').forEach(n => investigation.ensureCveInThread(n.entity_id))`.

Related CVEs: Radix `Checkbox` `checked={showRelatedCves}` `onCheckedChange={setShowRelatedCves}` `label={`Related CVEs (${relatedCveCount(graph)})`}`.

Type chips: ALL / cve / ioc / technique / campaign / publication — `setEntityType`.

Find: input; highlight `node.label` substring; Enter → pan so match is centered (`setView` so `view.x + match.x * view.scale ≈ width/2`).

Semantic: Checkbox refetch `fetchInvestigationRelationships(..., { include_semantic: true })` replacing graph via `mergeGraphPage(emptyGraphState(), page)` **only for the current root** (do not wipe expansions unless simplest: merge with include_semantic on root only). Spec: refetch **root** relationships with the flag and `mergeGraphPage` (sticky nodes OK).

LOAD MORE: `fetchInvestigationRelationships(type, id, { cursor: graph.cursorsByNodeId[id] })`.

Neighborhood dim: if `selectedId || hoveredId`, dim nodes not in `neighborIds` ∪ focus ∪ root.

- [ ] **Step 5: CSS**

```css
.investigate-canvas {
  overflow: hidden;
  touch-action: none;
  cursor: grab;
  user-select: none;
  position: relative;
  flex: 1 1 auto;
  min-height: 360px;
}

.investigate-canvas:active {
  cursor: grabbing;
}

.investigate-camera-tools {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  display: flex;
  gap: var(--space-1);
  z-index: 1;
}

.investigate-camera-tools button {
  min-width: var(--hit-target-min, 24px);
  height: var(--control-height-md, 32px);
  border: 1px solid var(--border-default, var(--border2));
  background: var(--surface-raised, var(--bg2));
  color: var(--text-primary, var(--text));
  font-family: var(--font-mono);
  cursor: pointer;
}

.investigate-node-dim {
  opacity: 0.28;
}
```

Hint: `Scroll to zoom · drag to pan · click to inspect · double-click to expand`.

- [ ] **Step 6: Manual smoke**

1. Resolve a busy CVE. Auto-Fit fills canvas.
2. Wheel: zoom at cursor; **page behind does not scroll**.
3. `+`/`−`/FIT/RESET without wheel.
4. Click spoke: inspector shows `source_key`; node count unchanged.
5. LOOKUP LIVE on an IOC opens IOC LOOKUP with prefill.
6. OPEN CVE opens drawer.
7. Uncheck Related CVEs: star thins.
8. LOAD MORE if truncated.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/components/investigate/InvestigateGraph.css frontend/src/App.jsx
git commit -m "feat(investigate): architecture-style pan/zoom and inspect vs expand"
```

---

### Task 6: Deep-link `?tab=investigate&q=`

**Files:**
- Modify: `frontend/src/utils/shellUrlState.js`
- Modify: `frontend/src/utils/shellUrlState.test.js`
- Modify: `frontend/src/App.jsx` or `InvestigateGraph.jsx`

- [ ] **Step 1: Test `buildAppTabSearchParams`**

When leaving investigate, delete `q`. When entering investigate, do not invent `q`. When already on investigate, `InvestigateGraph` reads `searchParams.get('q')` once on mount / when `q` changes and `runSearch`.

Add test:

```javascript
  it('drops investigate q when leaving the investigate tab', () => {
    const prev = new URLSearchParams('tab=investigate&q=CVE-2024-9100')
    const next = buildAppTabSearchParams(prev, 'feed')
    assert.equal(next.get('tab'), 'feed')
    assert.equal(next.get('q'), null)
  })
```

In `buildAppTabSearchParams`, if `nextTab !== 'investigate'` then `next.delete('q')`.

On successful resolve, `pushContext` set `q` to the resolved query string (CVE id).

- [ ] **Step 2: Run** `cd frontend && node --test src/utils/shellUrlState.test.js`

- [ ] **Step 3: Implement + wire `useSearchParams` in InvestigateGraph** (or pass `initialQuery` from App). Prefer App passing `investigateQuery` from `searchParams.get('q')` when `activeTab === 'investigate'` to avoid extra router imports in the canvas.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/shellUrlState.js frontend/src/utils/shellUrlState.test.js frontend/src/App.jsx frontend/src/components/investigate/InvestigateGraph.jsx
git commit -m "feat(investigate): deep-link search via tab=investigate&q="
```

---

### Task 7: Docs

**Files:**
- Modify: `docs/PRODUCT_STATUS.md`
- Modify: `docs/USE.md`

- [ ] **Step 1:** PRODUCT_STATUS — pan/zoom (architecture camera), inspect vs expand, evidence inspector, pivots, related-CVE toggle, Load more, `q=` deep-link. Remove “click-to-expand” as the primary gesture.

- [ ] **Step 2:** USE.md — scroll to zoom, click inspect, double-click expand.

- [ ] **Step 3: Commit**

```bash
git add docs/PRODUCT_STATUS.md docs/USE.md
git commit -m "docs: INVESTIGATE map navigation and stored-intel pivots"
```

---

### Task 8: Verify

- [ ] `cd frontend && npm run test:unit` — PASS
- [ ] `cd frontend && npm run build` — PASS
- [ ] `./scripts/verify-local.sh` — green

---

## Spec coverage

| Spec | Task |
|------|------|
| Wheel zoom, page must not scroll | 5 (reuse Task 1 `zoomAtCursor`) |
| Fit / pan / +− / Reset | 1, 5 |
| Layout unclamped | 2 |
| Inspect vs expand | 5 |
| LOD + glyphs | 5 |
| Inspector evidence | 4, 5 |
| Related CVE + type chips + find | 4, 5 |
| Pivots (drawer, IOC, Forge, watchlist, thread) | 5 |
| Load more | 3, 5 |
| Deep-link q= | 6 |
| Docs | 7 |
| No forked camera / no graph lib | Task 1 + global |

## Placeholder scan

No TBD. `handleWatchlistChange` already exists in `App.jsx` (~line 838). `pivotToIoc` / `pivotToTechnique` already exist on `InvestigationContext`.

## Deliberately not in this plan

Server-side related-CVE ranking; minimap; PNG export; graph DB; email/mutex nodes.
