# INVESTIGATE canvas UX — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the INVESTIGATE tab a readable, pannable, zoomable map of stored hops — inspect without accidental expand, Fit the neighborhood to the canvas, and stop related-CVE stars from becoming an illegible clump.

**Architecture:** Keep the frozen GraphPage API and custom SVG. Split **world layout** (`investigateForceLayout.js`) from **view camera** (`investigateCamera.js`). `InvestigateGraph.jsx` applies `translate(tx,ty) scale(k)` to a `<g>`, changes click vs expand, LOD labels, type glyphs, related-CVE filter, and Load more via `next_cursor` stored in `mergeGraphPage`.

**Tech Stack:** React/Vite, existing SVG canvas, Node test runner (`node:test`) for frontend unit tests, CSS tokens. No new graph libraries.

## Global Constraints

- Semantic tokens only (`--surface-*`, `--text-*`, `--accent-*`, `--space-*`, `--font-size-*`) — no raw hex in components.
- GraphPage JSON unchanged (no x/y from API, no graph DB, no live enrichment on expand).
- Client caps stay 200 nodes / 300 edges; root preserved.
- `prefers-reduced-motion` / `data-motion`: camera jumps, force ≤ 12 ticks.
- Overlay controls `aria-label` + hit target ≥ 24px.
- Merge gate: `cd frontend && npm run test:unit` and `npm run build`; `./scripts/verify-local.sh` before merge.

## File map

| File | Responsibility |
|------|----------------|
| Create: `frontend/src/utils/investigateCamera.js` | Zoom/pan/fit/world↔screen math |
| Create: `frontend/src/utils/investigateCamera.test.js` | Camera unit tests |
| Create: `frontend/src/utils/investigateGraphFilters.js` | Related-CVE visibility filter |
| Create: `frontend/src/utils/investigateGraphFilters.test.js` | Filter unit tests |
| Modify: `frontend/src/utils/investigateForceLayout.js` | Type-ring seed, scalable springs, grid repulsion, no viewport clamp |
| Modify: `frontend/src/utils/investigateForceLayout.test.js` | n>80 repulsion + finite coords |
| Modify: `frontend/src/utils/investigateGraphMerge.js` | `next_cursor` + `cursorsByNodeId` |
| Modify: `frontend/src/utils/investigateGraphMerge.test.js` | Cursor sticky merge |
| Modify: `frontend/src/components/investigate/InvestigateGraph.jsx` | Camera, gestures, LOD, glyphs, Load more |
| Modify: `frontend/src/components/investigate/InvestigateGraph.css` | Overlay chrome, glyphs |
| Modify: `docs/PRODUCT_STATUS.md` | Canvas UX shipped notes |
| Modify: `docs/USE.md` | Investigate gestures (one line) |

---

### Task 1: Camera math

**Files:**
- Create: `frontend/src/utils/investigateCamera.js`
- Test: `frontend/src/utils/investigateCamera.test.js`

**Interfaces:**
- Produces: `ZOOM_MIN`, `ZOOM_MAX`, `createCamera()`, `clampZoom(k)`, `zoomAt(camera, worldX, worldY, factor)`, `panBy(camera, dx, dy)`, `screenToWorld(camera, sx, sy)`, `worldToScreen(camera, x, y)`, `boundsOf(positions)`, `fitBounds(bounds, width, height, padding)`

- [ ] **Step 1: Write the failing tests**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  ZOOM_MIN,
  ZOOM_MAX,
  createCamera,
  clampZoom,
  zoomAt,
  panBy,
  screenToWorld,
  worldToScreen,
  boundsOf,
  fitBounds,
} from './investigateCamera.js'

describe('investigateCamera', () => {
  it('clamps zoom', () => {
    assert.equal(clampZoom(0.01), ZOOM_MIN)
    assert.equal(clampZoom(99), ZOOM_MAX)
  })

  it('keeps the world point under the cursor stable when zooming', () => {
    const camera = { k: 1, tx: 10, ty: 20 }
    const world = { x: 100, y: 50 }
    const before = worldToScreen(camera, world.x, world.y)
    const next = zoomAt(camera, world.x, world.y, 2)
    const after = worldToScreen(next, world.x, world.y)
    assert.equal(Math.round(after.x), Math.round(before.x))
    assert.equal(Math.round(after.y), Math.round(before.y))
    assert.ok(next.k > camera.k)
  })

  it('panBy shifts screen translation', () => {
    const next = panBy(createCamera(), 15, -8)
    assert.equal(next.tx, 15)
    assert.equal(next.ty, -8)
    assert.equal(next.k, 1)
  })

  it('screenToWorld inverts worldToScreen', () => {
    const camera = { k: 1.5, tx: 40, ty: -12 }
    const world = screenToWorld(camera, 100, 80)
    const screen = worldToScreen(camera, world.x, world.y)
    assert.equal(Math.round(screen.x), 100)
    assert.equal(Math.round(screen.y), 80)
  })

  it('fitBounds places the bbox center at the viewport center', () => {
    const positions = [
      { x: 0, y: 0 },
      { x: 200, y: 100 },
    ]
    const bounds = boundsOf(positions)
    const camera = fitBounds(bounds, 800, 600, 40)
    const mid = worldToScreen(camera, 100, 50)
    assert.ok(Math.abs(mid.x - 400) < 2)
    assert.ok(Math.abs(mid.y - 300) < 2)
    assert.ok(camera.k >= ZOOM_MIN && camera.k <= ZOOM_MAX)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/utils/investigateCamera.test.js`

Expected: FAIL (module not found)

- [ ] **Step 3: Write implementation**

```javascript
/** View camera: screen = world * k + (tx, ty). Layout stays in world space. */

export const ZOOM_MIN = 0.25
export const ZOOM_MAX = 4

export function createCamera() {
  return { k: 1, tx: 0, ty: 0 }
}

export function clampZoom(k) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, k))
}

export function worldToScreen(camera, x, y) {
  return {
    x: x * camera.k + camera.tx,
    y: y * camera.k + camera.ty,
  }
}

export function screenToWorld(camera, sx, sy) {
  return {
    x: (sx - camera.tx) / camera.k,
    y: (sy - camera.ty) / camera.k,
  }
}

export function panBy(camera, dx, dy) {
  return { k: camera.k, tx: camera.tx + dx, ty: camera.ty + dy }
}

export function zoomAt(camera, worldX, worldY, factor) {
  const k2 = clampZoom(camera.k * factor)
  const screen = worldToScreen(camera, worldX, worldY)
  return {
    k: k2,
    tx: screen.x - worldX * k2,
    ty: screen.y - worldY * k2,
  }
}

export function boundsOf(positions) {
  if (!positions.length) {
    return { minX: 0, minY: 0, maxX: 1, maxY: 1 }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of positions) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) continue
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x)
    maxY = Math.max(maxY, node.y)
  }
  if (!Number.isFinite(minX)) {
    return { minX: 0, minY: 0, maxX: 1, maxY: 1 }
  }
  return { minX, minY, maxX, maxY }
}

export function fitBounds(bounds, width, height, padding = 48) {
  const bw = Math.max(bounds.maxX - bounds.minX, 1)
  const bh = Math.max(bounds.maxY - bounds.minY, 1)
  const innerW = Math.max(width - padding * 2, 1)
  const innerH = Math.max(height - padding * 2, 1)
  const k = clampZoom(Math.min(innerW / bw, innerH / bh))
  const cx = (bounds.minX + bounds.maxX) / 2
  const cy = (bounds.minY + bounds.maxY) / 2
  return {
    k,
    tx: width / 2 - cx * k,
    ty: height / 2 - cy * k,
  }
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd frontend && node --test src/utils/investigateCamera.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateCamera.js frontend/src/utils/investigateCamera.test.js
git commit -m "feat(investigate): add pan/zoom/fit camera math"
```

---

### Task 2: Force layout — no clamp, repulsion at n>80, type-ring seed

**Files:**
- Modify: `frontend/src/utils/investigateForceLayout.js`
- Test: `frontend/src/utils/investigateForceLayout.test.js`

**Interfaces:**
- Consumes: `nodes[].entity_type`, optional `nodes[].node_id`, `edges[].source_key`
- Produces: same `seedPositions(nodes, width, height, prior)` / `stepForce(positions, edges, width, height)` signatures. World coords may leave the viewport; camera (Task 4) frames them.

- [ ] **Step 1: Extend tests**

Add to `investigateForceLayout.test.js`:

```javascript
  it('keeps repulsion active above 80 nodes (positions spread)', () => {
    const nodes = Array.from({ length: 90 }, (_, i) => ({
      node_id: `n${i}`,
      entity_type: i === 0 ? 'cve' : 'cve',
      label: `n${i}`,
    }))
    const edges = nodes.slice(1).map((node) => ({
      source_node_id: 'n0',
      target_node_id: node.node_id,
    }))
    let positions = seedPositions(nodes, 800, 600)
    for (let i = 0; i < 40; i += 1) {
      positions = stepForce(positions, edges, 800, 600)
    }
    const xs = positions.map((p) => p.x)
    const span = Math.max(...xs) - Math.min(...xs)
    assert.ok(span > 200, `expected spread, got ${span}`)
  })

  it('does not clamp nodes into a 36px viewport pad', () => {
    const nodes = [
      { node_id: 'a', entity_type: 'cve' },
      { node_id: 'b', entity_type: 'ioc' },
    ]
    let positions = seedPositions(nodes, 400, 400)
    positions[0].x = -50
    positions[0].y = -50
    positions[0].vx = 0
    positions[0].vy = 0
    const next = stepForce(positions, [], 400, 400)
    assert.ok(next[0].x < 36 || next[0].x > 364 || next[0].x === -50 || next[0].x < 0)
  })
```

The second assertion should be: after one tick **without** pad clamp, a node at (-50,-50) is **not** forced to x=36. Implement so `applyCenterAndBounds` no longer `Math.min(width-pad, Math.max(pad, node.x))`. Soft finite clamp at ±8000 only.

- [ ] **Step 2: Run tests — expect FAIL** on spread / clamp.

Run: `cd frontend && node --test src/utils/investigateForceLayout.test.js`

- [ ] **Step 3: Implement layout**

Replace constants and helpers in `investigateForceLayout.js`:

```javascript
const REPULSE = 2800
const SPRING = 0.035
const SPRING_LENGTH_MIN = 160
const SPRING_LENGTH_MAX = 420
const ROOT_CENTER = 0.008
const DAMPING = 0.86
const WORLD_LIMIT = 8000
const GRID_REPULSE_MAX = 24

function springLength(count) {
  const scaled = SPRING_LENGTH_MIN + Math.sqrt(Math.max(count, 1)) * 18
  return Math.min(SPRING_LENGTH_MAX, scaled)
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
  nodes.forEach((node, index) => {
    const key = node.entity_type || 'other'
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push({ node, index })
  })
  return nodes.map((node) => {
    const kept = prior.get(node.node_id)
    if (kept && Number.isFinite(kept.x) && Number.isFinite(kept.y)) {
      return { ...node, x: kept.x, y: kept.y, vx: kept.vx || 0, vy: kept.vy || 0 }
    }
    if (node.node_id === root) {
      return { ...node, x: cx, y: cy, vx: 0, vy: 0 }
    }
    const group = buckets.get(node.entity_type || 'other') || []
    const gi = group.findIndex((item) => item.node.node_id === node.node_id)
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
            dx = ((i + j) % 5) - 2
            dy = ((i * 3 + j) % 5) - 2
            distSq = Math.max(dx * dx + dy * dy, 1)
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
    const fx = (dx / dist) * stretch * SPRING
    const fy = (dy / dist) * stretch * SPRING
    a.vx += fx
    a.vy += fy
    b.vx -= fx
    b.vy -= fy
  }
}

function applyRootCenterAndDamping(next, width, height) {
  const cx = width / 2
  const cy = height / 2
  for (const node of next) {
    const isRoot = node.node_id && node.node_id === next[0]?.node_id
    if (isRoot) {
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
}

export function stepForce(positions, edges, width, height) {
  const next = positions.map((node) => ({ ...node }))
  const byId = new Map(next.map((node) => [node.node_id, node]))
  applyRepulsion(next)
  applySprings(next, edges, byId)
  applyRootCenterAndDamping(next, width, height)
  return next
}
```

**Root identity:** do not use `next[0]` as root. Pass `rootId` into `stepForce` as a 5th argument defaulting to `positions[0]?.node_id`, and have `InvestigateGraph` pass `graph.root_id`. Update the existing finite-coords test to still pass (it can omit `rootId`).

```javascript
export function stepForce(positions, edges, width, height, rootId = null) {
  const next = positions.map((node) => ({ ...node }))
  const byId = new Map(next.map((node) => [node.node_id, node]))
  const root = rootId || next[0]?.node_id
  applyRepulsion(next)
  applySprings(next, edges, byId)
  applyRootCenterAndDamping(next, width, height, root)
  return next
}
```

And `applyRootCenterAndDamping(..., rootId)` uses `node.node_id === rootId`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd frontend && node --test src/utils/investigateForceLayout.test.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateForceLayout.js frontend/src/utils/investigateForceLayout.test.js
git commit -m "fix(investigate): spread force layout without viewport clamp"
```

---

### Task 3: Persist `next_cursor` on merge

**Files:**
- Modify: `frontend/src/utils/investigateGraphMerge.js`
- Test: `frontend/src/utils/investigateGraphMerge.test.js`

**Interfaces:**
- Produces: graph state fields `next_cursor`, `cursorsByNodeId` (map node_id → cursor string | null)

- [ ] **Step 1: Write failing test** (append to merge describe)

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
    assert.equal(first.next_cursor, 'abc')
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
    assert.equal(second.next_cursor, null)
  })
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && node --test src/utils/investigateGraphMerge.test.js`

- [ ] **Step 3: Implement**

In `emptyGraphState()` add `next_cursor: null, cursorsByNodeId: {}`.

In `mergeGraphPage` return:

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

When `trimmed.capped` is true, still store the cursor (Load more is hidden in UI when capped — Task 4).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphMerge.js frontend/src/utils/investigateGraphMerge.test.js
git commit -m "feat(investigate): keep relationship next_cursor per node"
```

---

### Task 4: Related-CVE filter helper

**Files:**
- Create: `frontend/src/utils/investigateGraphFilters.js`
- Test: `frontend/src/utils/investigateGraphFilters.test.js`

**Interfaces:**
- Produces: `visibleGraph(graph, { showRelatedCves: boolean })` → `{ nodes, edges }`

- [ ] **Step 1: Failing tests**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { visibleGraph } from './investigateGraphFilters.js'

const root = { node_id: 'cve:ROOT', entity_type: 'cve', entity_id: 'ROOT', label: 'ROOT' }
const ioc = { node_id: 'ioc:ip:1.1.1.1', entity_type: 'ioc', entity_id: 'ip:1.1.1.1', label: '1.1.1.1' }
const rel = { node_id: 'cve:REL', entity_type: 'cve', entity_id: 'REL', label: 'REL' }

const graph = {
  root_id: 'cve:ROOT',
  nodes: [root, ioc, rel],
  edges: [
    { edge_id: 'e-ioc', source_node_id: 'cve:ROOT', target_node_id: 'ioc:ip:1.1.1.1', source_key: 'otx', edge_class: 'reported' },
    { edge_id: 'e-rel', source_node_id: 'cve:ROOT', target_node_id: 'cve:REL', source_key: 'related_cve_heuristic', edge_class: 'derived' },
  ],
}

describe('visibleGraph', () => {
  it('keeps related CVEs when enabled', () => {
    const out = visibleGraph(graph, { showRelatedCves: true })
    assert.equal(out.nodes.length, 3)
    assert.equal(out.edges.length, 2)
  })

  it('hides nodes only reached by related_cve_heuristic', () => {
    const out = visibleGraph(graph, { showRelatedCves: false })
    assert.deepEqual(out.nodes.map((n) => n.node_id).sort(), ['cve:ROOT', 'ioc:ip:1.1.1.1'])
    assert.equal(out.edges.length, 1)
  })

  it('keeps a CVE that also has a non-heuristic edge', () => {
    const extra = {
      ...graph,
      edges: [
        ...graph.edges,
        { edge_id: 'e-otx', source_node_id: 'cve:ROOT', target_node_id: 'cve:REL', source_key: 'otx', edge_class: 'reported' },
      ],
    }
    const out = visibleGraph(extra, { showRelatedCves: false })
    assert.ok(out.nodes.some((n) => n.node_id === 'cve:REL'))
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```javascript
export function visibleGraph(graph, { showRelatedCves = true } = {}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  if (showRelatedCves) return { nodes, edges }

  const justified = new Set()
  if (graph.root_id) justified.add(graph.root_id)
  for (const edge of edges) {
    if (edge.source_key === 'related_cve_heuristic') continue
    justified.add(edge.source_node_id)
    justified.add(edge.target_node_id)
  }
  const visibleNodes = nodes.filter((node) => justified.has(node.node_id))
  const ids = new Set(visibleNodes.map((node) => node.node_id))
  const visibleEdges = edges.filter(
    (edge) => ids.has(edge.source_node_id) && ids.has(edge.target_node_id)
      && edge.source_key !== 'related_cve_heuristic',
  )
  return { nodes: visibleNodes, edges: visibleEdges }
}

export function relatedCveCount(graph) {
  return (graph.edges || []).filter((edge) => edge.source_key === 'related_cve_heuristic').length
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/investigateGraphFilters.js frontend/src/utils/investigateGraphFilters.test.js
git commit -m "feat(investigate): filter heuristic related-CVE hops"
```

---

### Task 5: Wire camera, gestures, LOD, glyphs, Load more in the canvas

**Files:**
- Modify: `frontend/src/components/investigate/InvestigateGraph.jsx`
- Modify: `frontend/src/components/investigate/InvestigateGraph.css`

**Interfaces:**
- Consumes: Task 1 camera, Task 2 `stepForce(..., rootId)`, Task 3 cursors, Task 4 `visibleGraph` / `relatedCveCount`
- Produces: analyst-visible canvas behavior per spec §1–8

This is the largest task; keep it to one PR commit after unit tests from 1–4 are green.

- [ ] **Step 1: Camera state + SVG group**

In `InvestigateGraph.jsx`:

```javascript
import {
  createCamera,
  fitBounds,
  boundsOf,
  panBy,
  zoomAt,
  screenToWorld,
  ZOOM_MIN,
  ZOOM_MAX,
} from '../../utils/investigateCamera.js'
import { visibleGraph, relatedCveCount } from '../../utils/investigateGraphFilters.js'

const [camera, setCamera] = useState(createCamera)
const [showRelatedCves, setShowRelatedCves] = useState(true)
const cameraRef = useRef(camera)
cameraRef.current = camera

const view = useMemo(
  () => visibleGraph(graph, { showRelatedCves }),
  [graph, showRelatedCves],
)
```

Force loop and seeds must use `view.nodes` / `view.edges`. Pass `graph.root_id` into `stepForce`.

After the force effect, when `ticks` hits `maxTicks`, call Fit **once** if the user has not panned/zoomed (`userMovedCameraRef`):

```javascript
if (ticks === maxTicks && !userMovedCameraRef.current) {
  const { width, height } = sizeRef.current
  setCamera(fitBounds(boundsOf(positionsRef.current), width, height, 48))
}
```

SVG:

```jsx
<svg
  className="investigate-svg"
  width="100%"
  height="100%"
  role="img"
  tabIndex={0}
  aria-label={selected
    ? `Investigation graph, selected ${selected.entity_type} ${selected.entity_id}`
    : 'Investigation relationship graph'}
  onWheel={onWheel}
  onPointerDown={onPointerDown}
  onPointerMove={onPointerMove}
  onPointerUp={onPointerUp}
  onKeyDown={onCanvasKey}
>
  <g transform={`translate(${camera.tx} ${camera.ty}) scale(${camera.k})`}>
    {/* lines + nodes */}
  </g>
</svg>
```

- [ ] **Step 2: Pointer handlers**

```javascript
const dragRef = useRef(null) // { mode: 'pan'|'node', id, lastX, lastY }

function clientToSvg(event) {
  const el = canvasRef.current
  const rect = el.getBoundingClientRect()
  return { sx: event.clientX - rect.left, sy: event.clientY - rect.top }
}

function onWheel(event) {
  event.preventDefault()
  userMovedCameraRef.current = true
  const { sx, sy } = clientToSvg(event)
  const world = screenToWorld(cameraRef.current, sx, sy)
  const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15
  setCamera(zoomAt(cameraRef.current, world.x, world.y, factor))
}

function onPointerDown(event) {
  if (event.button !== 0) return
  const target = event.target
  const nodeId = target.closest?.('[data-node-id]')?.getAttribute('data-node-id')
  const { sx, sy } = clientToSvg(event)
  if (nodeId) {
    dragRef.current = { mode: 'node', id: nodeId, lastX: sx, lastY: sy, moved: false }
  } else {
    dragRef.current = { mode: 'pan', lastX: sx, lastY: sy }
    userMovedCameraRef.current = true
  }
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function onPointerMove(event) {
  const drag = dragRef.current
  if (!drag) return
  const { sx, sy } = clientToSvg(event)
  const dx = sx - drag.lastX
  const dy = sy - drag.lastY
  if (drag.mode === 'pan') {
    setCamera((c) => panBy(c, dx, dy))
  } else if (Math.hypot(dx, dy) > 3) {
    drag.moved = true
    const worldDelta = { x: dx / cameraRef.current.k, y: dy / cameraRef.current.k }
    setPositions((prev) => prev.map((n) => (
      n.node_id === drag.id
        ? { ...n, x: n.x + worldDelta.x, y: n.y + worldDelta.y, vx: 0, vy: 0 }
        : n
    )))
  }
  drag.lastX = sx
  drag.lastY = sy
}
```

On pointer up: if `mode==='node'` and `!moved`, **select** (`setSelectedId`); do **not** expand. Double-click on `[data-node-id]` calls `expandNode`.

```javascript
function onNodeClick(node, event) {
  event.stopPropagation()
  setSelectedId(node.node_id)
}

function onNodeDoubleClick(node, event) {
  event.stopPropagation()
  expandNode(node)
}
```

Remove `onClick={() => expandNode(node)}`. Space/Enter select; Shift+Enter expand.

- [ ] **Step 3: Overlay controls + related toggle + Load more**

Inside `.investigate-canvas` (not stealing grid columns):

```jsx
<div className="investigate-camera-tools" role="toolbar" aria-label="Graph camera">
  <button type="button" aria-label="Zoom out" onClick={() => {
    userMovedCameraRef.current = true
    const { width, height } = sizeRef.current
    const world = screenToWorld(camera, width / 2, height / 2)
    setCamera(zoomAt(camera, world.x, world.y, 1 / 1.15))
  }}>−</button>
  <button type="button" aria-label="Zoom in" onClick={() => { /* factor 1.15 */ }}>+</button>
  <button type="button" aria-label="Fit graph" onClick={() => {
    setCamera(fitBounds(boundsOf(positions), sizeRef.current.width, sizeRef.current.height, 48))
  }}>FIT</button>
  <button type="button" aria-label="Reset camera" onClick={() => {
    userMovedCameraRef.current = false
    setCamera(createCamera())
  }}>RESET</button>
</div>
```

Inspector:

```jsx
<label className="investigate-toggle">
  <input
    type="checkbox"
    checked={showRelatedCves}
    onChange={(e) => setShowRelatedCves(e.target.checked)}
  />
  Related CVEs ({relatedCveCount(graph)})
</label>
```

Use Radix `Checkbox` from `frontend/src/components/ui` (CONTRIBUTOR_RULES: no native checkbox). Label text remains `Related CVEs (N)`.

Honesty + Load more:

```javascript
const loadCursor = selectedId
  ? graph.cursorsByNodeId?.[selectedId]
  : graph.cursorsByNodeId?.[graph.root_id]
const canLoadMore = Boolean(graph.truncated && loadCursor && !graph.capped)

async function loadMore() {
  const node = graph.nodes.find((n) => n.node_id === (selectedId || graph.root_id))
  if (!node || !loadCursor) return
  const page = await fetchInvestigationRelationships(node.entity_type, node.entity_id, {
    cursor: loadCursor,
  })
  setGraph((prev) => mergeGraphPage(prev, page))
}
```

Hint copy change:

`Click a node to inspect. Double-click or EXPAND to pivot. Scroll to zoom, drag empty canvas to pan.`

- [ ] **Step 4: LOD labels + hit radius + glyphs**

```javascript
function showLabel(node, cameraK, selectedId, hoverId, rootId) {
  if (node.node_id === selectedId || node.node_id === hoverId || node.node_id === rootId) {
    return true
  }
  if (cameraK >= 2) return true
  if (cameraK >= 1.25 && node.entity_type !== 'cve') return true
  return false
}

const hitR = Math.min(24, Math.max(8, 12 / camera.k))
```

Render type glyphs: `cve` circle; `ioc` diamond (`<rect transform=rotate(45)>`); `technique` / `sigma_rule` / `publication` square; `campaign` hexagon polyline. Root circle `r={12}`; related-cve-only nodes `r={6}` (detect via edge `source_key` map).

- [ ] **Step 5: CSS overlay**

```css
.investigate-canvas {
  overflow: hidden;
  touch-action: none;
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

.investigate-svg:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (prefers-reduced-motion: reduce) {
  .investigate-svg g {
    transition: none;
  }
}
```

Hero: reduce `.investigate-hero-copy` so the stage `flex: 1` gets height (`min-height: calc(100vh - 72px)` already on page).

- [ ] **Step 6: Wheel non-passive**

React’s `onWheel` is passive in some browsers. Attach a native listener in `useEffect` on the SVG/canvas with `{ passive: false }` so `preventDefault` actually stops page scroll.

```javascript
useEffect(() => {
  const el = canvasRef.current
  if (!el) return undefined
  const handler = (event) => {
    event.preventDefault()
    userMovedCameraRef.current = true
    const rect = el.getBoundingClientRect()
    const sx = event.clientX - rect.left
    const sy = event.clientY - rect.top
    const world = screenToWorld(cameraRef.current, sx, sy)
    const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15
    setCamera(zoomAt(cameraRef.current, world.x, world.y, factor))
  }
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [])
```

- [ ] **Step 7: Manual smoke (required before commit)**

1. Resolve a high-degree CVE. Graph should Fit to fill the canvas.
2. Wheel zoom toward a spoke — that spoke stays under the cursor.
3. Click spoke — inspector only; node count unchanged.
4. Double-click — node count may increase.
5. Uncheck Related CVEs — star thins; intel hops remain.
6. If honesty says truncated and cursor exists, LOAD MORE appends nodes.
7. `prefers-reduced-motion: reduce` — no long float, Fit still runs.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/investigate/InvestigateGraph.jsx frontend/src/components/investigate/InvestigateGraph.css
git commit -m "feat(investigate): pan/zoom/fit canvas with inspect vs expand"
```

---

### Task 6: Docs

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` (Investigation graph row)
- Modify: `docs/USE.md` (investigate row)
- Modify: `docs/plans/2026-08-13-investigation-platform-roadmap.md` (P1 note: P1.5 canvas UX)

- [ ] **Step 1: PRODUCT_STATUS** — replace “click-to-expand” with inspect / double-click expand, pan/zoom/Fit, related-CVE toggle, Load more via `next_cursor`.

- [ ] **Step 2: USE.md** — one sentence: pan/zoom, click inspect, double-click expand.

- [ ] **Step 3: Commit**

```bash
git add docs/PRODUCT_STATUS.md docs/USE.md docs/plans/2026-08-13-investigation-platform-roadmap.md
git commit -m "docs: INVESTIGATE canvas pan/zoom and inspect vs expand"
```

---

### Task 7: Verify

- [ ] **Step 1:** `cd frontend && npm run test:unit`

Expected: PASS including new camera/filter/layout/merge tests.

- [ ] **Step 2:** `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 3:** `./scripts/verify-local.sh`

Expected: green (or documented SQLite fallback). No backend test changes required.

---

## Spec coverage

| Spec section | Task |
|--------------|------|
| Camera pan/zoom/fit/reset/keyboard | 1, 5 |
| Layout unclamped + repulsion n>80 + rings | 2 |
| Inspect vs expand | 5 |
| LOD labels + inverse hit radius | 5 |
| Type glyphs | 5 |
| Related-CVE toggle | 4, 5 |
| Load more / next_cursor | 3, 5 |
| Overlay chrome / a11y / reduced motion | 5 |
| Docs | 6 |
| No new graph lib / GraphPage unchanged | Global + all tasks |

## Placeholder scan

No TBD/TODO remaining. `stepForce` 5th argument `rootId` is defined in Task 2 and consumed in Task 5.

## Out of this plan (follow-ups, not blockers)

- Server-side cap or down-rank of `related_cve_heuristic` if 50 derived CVEs still dominate after the toggle.
- Minimap.
- Persisted camera per query in `sessionStorage`.
- Email/mutex as graph entity types (P1+ contracts).
