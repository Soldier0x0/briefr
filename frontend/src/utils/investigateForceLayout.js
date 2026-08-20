/** Client-only force layout for INVESTIGATE. API GraphPage has no x/y. */

const REPULSE = 2200
const SPRING = 0.04
const SPRING_LENGTH = 140
const CENTER = 0.012
const DAMPING = 0.82
const REPULSE_PAIR_CAP = 80

export function seedPositions(nodes, width, height, prior = new Map()) {
  const cx = width / 2
  const cy = height / 2
  const radius = Math.min(width, height) * 0.28
  const count = Math.max(nodes.length, 1)
  return nodes.map((node, index) => {
    const kept = prior.get(node.node_id)
    if (kept && Number.isFinite(kept.x) && Number.isFinite(kept.y)) {
      return { ...node, x: kept.x, y: kept.y, vx: kept.vx || 0, vy: kept.vy || 0 }
    }
    const angle = (index / count) * Math.PI * 2
    return {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    }
  })
}

function applySprings(next, edges, byId) {
  for (const edge of edges) {
    const a = byId.get(edge.source_node_id)
    const b = byId.get(edge.target_node_id)
    if (!a || !b) continue
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
    const stretch = dist - SPRING_LENGTH
    const fx = (dx / dist) * stretch * SPRING
    const fy = (dy / dist) * stretch * SPRING
    a.vx += fx
    a.vy += fy
    b.vx -= fx
    b.vy -= fy
  }
}

function applyCenterAndBounds(next, width, height) {
  const cx = width / 2
  const cy = height / 2
  const pad = 36
  for (const node of next) {
    node.vx += (cx - node.x) * CENTER
    node.vy += (cy - node.y) * CENTER
    node.vx *= DAMPING
    node.vy *= DAMPING
    node.x += node.vx
    node.y += node.vy
    node.x = Math.min(width - pad, Math.max(pad, node.x))
    node.y = Math.min(height - pad, Math.max(pad, node.y))
  }
}

export function stepForce(positions, edges, width, height) {
  const next = positions.map((node) => ({ ...node }))
  const byId = new Map(next.map((node) => [node.node_id, node]))

  if (next.length <= REPULSE_PAIR_CAP) {
    for (let i = 0; i < next.length; i += 1) {
      for (let j = i + 1; j < next.length; j += 1) {
        const a = next[i]
        const b = next[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let distSq = dx * dx + dy * dy
        if (distSq < 16) {
          const jitter = ((i + j) % 5) - 2
          dx = jitter * 0.5
          dy = ((i * 3 + j) % 5) - 2
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
      }
    }
  }

  applySprings(next, edges, byId)
  applyCenterAndBounds(next, width, height)
  return next
}
