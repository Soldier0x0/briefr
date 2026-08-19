import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { emptyGraphState, investigationEntityPath, mergeGraphPage } from './investigateGraphMerge.js'

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
    assert.equal(second.source_status, 'degraded')
    assert.equal(second.root_id, 'ioc:ip:1.1.1.1')
  })
})

describe('investigationEntityPath', () => {
  it('keeps slashes in path ids for FastAPI :path', () => {
    assert.equal(
      investigationEntityPath('ioc', 'url:https://evil.example/phish'),
      '/investigations/entities/ioc/url:https://evil.example/phish',
    )
  })
})
