import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { seedPositions, stepForce } from './investigateForceLayout.js'

describe('investigateForceLayout', () => {
  it('keeps finite coordinates after ticks', () => {
    const nodes = [
      { node_id: 'a', label: 'A' },
      { node_id: 'b', label: 'B' },
    ]
    let positions = seedPositions(nodes, 800, 600)
    for (let i = 0; i < 20; i += 1) {
      positions = stepForce(
        positions,
        [{ source_node_id: 'a', target_node_id: 'b' }],
        800,
        600,
      )
    }
    for (const node of positions) {
      assert.equal(Number.isFinite(node.x), true)
      assert.equal(Number.isFinite(node.y), true)
    }
  })

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
    const overlap = { x: 400, y: 400, vx: 0, vy: 0 }
    const prior = new Map(nodes.map((node) => [node.node_id, overlap]))
    let positions = seedPositions(nodes, 800, 600, prior, 'n0')
    const startXs = positions.map((p) => p.x)
    const startSpan = Math.max(...startXs) - Math.min(...startXs)
    assert.equal(startSpan, 0)
    for (let i = 0; i < 40; i += 1) {
      positions = stepForce(positions, edges, 800, 600, 'n0')
    }
    const xs = positions.map((p) => p.x)
    const span = Math.max(...xs) - Math.min(...xs)
    assert.ok(span > startSpan, `expected spread from overlap, got ${span}`)
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
})
