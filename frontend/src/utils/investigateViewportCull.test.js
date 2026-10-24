import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { cullNodesForViewport, visibleInViewport } from './investigateViewportCull.js'

describe('investigateViewportCull', () => {
  it('keeps nodes inside the viewport margin', () => {
    const node = { node_id: 'cve:CVE-1', x: 100, y: 100 }
    const view = { x: 0, y: 0, scale: 1 }
    const viewport = { width: 800, height: 600 }
    assert.equal(visibleInViewport(node, view, viewport), true)
    const culled = cullNodesForViewport([node], view, viewport)
    assert.equal(culled.length, 1)
  })
})
