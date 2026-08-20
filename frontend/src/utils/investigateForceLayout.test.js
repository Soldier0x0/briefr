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
})
