import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  visibleGraph,
  incidentEdges,
  relatedCveCount,
  neighborIds,
  parseIocEntityId,
  canExpandEntityType,
  heuristicCveIds,
  formatNeighborhoodMarkdown,
} from './investigateGraphFilters.js'

const root = { node_id: 'cve:ROOT', entity_type: 'cve', entity_id: 'ROOT', label: 'ROOT' }
const ioc = { node_id: 'ioc:hash:abcd', entity_type: 'ioc', entity_id: 'hash:abcd', label: 'abcd' }
const rel = { node_id: 'cve:REL', entity_type: 'cve', entity_id: 'REL', label: 'REL' }
const sigma = { node_id: 'sigma_rule:S1', entity_type: 'sigma_rule', entity_id: 'S1', label: 'S1' }
const graph = {
  root_id: 'cve:ROOT',
  nodes: [root, ioc, rel, sigma],
  edges: [
    {
      edge_id: 'e-ioc',
      source_node_id: 'cve:ROOT',
      target_node_id: 'ioc:hash:abcd',
      source_key: 'otx',
      edge_class: 'reported',
      observed_at: '2024-01-01T00:00:00Z',
    },
    {
      edge_id: 'e-rel',
      source_node_id: 'cve:ROOT',
      target_node_id: 'cve:REL',
      source_key: 'related_cve_heuristic',
      edge_class: 'derived',
    },
    {
      edge_id: 'e-sigma',
      source_node_id: 'cve:ROOT',
      target_node_id: 'sigma_rule:S1',
      source_key: 'sigmahq',
      edge_class: 'direct_fact',
    },
  ],
}

describe('visibleGraph', () => {
  it('hides heuristic-only CVEs when showRelatedCves is false', () => {
    const out = visibleGraph(graph, { showRelatedCves: false })
    assert.deepEqual(
      out.nodes.map((n) => n.node_id).sort(),
      ['cve:ROOT', 'ioc:hash:abcd', 'sigma_rule:S1'],
    )
  })

  it('filters to IOC type chips without dropping the root', () => {
    const out = visibleGraph(graph, { showRelatedCves: true, entityType: 'ioc' })
    assert.ok(out.nodes.some((n) => n.node_id === 'cve:ROOT'))
    assert.ok(out.nodes.every((n) => n.entity_type === 'ioc' || n.node_id === 'cve:ROOT'))
  })

  it('hides derived edges when edgeClasses omits derived', () => {
    const out = visibleGraph(graph, {
      showRelatedCves: true,
      edgeClasses: new Set(['direct_fact', 'reported']),
    })
    assert.equal(out.edges.some((e) => e.edge_class === 'derived'), false)
    assert.equal(out.nodes.some((n) => n.node_id === 'cve:REL'), false)
  })

  it('isolates selected plus one hop', () => {
    const out = visibleGraph(graph, { isolateNodeId: 'ioc:hash:abcd' })
    assert.deepEqual(
      out.nodes.map((n) => n.node_id).sort(),
      ['cve:ROOT', 'ioc:hash:abcd'],
    )
  })
})

describe('parseIocEntityId', () => {
  it('splits kind:value without treating hashes as ips', () => {
    assert.deepEqual(parseIocEntityId('hash:deadbeef', 'deadbeef'), {
      type: 'hash',
      value: 'deadbeef',
    })
    assert.deepEqual(parseIocEntityId('domain:evil.example', 'evil.example'), {
      type: 'domain',
      value: 'evil.example',
    })
    assert.deepEqual(parseIocEntityId('url:https://evil.example/x', 'https://evil.example/x'), {
      type: 'url',
      value: 'https://evil.example/x',
    })
    assert.deepEqual(parseIocEntityId('ip:1.1.1.1', '1.1.1.1'), {
      type: 'ip',
      value: '1.1.1.1',
    })
  })
})

describe('canExpandEntityType', () => {
  it('allows publication and rejects sigma_rule', () => {
    assert.equal(canExpandEntityType('publication'), true)
    assert.equal(canExpandEntityType('sigma_rule'), false)
  })
})

describe('incidentEdges', () => {
  it('returns edges touching the selected node with source_key', () => {
    const rows = incidentEdges(graph, 'cve:ROOT')
    assert.equal(rows.length, 3)
    assert.equal(rows[0].source_key, 'otx')
  })
})

describe('formatNeighborhoodMarkdown', () => {
  it('emits ticket-ready lines', () => {
    const md = formatNeighborhoodMarkdown(root, incidentEdges(graph, 'cve:ROOT'), new Map(
      graph.nodes.map((n) => [n.node_id, n]),
    ))
    assert.match(md, /cve ROOT/)
    assert.match(md, /otx/)
    assert.match(md, /reported/)
  })
})

describe('heuristicCveIds', () => {
  it('marks related CVEs that have no non-heuristic edge', () => {
    const ids = heuristicCveIds(graph)
    assert.equal(ids.has('cve:REL'), true)
    assert.equal(ids.has('cve:ROOT'), false)
  })
})
