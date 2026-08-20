import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyGraphDom,
  applyNodeScaleDom,
  applyWorldTransform,
  hitRadius,
  shouldShowLabel,
} from './investigateGraphDom.js'

function mockEl(initial = {}) {
  const attrs = new Map(Object.entries(initial))
  const children = []
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
    querySelector(selector) {
      if (selector === '.investigate-node-hit') return children.find((c) => c.className === 'hit') || null
      if (selector === '.investigate-node-label') return children.find((c) => c.className === 'label') || null
      return null
    },
    attrs,
    children,
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

  it('applyGraphDom no-ops on transient empty positions', () => {
    const staleNode = mockEl({ 'data-node-id': 'gone' })
    const root = mockRoot({ nodes: [staleNode], lines: [] })
    applyGraphDom(root, [], [])
    assert.equal(staleNode.getAttribute('visibility'), null)
  })

  it('applyGraphDom hides stale nodes when hideWhenEmpty is set', () => {
    const staleNode = mockEl({ 'data-node-id': 'gone' })
    const line = mockEl({ 'data-edge-id': 'e1' })
    const root = mockRoot({ nodes: [staleNode], lines: [line] })
    applyGraphDom(root, [], [{
      edge_id: 'e1',
      source_node_id: 'a',
      target_node_id: 'b',
    }], { hideWhenEmpty: true })
    assert.equal(staleNode.getAttribute('visibility'), 'hidden')
    assert.equal(line.getAttribute('visibility'), 'hidden')
  })

  it('applyNodeScaleDom updates hit radius when scale changes', () => {
    const hit = mockEl({ className: 'hit' })
    hit.className = 'hit'
    const node = mockEl({
      'data-node-id': 'n1',
      'data-entity-type': 'cve',
      'data-label': 'CVE-2026-0001',
    })
    node.children.push(hit)
    const root = mockRoot({ nodes: [node] })
    applyNodeScaleDom(root, 1, {})
    const r1 = hit.getAttribute('r')
    applyNodeScaleDom(root, 2, {})
    const r2 = hit.getAttribute('r')
    assert.notEqual(r1, r2)
    assert.equal(Number(r1), hitRadius(1))
    assert.equal(Number(r2), hitRadius(2))
  })

  it('applyNodeScaleDom toggles label visibility at scale thresholds', () => {
    const label = mockEl({ className: 'label' })
    label.className = 'label'
    const node = mockEl({
      'data-node-id': 'n1',
      'data-entity-type': 'ioc',
      'data-label': '1.2.3.4',
    })
    node.children.push(label)
    const root = mockRoot({ nodes: [node] })
    applyNodeScaleDom(root, 1, {})
    assert.equal(label.getAttribute('visibility'), 'hidden')
    applyNodeScaleDom(root, 1.3, {})
    assert.equal(label.getAttribute('visibility'), 'visible')
    assert.equal(
      shouldShowLabel({ node_id: 'n1', entity_type: 'ioc', label: '1.2.3.4' }, {
        selectedId: null,
        hoveredId: null,
        findLower: '',
        scale: 1.3,
        rootId: null,
      }),
      true,
    )
  })
})
