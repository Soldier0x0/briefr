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
