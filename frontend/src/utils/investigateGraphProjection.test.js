import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { splitGraphLayers, applyGraphLayers } from './investigateGraphProjection.js'

const SAMPLE = {
  root_id: 'n-root',
  nodes: [
    { node_id: 'n-root', entity_type: 'cve', entity_id: 'CVE-1' },
    { node_id: 'n-ioc', entity_type: 'ioc', entity_id: 'ip:1.1.1.1' },
    { node_id: 'n-rel', entity_type: 'cve', entity_id: 'CVE-2' },
  ],
  edges: [
    {
      source_node_id: 'n-root',
      target_node_id: 'n-ioc',
      source_key: 'nvd',
      edge_class: 'direct_fact',
    },
    {
      source_node_id: 'n-root',
      target_node_id: 'n-rel',
      source_key: 'related_cve_heuristic',
      edge_class: 'derived',
    },
  ],
}

describe('splitGraphLayers', () => {
  it('puts heuristic CVE fan in related layer only', () => {
    const { core, related, counts } = splitGraphLayers(SAMPLE)
    assert.equal(core.nodes.length, 2)
    assert.equal(related.nodes.length, 1)
    assert.equal(counts.relatedCves, 1)
  })

  it('always keeps the root in core even with no incident edges', () => {
    const graph = {
      root_id: 'lonely',
      nodes: [{ node_id: 'lonely', entity_type: 'cve', entity_id: 'CVE-9' }],
      edges: [],
    }
    const { core } = splitGraphLayers(graph)
    assert.equal(core.nodes.length, 1)
    assert.equal(core.nodes[0].node_id, 'lonely')
  })
})

describe('applyGraphLayers', () => {
  it('defaults to core-only (related off)', () => {
    const visible = applyGraphLayers(SAMPLE, { showRelatedCves: false, showSemantic: false })
    assert.ok(visible.nodes.some((n) => n.node_id === 'n-ioc'))
    assert.ok(!visible.nodes.some((n) => n.node_id === 'n-rel'))
  })

  it('includes heuristic nodes when related layer is on', () => {
    const visible = applyGraphLayers(SAMPLE, { showRelatedCves: true, showSemantic: false })
    assert.ok(visible.nodes.some((n) => n.node_id === 'n-rel'))
  })
})
