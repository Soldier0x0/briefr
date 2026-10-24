import { describe, it, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  clearInvestigateDraft,
  hasInvestigateDraft,
  loadInvestigateDraft,
  saveInvestigateDraft,
} from './investigateDraftStorage.js'

const STORAGE_KEY = 'briefr:investigate:draft:v1'

describe('investigateDraftStorage', () => {
  beforeEach(() => {
    globalThis.window = { localStorage: new MapStorage() }
  })

  afterEach(() => {
    delete globalThis.window
  })

  it('round-trips draft payload', () => {
    const payload = {
      query: 'CVE-2024-1',
      graph: { nodes: [{ node_id: 'cve:CVE-2024-1' }], edges: [] },
      positions: [{ node_id: 'cve:CVE-2024-1', x: 1, y: 2 }],
      view: { x: 0, y: 0, scale: 1 },
      filters: { showRelatedCves: false },
    }
    saveInvestigateDraft(payload)
    assert.equal(hasInvestigateDraft(), true)
    const loaded = loadInvestigateDraft()
    assert.equal(loaded.query, 'CVE-2024-1')
    assert.equal(loaded.graph.nodes[0].node_id, 'cve:CVE-2024-1')
  })

  it('expires drafts older than 24h', () => {
    saveInvestigateDraft({
      graph: { nodes: [], edges: [] },
      savedAt: Date.now() - (25 * 60 * 60 * 1000),
    })
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      graph: { nodes: [], edges: [] },
      savedAt: Date.now() - (25 * 60 * 60 * 1000),
    }))
    assert.equal(loadInvestigateDraft(), null)
  })

  it('clear removes draft', () => {
    saveInvestigateDraft({ graph: { nodes: [], edges: [] } })
    clearInvestigateDraft()
    assert.equal(hasInvestigateDraft(), false)
  })
})

class MapStorage {
  constructor() {
    this.store = new Map()
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null
  }

  setItem(key, value) {
    this.store.set(key, value)
  }

  removeItem(key) {
    this.store.delete(key)
  }
}
