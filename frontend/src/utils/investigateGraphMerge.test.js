import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  emptyGraphState,
  INVESTIGATE_GRAPH_MAX_EDGES,
  INVESTIGATE_GRAPH_MAX_NODES,
  buildInvestigationRelationshipQuery,
  investigationEntityPath,
  mergeGraphPage,
} from './investigateGraphMerge.js'

describe('mergeGraphPage', () => {
  it('merges nodes and edges by id and keeps truncation sticky', () => {
    const first = mergeGraphPage(emptyGraphState(), {
      root: { node_id: 'cve:CVE-2024-1', entity_type: 'cve', entity_id: 'CVE-2024-1', label: 'CVE-2024-1' },
      nodes: [{ node_id: 'ioc:ip:1.1.1.1', entity_type: 'ioc', entity_id: 'ip:1.1.1.1', label: '1.1.1.1' }],
      edges: [{ edge_id: 'e1', source_node_id: 'cve:CVE-2024-1', target_node_id: 'ioc:ip:1.1.1.1', edge_class: 'reported' }],
      truncated: true,
      source_status: 'ok',
      knowledge_state: 'partial',
    })
    const second = mergeGraphPage(first, {
      root: { node_id: 'ioc:ip:1.1.1.1', entity_type: 'ioc', entity_id: 'ip:1.1.1.1', label: '1.1.1.1' },
      nodes: [{ node_id: 'cve:CVE-2024-2', entity_type: 'cve', entity_id: 'CVE-2024-2', label: 'CVE-2024-2' }],
      edges: [{ edge_id: 'e2', source_node_id: 'ioc:ip:1.1.1.1', target_node_id: 'cve:CVE-2024-2', edge_class: 'derived' }],
      truncated: false,
      source_status: 'degraded',
      knowledge_state: 'known',
    })
    assert.equal(second.nodes.length, 3)
    assert.equal(second.edges.length, 2)
    assert.equal(second.truncated, true)
    assert.equal(second.capped, false)
    assert.equal(second.source_status, 'degraded')
    assert.equal(second.root_id, 'ioc:ip:1.1.1.1')
  })

  it('caps accumulated nodes and edges and keeps capped sticky', () => {
    const root = { node_id: 'cve:CVE-ROOT', entity_type: 'cve', entity_id: 'CVE-ROOT', label: 'CVE-ROOT' }
    const nodes = Array.from({ length: INVESTIGATE_GRAPH_MAX_NODES + 25 }, (_, i) => ({
      node_id: `cve:CVE-${i}`,
      entity_type: 'cve',
      entity_id: `CVE-${i}`,
      label: `CVE-${i}`,
    }))
    const edges = Array.from({ length: INVESTIGATE_GRAPH_MAX_EDGES + 10 }, (_, i) => ({
      edge_id: `e${i}`,
      source_node_id: 'cve:CVE-ROOT',
      target_node_id: 'cve:CVE-0',
      edge_class: 'derived',
    }))
    const merged = mergeGraphPage(emptyGraphState(), {
      root,
      nodes,
      edges,
      truncated: false,
      source_status: 'ok',
    })
    assert.equal(merged.nodes.length, INVESTIGATE_GRAPH_MAX_NODES)
    assert.equal(merged.edges.length, INVESTIGATE_GRAPH_MAX_EDGES)
    assert.equal(merged.capped, true)
    assert.equal(merged.truncated, true)
    assert.ok(merged.nodes.some((node) => node.node_id === 'cve:CVE-ROOT'))

    const again = mergeGraphPage(merged, {
      root,
      nodes: [{ node_id: 'cve:CVE-NEW', entity_type: 'cve', entity_id: 'CVE-NEW', label: 'CVE-NEW' }],
      edges: [],
      truncated: false,
      source_status: 'ok',
    })
    assert.equal(again.capped, true)
    assert.equal(again.truncated, true)
  })

  it('stores next_cursor per expanded root id', () => {
    const page = {
      root: { node_id: 'cve:CVE-1', entity_type: 'cve', entity_id: 'CVE-1', label: 'CVE-1' },
      nodes: [{ node_id: 'cve:CVE-1', entity_type: 'cve', entity_id: 'CVE-1', label: 'CVE-1' }],
      edges: [],
      truncated: true,
      next_cursor: 'abc',
      source_status: 'ok',
      knowledge_state: 'partial',
    }
    const first = mergeGraphPage(emptyGraphState(), page)
    assert.equal(first.cursorsByNodeId['cve:CVE-1'], 'abc')
    const second = mergeGraphPage(first, {
      ...page,
      root: { node_id: 'cve:CVE-2', entity_type: 'cve', entity_id: 'CVE-2', label: 'CVE-2' },
      nodes: [{ node_id: 'cve:CVE-2', entity_type: 'cve', entity_id: 'CVE-2', label: 'CVE-2' }],
      truncated: false,
      next_cursor: null,
    })
    assert.equal(second.cursorsByNodeId['cve:CVE-1'], 'abc')
    assert.equal(second.cursorsByNodeId['cve:CVE-2'], null)
  })
})

describe('investigationEntityPath', () => {
  it('percent-encodes path segments (slashes stay encoded, not raw)', () => {
    assert.equal(
      investigationEntityPath('ioc', 'url:https://evil.example/phish'),
      '/investigations/entities/ioc/url%3Ahttps%3A%2F%2Fevil.example%2Fphish',
    )
  })

  it('blocks path traversal via encodeURIComponent on entity_id', () => {
    assert.equal(
      investigationEntityPath('cve', '../cve/CVE-2024-1'),
      '/investigations/entities/cve/..%2Fcve%2FCVE-2024-1',
    )
    assert.equal(
      investigationEntityPath('../ioc', 'ip:1.1.1.1'),
      '/investigations/entities/..%2Fioc/ip%3A1.1.1.1',
    )
  })
})

describe('buildInvestigationRelationshipQuery', () => {
  it('serializes limit and depth when zero', () => {
    assert.equal(buildInvestigationRelationshipQuery({ limit: 0, depth: 0 }), '?limit=0&depth=0')
  })

  it('omits absent params', () => {
    assert.equal(buildInvestigationRelationshipQuery(), '')
    assert.equal(buildInvestigationRelationshipQuery({ cursor: 'abc' }), '?cursor=abc')
  })

  it('sends include_semantic when true', () => {
    assert.equal(
      buildInvestigationRelationshipQuery({ include_semantic: true }),
      '?include_semantic=true',
    )
  })

  it('omits include_semantic when false', () => {
    assert.equal(buildInvestigationRelationshipQuery({ include_semantic: false }), '')
  })
})
