# INVESTIGATE canvas UX — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make INVESTIGATE a readable stored-intel map: architecture-graph wheel zoom (page must not scroll), Fit/pan/`+`/`−`, inspect vs expand, evidence inspector, density filters, and pivots into drawer / IOC LOOKUP (correct IocKind) / Forge / watchlist / thread PDF.

**Architecture:** Reuse `{ x, y, scale }` + `zoomAtCursor` / `computeFitView` from `architectureGraphView.js` (do **not** add `investigateCamera.js`). World layout stays in `investigateForceLayout.js` (unbounded). Filters, IOC parse, and cursor merge stay pure functions. `InvestigateGraph.jsx` copies the architecture wheel/pan listeners and wires existing `InvestigationContext` + `useWatchlist` + `onOpenCve` + `openForgeCampaigns`.

**Tech Stack:** React/Vite, existing SVG + architecture camera, Radix `Checkbox` (`frontend/src/components/ui/Checkbox.jsx`), Node `node:test`. No new graph libraries.

## Global Constraints

- Semantic tokens only — no raw hex.
- GraphPage JSON unchanged; GraphNode stays `extra=forbid`; **no live enrichment on expand**.
- Client caps 200 nodes / 300 edges; root preserved.
- Wheel zoom **must** use `addEventListener('wheel', handler, { passive: false })` and `preventDefault` (React `onWheel` cannot stop page scroll).
- View model is `{ x, y, scale }` — same as System Architecture.
- `prefers-reduced-motion`: force ≤ 12 ticks; camera jumps.
- Overlay controls `aria-label`; hit target ≥ 24px (`--hit-target-min`).
- `handleWatchlistChange(cveId, action)` no-ops unless `action === 'pin'`.
- EXPAND only for `cve|ioc|technique|campaign|publication` (Sigma is 422).
- LOOKUP LIVE must pass IocKind (`ip|hash|domain|url`), never hardcode `ip`.
- Merge gate: `cd frontend && npm run test:unit` && `npm run build`; `./scripts/verify-local.sh`.

## File map

| File | Responsibility |
|------|----------------|
| Modify: `frontend/src/utils/architectureGraphView.js` | `computePointCloudBounds` for circular nodes |
| Modify: `frontend/src/utils/architectureGraphView.test.js` | Fit tests for point clouds |
| Modify: `frontend/src/utils/investigateForceLayout.js` | Rings, grid repulsion, no pad clamp, `rootId` |
| Modify: `frontend/src/utils/investigateForceLayout.test.js` | n>80 spread |
| Modify: `frontend/src/utils/investigateGraphMerge.js` | `cursorsByNodeId` + `include_semantic` query |
| Modify: `frontend/src/utils/investigateGraphMerge.test.js` | Cursor + query tests |
| Create: `frontend/src/utils/investigateGraphFilters.js` | Related-CVE, type, edge-class, isolate, IOC parse, markdown |
| Create: `frontend/src/utils/investigateGraphFilters.test.js` | Filter / parse / markdown tests |
| Modify: `frontend/src/context/InvestigationContext.jsx` | `pivotToIoc` third arg `indicatorType` |
| Modify: `frontend/src/components/investigate/InvestigateGraph.jsx` | Camera, inspect, inspector, pivots, filters |
| Modify: `frontend/src/components/investigate/InvestigateGraph.css` | `.sa-graph-canvas` analogue |
| Modify: `frontend/src/App.jsx` | watchlist, `openForgeCampaigns`, `openAdvisories`, `q` deep-link |
| Modify: `frontend/src/utils/shellUrlState.js` | Drop `q` when leaving investigate |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/USE.md` | Shipped UX |

**Do not create** `investigateCamera.js` — that would fork the architecture camera.

**Do not drag nodes.** Pan empty canvas only.

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

Add to `architectureGraphView.js` (do **not** change `zoomAtCursor`):

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

- [ ] **Step 3: Implement** — replace `investigateForceLayout.js` with:

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
        if (considered >= GRID_REPULSE_MAX) break
      }
      if (considered >= GRID_REPULSE_MAX) break
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

### Task 3: Persist `next_cursor` and send `include_semantic`

**Files:**
- Modify: `frontend/src/utils/investigateGraphMerge.js`
- Test: `frontend/src/utils/investigateGraphMerge.test.js`

**Interfaces:**
- Produces: `emptyGraphState().cursorsByNodeId`; `mergeGraphPage` writes `cursorsByNodeId[page.root.node_id] = page.next_cursor`; `buildInvestigationRelationshipQuery` serializes `include_semantic` and `edge_class` (canvas uses semantic only; do not refetch by `edge_class`).

- [ ] **Step 1: Failing tests**

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

In `buildInvestigationRelationshipQuery` describe:

```javascript
  it('sends include_semantic when true', () => {
    assert.equal(
      buildInvestigationRelationshipQuery({ include_semantic: true }),
      '?include_semantic=true',
    )
  })

  it('omits include_semantic when false', () => {
    assert.equal(buildInvestigationRelationshipQuery({ include_semantic: false }), '')
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

`buildInvestigationRelationshipQuery`:

```javascript
export function buildInvestigationRelationshipQuery(params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.depth != null) qs.set('depth', String(params.depth))
  if (params.cursor) qs.set('cursor', params.cursor)
  if (params.include_semantic === true) qs.set('include_semantic', 'true')
  if (params.edge_class) qs.set('edge_class', String(params.edge_class))
  return qs.toString() ? `?${qs.toString()}` : ''
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphMerge.js frontend/src/utils/investigateGraphMerge.test.js
git commit -m "feat(investigate): keep next_cursor and send include_semantic"
```

---

### Task 4: Visible-graph filters, isolate, IOC parse, neighborhood markdown

**Files:**
- Create: `frontend/src/utils/investigateGraphFilters.js`
- Test: `frontend/src/utils/investigateGraphFilters.test.js`

**Interfaces:**
- Produces:
  - `EXPANDABLE_ENTITY_TYPES` `Set`
  - `IOC_KINDS` `Set`
  - `EDGE_CLASS_CHIPS` `['direct_fact','reported','derived','analyst_assertion','semantic']`
  - `canExpandEntityType(type)` → boolean
  - `parseIocEntityId(entityId, label)` → `{ type, value }`
  - `visibleGraph(graph, { showRelatedCves, entityType, edgeClasses, isolateNodeId })` → `{ nodes, edges }`
  - `incidentEdges(graph, nodeId)` / `neighborIds(graph, nodeId)` / `otherNodeId(edge, nodeId)`
  - `relatedCveCount(graph)` / `heuristicCveIds(graph)` → `Set` of CVE node ids only reached via `related_cve_heuristic`
  - `formatNeighborhoodMarkdown(node, edges, nodesById)` → string

- [ ] **Step 1: Write the full test file**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  visibleGraph,
  incidentEdges,
  relatedCveCount,
  neighborIds,
  parseIocEntityId,
  canExpandEntityType,
  heuristicCveIds,
  formatNeighborhoodMarkdown,
} from './investigateGraphFilters.js'

const root = { node_id: 'cve:ROOT', entity_type: 'cve', entity_id: 'ROOT', label: 'ROOT' }
const ioc = { node_id: 'ioc:hash:abcd', entity_type: 'ioc', entity_id: 'hash:abcd', label: 'abcd' }
const rel = { node_id: 'cve:REL', entity_type: 'cve', entity_id: 'REL', label: 'REL' }
const sigma = { node_id: 'sigma_rule:S1', entity_type: 'sigma_rule', entity_id: 'S1', label: 'S1' }
const graph = {
  root_id: 'cve:ROOT',
  nodes: [root, ioc, rel, sigma],
  edges: [
    {
      edge_id: 'e-ioc',
      source_node_id: 'cve:ROOT',
      target_node_id: 'ioc:hash:abcd',
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
    {
      edge_id: 'e-sigma',
      source_node_id: 'cve:ROOT',
      target_node_id: 'sigma_rule:S1',
      source_key: 'sigmahq',
      edge_class: 'direct_fact',
    },
  ],
}

describe('visibleGraph', () => {
  it('hides heuristic-only CVEs when showRelatedCves is false', () => {
    const out = visibleGraph(graph, { showRelatedCves: false })
    assert.deepEqual(
      out.nodes.map((n) => n.node_id).sort(),
      ['cve:ROOT', 'ioc:hash:abcd', 'sigma_rule:S1'],
    )
  })

  it('filters to IOC type chips without dropping the root', () => {
    const out = visibleGraph(graph, { showRelatedCves: true, entityType: 'ioc' })
    assert.ok(out.nodes.some((n) => n.node_id === 'cve:ROOT'))
    assert.ok(out.nodes.every((n) => n.entity_type === 'ioc' || n.node_id === 'cve:ROOT'))
  })

  it('hides derived edges when edgeClasses omits derived', () => {
    const out = visibleGraph(graph, {
      showRelatedCves: true,
      edgeClasses: new Set(['direct_fact', 'reported']),
    })
    assert.equal(out.edges.some((e) => e.edge_class === 'derived'), false)
    assert.equal(out.nodes.some((n) => n.node_id === 'cve:REL'), false)
  })

  it('isolates selected plus one hop', () => {
    const out = visibleGraph(graph, { isolateNodeId: 'ioc:hash:abcd' })
    assert.deepEqual(
      out.nodes.map((n) => n.node_id).sort(),
      ['cve:ROOT', 'ioc:hash:abcd'],
    )
  })
})

describe('parseIocEntityId', () => {
  it('splits kind:value without treating hashes as ips', () => {
    assert.deepEqual(parseIocEntityId('hash:deadbeef', 'deadbeef'), {
      type: 'hash',
      value: 'deadbeef',
    })
    assert.deepEqual(parseIocEntityId('domain:evil.example', 'evil.example'), {
      type: 'domain',
      value: 'evil.example',
    })
    assert.deepEqual(parseIocEntityId('url:https://evil.example/x', 'https://evil.example/x'), {
      type: 'url',
      value: 'https://evil.example/x',
    })
    assert.deepEqual(parseIocEntityId('ip:1.1.1.1', '1.1.1.1'), {
      type: 'ip',
      value: '1.1.1.1',
    })
  })
})

describe('canExpandEntityType', () => {
  it('allows publication and rejects sigma_rule', () => {
    assert.equal(canExpandEntityType('publication'), true)
    assert.equal(canExpandEntityType('sigma_rule'), false)
  })
})

describe('incidentEdges', () => {
  it('returns edges touching the selected node with source_key', () => {
    const rows = incidentEdges(graph, 'cve:ROOT')
    assert.equal(rows.length, 3)
    assert.equal(rows[0].source_key, 'otx')
  })
})

describe('formatNeighborhoodMarkdown', () => {
  it('emits ticket-ready lines', () => {
    const md = formatNeighborhoodMarkdown(root, incidentEdges(graph, 'cve:ROOT'), new Map(
      graph.nodes.map((n) => [n.node_id, n]),
    ))
    assert.match(md, /cve ROOT/)
    assert.match(md, /otx/)
    assert.match(md, /reported/)
  })
})

describe('heuristicCveIds', () => {
  it('marks related CVEs that have no non-heuristic edge', () => {
    const ids = heuristicCveIds(graph)
    assert.equal(ids.has('cve:REL'), true)
    assert.equal(ids.has('cve:ROOT'), false)
  })
})
```

- [ ] **Step 2: Run — expect FAIL** (`investigateGraphFilters.js` missing)

Run: `cd frontend && node --test src/utils/investigateGraphFilters.test.js`

- [ ] **Step 3: Implement `investigateGraphFilters.js`**

```javascript
export const EXPANDABLE_ENTITY_TYPES = new Set([
  'cve', 'ioc', 'technique', 'campaign', 'publication',
])
export const IOC_KINDS = new Set(['ip', 'hash', 'domain', 'url'])
export const EDGE_CLASS_CHIPS = [
  'direct_fact', 'reported', 'derived', 'analyst_assertion', 'semantic',
]
export const DEFAULT_EDGE_CLASSES = new Set([
  'direct_fact', 'reported', 'derived', 'analyst_assertion',
])

export function canExpandEntityType(entityType) {
  return EXPANDABLE_ENTITY_TYPES.has(entityType)
}

export function parseIocEntityId(entityId, label) {
  const raw = String(entityId || '')
  const idx = raw.indexOf(':')
  if (idx <= 0) return { type: 'ip', value: label || raw }
  const type = raw.slice(0, idx).toLowerCase()
  const value = raw.slice(idx + 1) || label || ''
  return { type: IOC_KINDS.has(type) ? type : 'ip', value }
}

export function relatedCveCount(graph) {
  return (graph.edges || []).filter((e) => e.source_key === 'related_cve_heuristic').length
}

export function incidentEdges(graph, nodeId) {
  if (!nodeId) return []
  return (graph.edges || []).filter(
    (e) => e.source_node_id === nodeId || e.target_node_id === nodeId,
  )
}

export function otherNodeId(edge, nodeId) {
  return edge.source_node_id === nodeId ? edge.target_node_id : edge.source_node_id
}

export function neighborIds(graph, nodeId) {
  const ids = new Set()
  for (const e of incidentEdges(graph, nodeId)) {
    ids.add(otherNodeId(e, nodeId))
  }
  return ids
}

export function heuristicCveIds(graph) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const byCve = new Map()
  for (const node of nodes) {
    if (node.entity_type === 'cve') byCve.set(node.node_id, { heuristic: false, other: false })
  }
  for (const edge of edges) {
    for (const nid of [edge.source_node_id, edge.target_node_id]) {
      const row = byCve.get(nid)
      if (!row) continue
      if (edge.source_key === 'related_cve_heuristic') row.heuristic = true
      else row.other = true
    }
  }
  const out = new Set()
  for (const [id, row] of byCve) {
    if (row.heuristic && !row.other && id !== graph.root_id) out.add(id)
  }
  return out
}

export function visibleGraph(graph, {
  showRelatedCves = true,
  entityType = 'all',
  edgeClasses = null,
  isolateNodeId = null,
} = {}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  const hiddenHeuristic = showRelatedCves ? new Set() : heuristicCveIds(graph)
  const allowedClass = edgeClasses || null

  let visibleEdges = edges.filter((e) => {
    if (allowedClass && !allowedClass.has(e.edge_class)) return false
    if (!showRelatedCves && e.source_key === 'related_cve_heuristic') return false
    return true
  })

  let ids = new Set()
  if (rootId) ids.add(rootId)
  for (const edge of visibleEdges) {
    ids.add(edge.source_node_id)
    ids.add(edge.target_node_id)
  }
  for (const hid of hiddenHeuristic) ids.delete(hid)
  if (rootId) ids.add(rootId)

  if (isolateNodeId) {
    const keep = new Set([isolateNodeId])
    for (const edge of visibleEdges) {
      if (edge.source_node_id === isolateNodeId) keep.add(edge.target_node_id)
      if (edge.target_node_id === isolateNodeId) keep.add(edge.source_node_id)
    }
    ids = keep
  }

  let visibleNodes = nodes.filter((n) => ids.has(n.node_id))
  if (entityType && entityType !== 'all') {
    visibleNodes = visibleNodes.filter(
      (n) => n.node_id === rootId || n.entity_type === entityType,
    )
  }
  const visibleIds = new Set(visibleNodes.map((n) => n.node_id))
  visibleEdges = visibleEdges.filter(
    (e) => visibleIds.has(e.source_node_id) && visibleIds.has(e.target_node_id),
  )
  return { nodes: visibleNodes, edges: visibleEdges }
}

export function formatNeighborhoodMarkdown(node, edges, nodesById) {
  if (!node) return ''
  const lines = [
    `# ${node.entity_type} ${node.entity_id}`,
    `knowledge: ${node.knowledge_state || 'known'}`,
    '',
    '## Incident edges',
  ]
  for (const edge of edges || []) {
    const other = nodesById.get(otherNodeId(edge, node.node_id))
    const otherLabel = other
      ? `${other.entity_type} ${other.entity_id}`
      : otherNodeId(edge, node.node_id)
    lines.push(
      `- ${edge.edge_class} via ${edge.source_key} → ${otherLabel}`
      + (edge.confidence ? ` confidence=${edge.confidence}` : '')
      + (edge.observed_at ? ` observed=${edge.observed_at}` : '')
      + (edge.fetched_at ? ` fetched=${edge.fetched_at}` : ''),
    )
  }
  return lines.join('\n')
}
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd frontend && node --test src/utils/investigateGraphFilters.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphFilters.js frontend/src/utils/investigateGraphFilters.test.js
git commit -m "feat(investigate): client filters, isolate, and IOC kind parse"
```

---

### Task 5: Camera — wheel, pan, Fit, `+`/`−`, keyboard

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

**Interfaces:**
- Consumes: Task 1 `computePointCloudBounds` / `zoomAtCursor` / `computeFitView` / `DEFAULT_VIEW`
- Produces: SVG scene `translate(x y) scale(s)`; page must not scroll on wheel

This task **only** adds the camera. Click still expands until Task 6 — acceptable intermediate. Do not add pivots yet.

- [ ] **Step 1: CSS** — add to `InvestigateGraph.css` (keep existing inspector rules):

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
  min-height: var(--control-height-md, 32px);
  border: 1px solid var(--border-default, var(--border2));
  background: var(--surface-raised, var(--bg2));
  color: var(--text-primary, var(--text));
  font-family: var(--font-mono);
  cursor: pointer;
}

.investigate-svg-scene {
  transform-box: fill-box;
  transform-origin: 0 0;
}
```

- [ ] **Step 2: View state + non-passive wheel** (copy architecture — do **not** use React `onWheel`)

Imports:

```javascript
import {
  DEFAULT_VIEW,
  computeFitView,
  computePointCloudBounds,
  truncateNodeLabel,
  zoomAtCursor,
} from '../../utils/architectureGraphView.js'
```

Inside the component:

```javascript
const [view, setView] = useState(() => ({ ...DEFAULT_VIEW }))
const viewRef = useRef(view)
viewRef.current = view
const userMovedRef = useRef(false)
const dragRef = useRef(null)

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

const fitGraphToView = useCallback(() => {
  const el = canvasRef.current
  if (!el || !positions.length) return
  const bounds = computePointCloudBounds(positions, 12, 48)
  setView(computeFitView(bounds, el.clientWidth, el.clientHeight))
}, [positions])

const zoomFromButton = useCallback((factor) => {
  const el = canvasRef.current
  if (!el) return
  userMovedRef.current = true
  setView((v) => zoomAtCursor(v, el.clientWidth / 2, el.clientHeight / 2, factor))
}, [])

const onPointerDown = useCallback((e) => {
  if (e.target.closest('[data-node-id]')) return
  dragRef.current = { startX: e.clientX, startY: e.clientY, origin: view }
  e.currentTarget.setPointerCapture(e.pointerId)
}, [view])

const onPointerMove = useCallback((e) => {
  if (!dragRef.current) return
  const { startX, startY, origin } = dragRef.current
  userMovedRef.current = true
  setView({
    ...origin,
    x: origin.x + (e.clientX - startX),
    y: origin.y + (e.clientY - startY),
  })
}, [])

const onPointerUp = useCallback((e) => {
  dragRef.current = null
  if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
    e.currentTarget.releasePointerCapture(e.pointerId)
  }
}, [])

const onCanvasKeyDown = useCallback((e) => {
  if (e.target.closest('input, textarea')) return
  const el = canvasRef.current
  if (!el) return
  const w = el.clientWidth
  const h = el.clientHeight
  if (e.key === '+' || e.key === '=') {
    e.preventDefault()
    zoomFromButton(1.1)
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault()
    zoomFromButton(1 / 1.1)
  } else if (e.key === '0') {
    e.preventDefault()
    userMovedRef.current = false
    fitGraphToView()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    userMovedRef.current = true
    setView((v) => ({ ...v, x: v.x + 40 }))
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    userMovedRef.current = true
    setView((v) => ({ ...v, x: v.x - 40 }))
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    userMovedRef.current = true
    setView((v) => ({ ...v, y: v.y + 40 }))
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    userMovedRef.current = true
    setView((v) => ({ ...v, y: v.y - 40 }))
  }
}, [fitGraphToView, zoomFromButton])
```

After the force loop reaches `maxTicks`, if `!userMovedRef.current` call `fitGraphToView()`. Reset `userMovedRef` to false when `graph.root_id` changes (new resolve).

Wrap node+edge SVG in:

```jsx
<g className="investigate-svg-scene" transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
```

Canvas div: `tabIndex={0}`, `onPointerDown/Move/Up/Leave`, `onKeyDown={onCanvasKeyDown}`, `aria-label="Investigation graph canvas"`.

Overlay (inside canvas, sibling of svg):

```jsx
<div className="investigate-camera-tools">
  <button type="button" aria-label="Zoom in" onClick={() => zoomFromButton(1.1)}>+</button>
  <button type="button" aria-label="Zoom out" onClick={() => zoomFromButton(1 / 1.1)}>−</button>
  <button type="button" aria-label="Fit graph" onClick={() => { userMovedRef.current = false; fitGraphToView() }}>FIT GRAPH</button>
  <button type="button" aria-label="Reset view" onClick={() => { userMovedRef.current = false; fitGraphToView() }}>RESET VIEW</button>
</div>
```

Add `data-node-id={node.node_id}` on each node `<g>` so pan ignores node hits.

Hint copy: `Scroll to zoom · drag to pan · click to inspect · double-click to expand`.

- [ ] **Step 3: Manual smoke (this task)** — resolve a CVE; wheel zooms at cursor; page does not scroll; `+`/`−`/FIT/RESET work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/components/investigate/InvestigateGraph.css
git commit -m "feat(investigate): architecture-style wheel zoom, pan, and Fit"
```

---

### Task 6: Inspect vs expand, LOD, glyphs, session marks

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`
- Modify: `frontend/src/App.jsx` (pass `watchlist` only; actions come in Task 7)

**Interfaces:**
- Consumes: Task 4 `canExpandEntityType`, `heuristicCveIds`, `neighborIds`
- Click sets `selectedId`; double-click / Shift+Enter calls `expandNode` only if expandable

- [ ] **Step 1: Click handlers**

Remove `onClick={() => expandNode(node)}`.

```javascript
function onNodeClick(node) {
  setSelectedId((id) => (id === node.node_id ? null : node.node_id))
}

function onNodeDoubleClick(node) {
  if (!canExpandEntityType(node.entity_type)) return
  expandNode(node)
}
```

`onKeyDown` on node: Enter/Space select (toggle); Shift+Enter expand if expandable.

Click canvas background (target is the canvas, not `[data-node-id]`): `setSelectedId(null)` — only if it was not a pan (`dragRef` movement < 4px). Copy architecture: click selected deselects.

- [ ] **Step 2: LOD + glyphs**

```javascript
function hitRadius(scale) {
  return Math.min(24, Math.max(8, 12 / scale))
}

function shouldShowLabel(node, { selectedId, hoveredId, findLower, scale, rootId }) {
  if (node.node_id === rootId || node.node_id === selectedId || node.node_id === hoveredId) return true
  if (findLower && (node.label || '').toLowerCase().includes(findLower)) return true
  if (node.entity_type !== 'cve' && scale >= 1.25) return true
  return scale >= 2
}
```

Draw: CVE `circle`; IOC rotated `rect` (diamond); technique/sigma/publication `rect`; campaign simple hex `polygon`. Root radius +3. If `heuristicCveIds(graph).has(node.node_id)` use r=6.

Watchlist: if `watchlist?.getState(node.entity_id) === 'pin'` draw a 4px triangle at top of node (accent stroke). Thread: if `investigation?.isCveInThread(node.entity_id)` extra dashed circle.

Labels: `truncateNodeLabel(node.label || node.entity_id, 28)` when `shouldShowLabel`. Inverse-scale font: `fontSize={11 / Math.max(view.scale, 0.5)}` is optional; prefer CSS `.investigate-node-label { font-size: 11px }` and accept camera scale.

Neighborhood dim: if `selectedId || hoveredId`, nodes not in `neighborIds ∪ {focus} ∪ {root}` get class `investigate-node-dim` (`opacity: 0.28`). Edges not incident get `opacity: 0.2`. **Do not hide** edges (unlike architecture).

- [ ] **Step 3: Gate test** (append to an existing investigate frontend test or create `frontend/src/components/investigate/investigateCanvasGate.test.js`):

```javascript
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const src = readFileSync(new URL('./InvestigateGraph.jsx', import.meta.url), 'utf8')

describe('InvestigateGraph canvas gates', () => {
  it('does not expand on single click', () => {
    assert.doesNotMatch(src, /onClick=\{\(\) => expandNode\(node\)\}/)
    assert.match(src, /onDoubleClick/)
  })
  it('uses a non-passive wheel listener', () => {
    assert.match(src, /addEventListener\('wheel', handler, \{ passive: false \}\)/)
    assert.doesNotMatch(src, /onWheel=/)
  })
})
```

- [ ] **Step 4: Run** `cd frontend && node --test src/components/investigate/investigateCanvasGate.test.js src/utils/architectureGraphView.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/components/investigate/InvestigateGraph.css frontend/src/components/investigate/investigateCanvasGate.test.js
git commit -m "feat(investigate): inspect vs expand with LOD glyphs"
```

---

### Task 7: Inspector evidence + pivots (correct IocKind)

**Files:**
- Modify: `frontend/src/context/InvestigationContext.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/App.jsx`
- Test: `frontend/src/context/investigationIocPivotGate.test.js` (source gate)

**Interfaces:**
- `pivotToIoc(value, cveContext, indicatorType = 'ip')` writes `indicators: [{ type: kind, value }]`
- App passes `watchlist`, `onWatchlistChange`, `onOpenForgeCampaigns`, `onOpenAdvisories`

- [ ] **Step 1: Failing gate**

```javascript
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const ctx = readFileSync(new URL('./InvestigationContext.jsx', import.meta.url), 'utf8')
const graph = readFileSync(new URL('../components/investigate/InvestigateGraph.jsx', import.meta.url), 'utf8')

describe('LOOKUP LIVE kind', () => {
  it('pivotToIoc accepts indicatorType and does not hardcode only ip in the graph path', () => {
    assert.match(ctx, /indicatorType/)
    assert.match(graph, /parseIocEntityId/)
    assert.match(graph, /LOOKUP LIVE/)
  })
})
```

- [ ] **Step 2: Extend `pivotToIoc`**

Replace the `setIocPrefill` block:

```javascript
  const pivotToIoc = useCallback((value, cveContext, indicatorType = 'ip') => {
    const kind = ['ip', 'hash', 'domain', 'url'].includes(indicatorType) ? indicatorType : 'ip'
    const from = cveContext || itemsRef.current[itemsRef.current.length - 1]
    // ... existing CVE-anchor thread logic, using `value` instead of `ip` ...
    recordIocPivot(value, from)
    navigation?.setActiveTab?.('ioc')
    navigation?.setIocPrefill?.({
      value,
      indicators: [{ type: kind, value }],
      trigger: Date.now(),
    })
  }, [recordItem, recordIocPivot, navigation])
```

Keep the two-arg drawer call working (`indicatorType` defaults to `ip`).

- [ ] **Step 3: App props** (next to existing `openForgeCampaigns` ~693)

```javascript
  const openAdvisories = useCallback(() => {
    setActiveTab('atlas')
    pushContext(setSearchParams, (prev) => {
      const next = buildAppTabSearchParams(prev, 'atlas')
      next.set('view', 'advisories')
      return next
    })
  }, [setSearchParams, setActiveTab])
```

Investigate mount:

```jsx
<InvestigateGraph
  isActive={activeTab === 'investigate'}
  onOpenCve={openCveById}
  watchlist={watchlist}
  onWatchlistChange={handleWatchlistChange}
  onOpenForgeCampaigns={openForgeCampaigns}
  onOpenAdvisories={openAdvisories}
/>
```

- [ ] **Step 4: Inspector actions** in `InvestigateGraph.jsx`

```javascript
import { copyToClipboard } from '../../utils/report.js'
import Checkbox from '../ui/Checkbox.jsx'
import {
  canExpandEntityType,
  parseIocEntityId,
  incidentEdges,
  otherNodeId,
  formatNeighborhoodMarkdown,
  relatedCveCount,
  visibleGraph,
  neighborIds,
  heuristicCveIds,
  DEFAULT_EDGE_CLASSES,
  EDGE_CLASS_CHIPS,
} from '../../utils/investigateGraphFilters.js'
```

Incident list from `incidentEdges(graph, selectedId)` — show `edge_class`, `source_key`, timestamps; clicking neighbor id `setSelectedId`.

Buttons (only if they apply):

```jsx
{canExpandEntityType(selected.entity_type) && (
  <button type="button" onClick={() => expandNode(selected)}>EXPAND</button>
)}
{selected.entity_type === 'cve' && onOpenCve && (
  <button type="button" onClick={() => onOpenCve(selected.entity_id)}>OPEN CVE</button>
)}
{selected.entity_type === 'ioc' && investigation && (
  <button
    type="button"
    onClick={() => {
      const parsed = parseIocEntityId(selected.entity_id, selected.label)
      investigation.pivotToIoc(parsed.value, null, parsed.type)
    }}
  >
    LOOKUP LIVE
  </button>
)}
{selected.entity_type === 'technique' && (
  <button type="button" onClick={() => investigation.pivotToTechnique(selected.entity_id, selected.label)}>
    OPEN IN FORGE
  </button>
)}
{selected.entity_type === 'campaign' && onOpenForgeCampaigns && (
  <button type="button" onClick={onOpenForgeCampaigns}>OPEN CAMPAIGNS</button>
)}
{selected.entity_type === 'publication' && onOpenAdvisories && (
  <button type="button" onClick={onOpenAdvisories}>OPEN ADVISORIES</button>
)}
{selected.entity_type === 'cve' && onWatchlistChange && (
  <button type="button" onClick={() => onWatchlistChange(selected.entity_id, 'pin')}>
    {watchlist?.getState(selected.entity_id) === 'pin' ? 'UNPIN WATCHLIST' : 'PIN WATCHLIST'}
  </button>
)}
<button type="button" onClick={() => pinNode(selected)}>PIN THREAD</button>
<button
  type="button"
  onClick={() => visible.nodes.filter((n) => n.entity_type === 'cve').forEach((n) => investigation.ensureCveInThread(n.entity_id))}
>
  PIN VISIBLE CVEs
</button>
<button type="button" onClick={() => copyToClipboard(selected.entity_id)}>COPY ID</button>
<button
  type="button"
  onClick={() => copyToClipboard(formatNeighborhoodMarkdown(selected, incidentEdges(graph, selected.node_id), positionById))}
>
  COPY NEIGHBORHOOD
</button>
```

`positionById` may be layout-only — build `nodesById` from `graph.nodes` for markdown.

Do **not** call `pivotToCampaign` (needs `members` not on GraphNode).

- [ ] **Step 5: Run gates**

`cd frontend && node --test src/context/investigationIocPivotGate.test.js src/components/investigate/investigateCanvasGate.test.js`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/context/InvestigationContext.jsx frontend/src/context/investigationIocPivotGate.test.js frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/App.jsx
git commit -m "feat(investigate): evidence inspector and stored-intel pivots"
```

---

### Task 8: Density chrome — related CVEs, type, edge class, isolate, find, semantic, Load more

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

**Interfaces:**
- Layout uses `visibleGraph(...)` output, **not** raw `graph.nodes` for paint. Force layout seeds from visible nodes so hidden related CVEs do not occupy space. Keep merge state in `graph` (full).

- [ ] **Step 1: State**

```javascript
const [showRelatedCves, setShowRelatedCves] = useState(true)
const [entityType, setEntityType] = useState('all')
const [edgeClasses, setEdgeClasses] = useState(() => new Set(DEFAULT_EDGE_CLASSES))
const [isolate, setIsolate] = useState(false)
const [findText, setFindText] = useState('')
const [includeSemantic, setIncludeSemantic] = useState(false)
```

```javascript
const visible = useMemo(
  () => visibleGraph(graph, {
    showRelatedCves,
    entityType,
    edgeClasses,
    isolateNodeId: isolate ? (selectedId || graph.root_id) : null,
  }),
  [graph, showRelatedCves, entityType, edgeClasses, isolate, selectedId],
)
```

Force `useEffect` and Fit must use `visible.nodes` / `visible.edges`. Positions: seed from visible; drop coords for hidden ids.

On `showRelatedCves` / `entityType` / `edgeClasses` / `isolate` change, call `fitGraphToView()` (architecture refits on cluster change).

- [ ] **Step 2: Toolbar chrome** (under search)

Radix Checkbox:

```jsx
<Checkbox
  checked={showRelatedCves}
  onCheckedChange={(v) => setShowRelatedCves(v === true)}
  label={`Related CVEs (${relatedCveCount(graph)})`}
/>
<Checkbox
  checked={isolate}
  onCheckedChange={(v) => setIsolate(v === true)}
  label="Isolate"
/>
<Checkbox
  checked={includeSemantic}
  onCheckedChange={async (v) => {
    const on = v === true
    setIncludeSemantic(on)
    setEdgeClasses((prev) => {
      const next = new Set(prev)
      if (on) next.add('semantic')
      else next.delete('semantic')
      return next
    })
    if (on && graph.root_id) {
      const root = graph.nodes.find((n) => n.node_id === graph.root_id)
      if (root) {
        const page = await fetchInvestigationRelationships(root.entity_type, root.entity_id, {
          include_semantic: true,
        })
        setGraph((prev) => mergeGraphPage(prev, page))
      }
    }
  }}
  label="Semantic"
/>
```

Type chips: ALL, cve, ioc, technique, campaign, publication — `role="tablist"` like `sa-type-tabs`.

Edge-class chips: toggle membership in `edgeClasses` (FACT label for `direct_fact`). Semantic chip disabled until Semantic checkbox is on (or toggling it turns Semantic on).

Find:

```jsx
<input
  aria-label="Find in graph"
  value={findText}
  onChange={(e) => setFindText(e.target.value)}
  onKeyDown={(e) => {
    if (e.key !== 'Enter') return
    const q = findText.trim().toLowerCase()
    const match = visible.nodes.find((n) =>
      (n.label || n.entity_id || '').toLowerCase().includes(q)
    )
    if (!match) return
    const pos = positions.find((p) => p.node_id === match.node_id)
    const el = canvasRef.current
    if (!pos || !el) return
    userMovedRef.current = true
    setView((v) => ({
      ...v,
      x: el.clientWidth / 2 - pos.x * v.scale,
      y: el.clientHeight / 2 - pos.y * v.scale,
    }))
    setSelectedId(match.node_id)
  }}
/>
```

Highlight find matches with class `investigate-node-match` (accent stroke). Do **not** hide non-matches.

LOAD MORE:

```jsx
{selected && graph.cursorsByNodeId?.[selected.node_id] && !graph.capped && (
  <button
    type="button"
    onClick={() => expandNode(selected, { cursor: graph.cursorsByNodeId[selected.node_id] })}
  >
    LOAD MORE
  </button>
)}
```

Change `expandNode` to pass through params:

```javascript
const page = await fetchInvestigationRelationships(node.entity_type, node.entity_id, {
  ...(params || {}),
  ...(includeSemantic ? { include_semantic: true } : {}),
})
```

Honesty banner: if `truncated` and a cursor exists, mention LOAD MORE.

- [ ] **Step 3: Filter unit tests already exist (Task 4).** Run:

`cd frontend && node --test src/utils/investigateGraphFilters.test.js src/utils/investigateGraphMerge.test.js`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/components/investigate/InvestigateGraph.css
git commit -m "feat(investigate): density filters, isolate, find, and Load more"
```

---

### Task 9: Deep-link `?tab=investigate&q=`

**Files:**
- Modify: `frontend/src/utils/shellUrlState.js`
- Modify: `frontend/src/utils/shellUrlState.test.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`

- [ ] **Step 1: Test**

```javascript
  it('drops investigate q when leaving the investigate tab', () => {
    const prev = new URLSearchParams('tab=investigate&q=CVE-2024-9100')
    const next = buildAppTabSearchParams(prev, 'feed')
    assert.equal(next.get('tab'), 'feed')
    assert.equal(next.get('q'), null)
  })

  it('keeps investigate q when staying on investigate', () => {
    const prev = new URLSearchParams('tab=investigate&q=CVE-2024-9100')
    const next = buildAppTabSearchParams(prev, 'investigate')
    assert.equal(next.get('q'), 'CVE-2024-9100')
  })
```

- [ ] **Step 2: Run — expect FAIL**

`cd frontend && node --test src/utils/shellUrlState.test.js`

- [ ] **Step 3: Implement**

In `buildAppTabSearchParams`, after setting `tab`:

```javascript
  if (nextTab !== 'investigate') next.delete('q')
```

App: pass `initialQuery={activeTab === 'investigate' ? (searchParams.get('q') || '') : ''}`.

`InvestigateGraph`: if `initialQuery` is non-empty and differs from last consumed ref, `setQuery` + `runSearch`. On successful resolve, App callback or graph `onResolvedQuery` so App can `pushContext` `q=` to the resolved string.

Prefer: InvestigateGraph calls optional `onQueryResolved(q)`:

```javascript
onQueryResolved?.(q)
```

In App:

```javascript
onQueryResolved={(q) => {
  pushContext(setSearchParams, (prev) => {
    const next = buildAppTabSearchParams(prev, 'investigate')
    if (q) next.set('q', q)
    else next.delete('q')
    return next
  })
}}
```

- [ ] **Step 4: Run** `cd frontend && node --test src/utils/shellUrlState.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/shellUrlState.js frontend/src/utils/shellUrlState.test.js frontend/src/App.jsx frontend/src/components/investigate/InvestigateGraph.jsx
git commit -m "feat(investigate): deep-link search via tab=investigate&q="
```

---

### Task 10: Docs

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` (Investigation graph row)
- Modify: `docs/USE.md` (INVESTIGATE row + short how-to)

- [ ] **Step 1:** PRODUCT_STATUS — replace “click-to-expand” as the primary gesture with: pan/zoom (architecture camera, non-passive wheel + `+`/`−`/FIT/RESET), click inspect / double-click expand, evidence inspector, related-CVE / type / edge-class / isolate filters, Load more, LOOKUP LIVE (correct IocKind), `q=` deep-link. State GraphNode still has no KEV/EPSS.

- [ ] **Step 2:** USE.md — `Scroll to zoom · drag to pan · click to inspect · double-click to expand`. Mention FIT GRAPH for laptop users without a wheel.

- [ ] **Step 3: Commit**

```bash
git add docs/PRODUCT_STATUS.md docs/USE.md
git commit -m "docs: INVESTIGATE map navigation and stored-intel pivots"
```

---

### Task 11: Verify

- [ ] `cd frontend && npm run test:unit` — PASS
- [ ] `cd frontend && npm run build` — PASS
- [ ] `./scripts/verify-local.sh` — green

Manual (when UI is up):

1. Resolve a busy CVE. Auto-Fit fills canvas.
2. Wheel: zoom at cursor; **page behind does not scroll**.
3. `+`/`−`/FIT GRAPH/RESET VIEW without a wheel.
4. Click spoke: inspector shows `source_key`; node count unchanged.
5. LOOKUP LIVE on a **hash** IOC opens IOC LOOKUP with type hash (not ip).
6. OPEN CVE opens drawer (KEV/EPSS still there).
7. Uncheck Related CVEs: star thins. Isolate: only 1-hop remains.
8. LOAD MORE if truncated.
9. Sigma node has no EXPAND.

---

## Spec coverage

| Spec | Task |
|------|------|
| Wheel zoom, page must not scroll | 5 (reuse Task 1 `zoomAtCursor`) |
| `+`/`−`/FIT/RESET + keyboard | 5 |
| Layout unclamped | 2 |
| Inspect vs expand + LOD + glyphs + session marks | 6 |
| Inspector evidence + COPY | 4, 7 |
| LOOKUP LIVE IocKind | 4, 7 |
| Campaigns / advisories / watchlist | 7 |
| Related CVE + type + edge class + isolate + find | 4, 8 |
| Semantic query flag | 3, 8 |
| Load more | 3, 8 |
| Deep-link q= | 9 |
| Docs | 10 |
| No forked camera / no graph lib / no GraphNode extras | Task 1 + global |

## Placeholder scan

No TBD. Exact files, tests, and code are in each task. `handleWatchlistChange` already exists in `App.jsx`. `openForgeCampaigns` already exists; `openAdvisories` is added in Task 7.

## Deliberately not in this plan

Server-side related-CVE ranking; minimap; PNG export; graph DB; email/mutex nodes; KEV/EPSS on GraphNode; sigma expand; node drag; live enrichment on click; architecture hide-edges-until-focus.
