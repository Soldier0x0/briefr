import { seedExpandPositions, seedPositions, stepForce } from './investigateForceLayout.js'

const ALPHA_DECAY = 0.985
const ALPHA_MIN = 0.001
const REHEAT_ALPHA = 0.4
const REDUCED_TICKS = 12

export function createGraphEngine({
  onFrame = null,
  onSettled = null,
  prefersReducedMotion = false,
} = {}) {
  let positions = []
  let edges = []
  let rootId = null
  let alpha = 0
  let pins = new Map()
  let raf = 0
  let settled = true
  let width = 800
  let height = 560
  let reducedTicksLeft = 0

  function notifyFrame() {
    onFrame?.(positions)
  }

  function tickOnce() {
    if (prefersReducedMotion) {
      if (reducedTicksLeft <= 0) {
        finishSettle()
        return false
      }
      positions = stepForce(positions, edges, width, height, rootId)
      applyPins()
      reducedTicksLeft -= 1
      notifyFrame()
      if (reducedTicksLeft <= 0) finishSettle()
      return reducedTicksLeft > 0
    }
    if (alpha <= ALPHA_MIN && pins.size === 0) {
      finishSettle()
      return false
    }
    const prev = new Map(positions.map((n) => [n.node_id, n]))
    const stepped = stepForce(positions, edges, width, height, rootId)
    positions = stepped.map((node) => {
      const pin = pins.get(node.node_id)
      if (pin) {
        return { ...node, x: pin.x, y: pin.y, vx: 0, vy: 0 }
      }
      const before = prev.get(node.node_id)
      if (!before) return node
      return {
        ...node,
        x: before.x + (node.x - before.x) * alpha,
        y: before.y + (node.y - before.y) * alpha,
        vx: node.vx * alpha,
        vy: node.vy * alpha,
      }
    })
    if (pins.size === 0) alpha *= ALPHA_DECAY
    notifyFrame()
    return true
  }

  function applyPins() {
    if (!pins.size) return
    positions = positions.map((node) => {
      const pin = pins.get(node.node_id)
      if (!pin) return node
      return { ...node, x: pin.x, y: pin.y, vx: 0, vy: 0 }
    })
  }

  function finishSettle() {
    if (settled) return
    settled = true
    onSettled?.(positions)
  }

  function loop() {
    const keep = tickOnce()
    if (keep) raf = requestAnimationFrame(loop)
    else raf = 0
  }

  function startLoop() {
    if (typeof requestAnimationFrame !== 'function') return
    if (raf) return
    raf = requestAnimationFrame(loop)
  }

  return {
    setSize(nextWidth, nextHeight) {
      width = Math.max(nextWidth, 1)
      height = Math.max(nextHeight, 1)
    },
    setTopology(nodes, nextEdges, nextRootId) {
      const prior = new Map(positions.map((n) => [n.node_id, n]))
      edges = nextEdges || []
      rootId = nextRootId
      const nodeIds = new Set((nodes || []).map((n) => n.node_id))
      for (const id of pins.keys()) {
        if (!nodeIds.has(id)) pins.delete(id)
      }
      positions = seedPositions(nodes, width, height, prior, rootId)
      this.reheat(1)
      notifyFrame()
    },
    restorePositions(nodes, nextEdges, nextRootId, savedPositions) {
      edges = nextEdges || []
      rootId = nextRootId
      const prior = new Map((savedPositions || []).map((n) => [n.node_id, n]))
      const metaById = new Map((nodes || []).map((n) => [n.node_id, n]))
      positions = (nodes || []).map((node) => {
        const saved = prior.get(node.node_id)
        const meta = metaById.get(node.node_id) || node
        if (saved) {
          return { ...meta, x: saved.x, y: saved.y, vx: 0, vy: 0 }
        }
        return { ...meta, x: width / 2, y: height / 2, vx: 0, vy: 0 }
      })
      alpha = ALPHA_MIN
      settled = true
      notifyFrame()
    },
    mergeTopology(allNodes, nextEdges, nextRootId, { expandParentId = null, parentPosition = null } = {}) {
      const prior = new Map(positions.map((n) => [n.node_id, n]))
      edges = nextEdges || []
      rootId = nextRootId
      const nodeIds = new Set((allNodes || []).map((n) => n.node_id))
      for (const id of pins.keys()) {
        if (!nodeIds.has(id)) pins.delete(id)
      }
      if (expandParentId && parentPosition) {
        const parentNode = {
          node_id: expandParentId,
          x: parentPosition.x,
          y: parentPosition.y,
        }
        const added = (allNodes || []).filter((n) => !prior.has(n.node_id))
        const merged = seedExpandPositions(parentNode, added, prior, { width, height })
        const metaById = new Map((allNodes || []).map((n) => [n.node_id, n]))
        positions = merged.map((node) => {
          const meta = metaById.get(node.node_id) || node
          return { ...meta, x: node.x, y: node.y, vx: node.vx || 0, vy: node.vy || 0 }
        })
        this.reheat(0.4)
      } else {
        positions = seedPositions(allNodes, width, height, prior, rootId)
        this.reheat(1)
      }
      notifyFrame()
    },
    reheat(nextAlpha = REHEAT_ALPHA) {
      alpha = Math.max(alpha, nextAlpha)
      settled = false
      if (prefersReducedMotion) reducedTicksLeft = REDUCED_TICKS
      startLoop()
    },
    pinNode(nodeId, x, y) {
      pins.set(nodeId, { x, y })
      applyPins()
      notifyFrame()
    },
    unpinNode(nodeId) {
      pins.delete(nodeId)
      this.reheat()
    },
    start() {
      startLoop()
    },
    stop() {
      if (raf && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(raf)
      raf = 0
    },
    tick() {
      return tickOnce()
    },
    getPositions() {
      return positions
    },
    alpha() {
      return alpha
    },
  }
}
