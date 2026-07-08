import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { formatSharedObservablesSummary } from './sharedObservables.js'

describe('formatSharedObservablesSummary', () => {
  it('formats mixed observable counts', () => {
    const summary = formatSharedObservablesSummary({
      shared_ip_count: 1,
      shared_domain_count: 2,
      shared_hash_count: 1,
      shared_url_count: 0,
    })
    assert.equal(summary, '1 IP · 2 domains · 1 hash')
  })

  it('falls back to total count', () => {
    assert.equal(formatSharedObservablesSummary({ shared_ioc_count: 3 }), '3 observables')
  })

  it('returns dash when empty', () => {
    assert.equal(formatSharedObservablesSummary({}), '—')
  })
})
