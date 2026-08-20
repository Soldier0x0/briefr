import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { createGraphEngine } from './investigateGraphEngine.js'

const nodes = [
  { node_id: 'root', entity_type: 'cve' },
  { node_id: 'a', entity_type: 'ioc' },
  { node_id: 'b', entity_type: 'cve' },
]
const edges = [
  { source_node_id: 'root', target_node_id: 'a' },
  { source_node_id: 'root', target_node_id: 'b' },
]

describe('createGraphEngine', () => {
  it('decays alpha until the loop stops', () => {
    const engine = createGraphEngine()
    engine.setSize(800, 600)
    engine.setTopology(nodes, edges, 'root')
    let running = true
    let ticks = 0
    while (running && ticks < 800) {
      running = engine.tick()
      ticks += 1
    }
    assert.ok(engine.alpha() <= 0.001 || running === false)
    assert.ok(ticks < 800)
  })

  it('reheat restarts motion after settle', () => {
    const engine = createGraphEngine()
    engine.setSize(800, 600)
    engine.setTopology(nodes, edges, 'root')
    while (engine.tick()) { /* settle */ }
    const before = engine.alpha()
    engine.reheat(0.4)
    assert.ok(engine.alpha() >= 0.4)
    assert.ok(engine.alpha() > before)
    assert.equal(engine.tick(), true)
  })

  it('keeps a pinned node fixed while neighbors move', () => {
    const engine = createGraphEngine()
    engine.setSize(800, 600)
    engine.setTopology(nodes, edges, 'root')
    engine.pinNode('a', 10, 20)
    engine.reheat(1)
    for (let i = 0; i < 20; i += 1) engine.tick()
    const a = engine.getPositions().find((n) => n.node_id === 'a')
    assert.equal(a.x, 10)
    assert.equal(a.y, 20)
  })

  it('fires onSettled once per settle', () => {
    let settled = 0
    const engine = createGraphEngine({
      onSettled: () => { settled += 1 },
      prefersReducedMotion: true,
    })
    engine.setSize(400, 400)
    engine.setTopology(nodes, edges, 'root')
    while (engine.tick()) { /* reduced ticks */ }
    engine.tick()
    engine.tick()
    assert.equal(settled, 1)
  })
})
