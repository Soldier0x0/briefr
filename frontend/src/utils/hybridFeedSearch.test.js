import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  filterHybridHits,
  hybridSearchStatusLabel,
  semanticHitToCveCard,
  shouldUseHybridSearch,
} from './hybridFeedSearch.js'

describe('hybridFeedSearch', () => {
  it('uses hybrid when search is the primary signal', () => {
    assert.equal(shouldUseHybridSearch({ search: 'openssl rce' }), true)
    assert.equal(
      shouldUseHybridSearch({ search: 'CVE-2024-1234', severity: 'HIGH' }),
      true,
    )
  })

  it('defers to /api/cves when list filters need server fields', () => {
    assert.equal(shouldUseHybridSearch({ search: 'x', poc_only: true }), false)
    assert.equal(shouldUseHybridSearch({ search: 'x', stack: 'nginx' }), false)
    assert.equal(shouldUseHybridSearch({ search: '' }), false)
  })

  it('maps hits and applies severity/kev filters', () => {
    const rows = filterHybridHits(
      [
        {
          cve_id: 'CVE-1',
          description: 'a',
          severity: 'CRITICAL',
          is_kev: true,
        },
        {
          cve_id: 'CVE-2',
          description: 'b',
          severity: 'LOW',
          is_kev: false,
        },
      ],
      { severity: 'CRITICAL', kev_only: true },
    )
    assert.equal(rows.length, 1)
    assert.equal(rows[0].cve_id, 'CVE-1')
    assert.equal(
      semanticHitToCveCard({ entity_id: 'CVE-9', description: 'z' }).cve_id,
      'CVE-9',
    )
  })

  it('labels keyword fallback quietly', () => {
    assert.match(
      hybridSearchStatusLabel({ method: 'keyword_fallback' }),
      /Keyword/,
    )
    assert.equal(hybridSearchStatusLabel({ method: 'hybrid' }), 'Hybrid search')
  })
})
