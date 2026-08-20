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
