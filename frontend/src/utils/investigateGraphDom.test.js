import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { applyGraphDom, applyWorldTransform } from './investigateGraphDom.js'

function mockEl(initial = {}) {
  const attrs = new Map(Object.entries(initial))
  return {
    getAttribute(key) {
      return attrs.has(key) ? attrs.get(key) : null
    },
    setAttribute(key, value) {
      attrs.set(key, value)
    },
    removeAttribute(key) {
      attrs.delete(key)
    },
    attrs,
  }
}

function mockRoot({ nodes = [], lines = [] } = {}) {
  return {
    querySelectorAll(selector) {
      if (selector === '[data-node-id]') return nodes
      if (selector === '[data-edge-id]') return lines
      return []
    },
  }
}

describe('investigateGraphDom', () => {
  it('applyWorldTransform sets world group transform', () => {
    const world = mockEl()
    applyWorldTransform(world, { x: 10, y: 20, scale: 2 })
    assert.equal(world.getAttribute('transform'), 'translate(10 20) scale(2)')
  })

  it('applyGraphDom positions nodes and edges from live data', () => {
    const nodeA = mockEl({ 'data-node-id': 'a' })
    const nodeB = mockEl({ 'data-node-id': 'b' })
    const line = mockEl({ 'data-edge-id': 'e1' })
    const root = mockRoot({ nodes: [nodeA, nodeB], lines: [line] })
    applyGraphDom(root, [
      { node_id: 'a', x: 1, y: 2 },
      { node_id: 'b', x: 3, y: 4 },
    ], [{
      edge_id: 'e1',
      source_node_id: 'a',
      target_node_id: 'b',
    }])
    assert.equal(nodeA.getAttribute('transform'), 'translate(1 2)')
    assert.equal(line.getAttribute('x1'), '1')
    assert.equal(line.getAttribute('y2'), '4')
  })

  it('applyGraphDom no-ops when positions are empty', () => {
    const staleNode = mockEl({ 'data-node-id': 'gone' })
    const root = mockRoot({ nodes: [staleNode], lines: [] })
    applyGraphDom(root, [], [])
    assert.equal(staleNode.getAttribute('visibility'), null)
  })

  it('applyGraphDom hides stale nodes and edges', () => {
    const staleNode = mockEl({ 'data-node-id': 'gone' })
    const line = mockEl({ 'data-edge-id': 'e1' })
    const root = mockRoot({ nodes: [staleNode], lines: [line] })
    applyGraphDom(root, [], [{
      edge_id: 'e1',
      source_node_id: 'a',
      target_node_id: 'b',
    }])
    assert.equal(staleNode.getAttribute('visibility'), 'hidden')
    assert.equal(line.getAttribute('visibility'), 'hidden')
  })
})
