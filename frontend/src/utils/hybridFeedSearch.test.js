import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  filterHybridHits,
  hybridSearchStatusLabel,
  partitionHybridHits,
  processHybridSearchResults,
  semanticHitToCampaignCard,
  semanticHitToCveCard,
  semanticHitToTechniqueCard,
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

  it('defers to /api/cves when list filters need server fields hybrid lacks', () => {
    assert.equal(shouldUseHybridSearch({ search: 'x', poc_only: true }), false)
    assert.equal(shouldUseHybridSearch({ search: 'microsoft', vendors: 'Microsoft' }), false)
    assert.equal(shouldUseHybridSearch({ search: 'x', exclude_vendors: 'linux' }), false)
    assert.equal(shouldUseHybridSearch({ search: 'x', severity_list: 'CRITICAL,HIGH' }), false)
    assert.equal(shouldUseHybridSearch({ search: '' }), false)
  })

  it('uses hybrid for multi-token natural queries even with parsed vendor chips', () => {
    assert.equal(
      shouldUseHybridSearch({
        feed_query: 'amazon kv',
        vendors: 'Amazon',
        search: 'kv',
      }),
      true,
    )
    assert.equal(
      shouldUseHybridSearch({
        feed_query: 'amazon plus kv',
        vendors: 'Amazon',
        search: 'plus kv',
      }),
      true,
    )
  })

  it('defers fully structured multi-token queries to /api/cves', () => {
    assert.equal(
      shouldUseHybridSearch({
        feed_query: 'amazon + kev',
        vendors: 'Amazon',
        search: '',
        kev_only: true,
      }),
      false,
    )
    assert.equal(
      shouldUseHybridSearch({
        feed_query: 'apache kev',
        vendors: 'Apache',
        search: '',
        kev_only: true,
      }),
      false,
    )
    assert.equal(
      shouldUseHybridSearch({ feed_query: 'vendor:apache is:kev' }),
      false,
    )
  })

  it('defers single-token vendor-only queries to /api/cves', () => {
    assert.equal(
      shouldUseHybridSearch({ feed_query: 'amazon', vendors: 'Amazon', search: '' }),
      false,
    )
  })

  it('keeps hybrid when My Stack / severity / KEV chips are active (E7)', () => {
    assert.equal(shouldUseHybridSearch({ search: 'rce', stack: 'nginx' }), true)
    assert.equal(shouldUseHybridSearch({ search: 'rce', my_stack_only: true }), true)
    assert.equal(shouldUseHybridSearch({ search: 'rce', severity: 'HIGH', kev_only: true }), true)
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

  it('partitions technique and campaign hits instead of dropping them', () => {
    const hits = [
      { entity_type: 'cve', cve_id: 'CVE-1', description: 'a', severity: 'HIGH' },
      {
        entity_type: 'technique',
        entity_id: 'T1059',
        name: 'Command and Scripting Interpreter',
        tactic: 'Execution',
      },
      {
        entity_type: 'campaign',
        entity_id: 'camp-1',
        label: 'Ransom op',
        member_count: 4,
      },
    ]
    const parts = partitionHybridHits(hits)
    assert.equal(parts.cves.length, 1)
    assert.equal(parts.techniques.length, 1)
    assert.equal(parts.campaigns.length, 1)

    const processed = processHybridSearchResults(hits, {})
    assert.equal(processed.cves.length, 1)
    assert.equal(processed.cves[0].cve_id, 'CVE-1')
    assert.equal(processed.techniques.length, 1)
    assert.equal(processed.techniques[0].technique_id, 'T1059')
    assert.equal(processed.campaigns.length, 1)
    assert.equal(processed.campaigns[0].campaign_id, 'camp-1')
  })

  it('still maps CVE hits via semanticHitToCveCard and applies CVE filters', () => {
    const hits = [
      { entity_type: 'cve', cve_id: 'CVE-1', severity: 'CRITICAL', is_kev: true },
      { entity_type: 'cve', cve_id: 'CVE-2', severity: 'LOW', is_kev: false },
      { entity_type: 'technique', entity_id: 'T1190', name: 'Exploit Public-Facing Application' },
    ]
    const processed = processHybridSearchResults(hits, { severity: 'CRITICAL', kev_only: true })
    assert.equal(processed.cves.length, 1)
    assert.equal(processed.cves[0].cve_id, 'CVE-1')
    assert.equal(processed.techniques.length, 1)
    assert.equal(
      semanticHitToTechniqueCard({ entity_id: 'T1059', name: 'PowerShell' }).technique_id,
      'T1059',
    )
    assert.equal(
      semanticHitToCampaignCard({ entity_id: 'camp-9', label: 'Cluster' }).campaign_id,
      'camp-9',
    )
  })
})
