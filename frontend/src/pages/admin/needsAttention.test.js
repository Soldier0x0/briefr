import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { collectNeedsAttentionItems } from './needsAttention.js'

const BASE_SYSTEM = {
  db_integrity: { ok: true },
  feeds: { sources: {}, incidents: { stale: false } },
  webhooks: { failing: [], failing_count: 0 },
  last_nvd_sync_age_seconds: 600,
  last_backup_age_seconds: 3600,
  backup_threshold_seconds: 43200,
  failed_auth_last_24h: 0,
}

describe('collectNeedsAttentionItems (E8-3)', () => {
  it('returns empty list when system is healthy', () => {
    assert.deepEqual(collectNeedsAttentionItems(BASE_SYSTEM), [])
  })

  it('aggregates open circuits and webhook failures', () => {
    const items = collectNeedsAttentionItems({
      ...BASE_SYSTEM,
      feeds: {
        ...BASE_SYSTEM.feeds,
        sources: {
          nvd: { circuit_open: true, consecutive_failures: 3 },
        },
      },
      webhooks: {
        failing: [{ id: 'discord', name: 'Discord', last_error: 'HTTP 500' }],
        failing_count: 1,
      },
    })
    assert.ok(items.some(i => i.id === 'circuit-nvd'))
    assert.ok(items.some(i => i.id === 'webhook-discord'))
    assert.equal(items[0].severity, 'error')
  })

  it('includes ingest and unacknowledged job error counts', () => {
    const items = collectNeedsAttentionItems(BASE_SYSTEM, {
      ingestErrorCount: 4,
      unackJobErrorCount: 2,
    })
    assert.ok(items.some(i => i.id === 'ingest-errors'))
    assert.ok(items.some(i => i.id === 'scheduler-errors'))
  })

  it('flags stale NVD and overdue backup', () => {
    const items = collectNeedsAttentionItems({
      ...BASE_SYSTEM,
      last_nvd_sync_age_seconds: 20000,
      last_backup_age_seconds: 50000,
    })
    assert.ok(items.some(i => i.id === 'nvd-stale' && i.severity === 'error' && i.pageId === 'scheduler'))
    assert.ok(items.some(i => i.id === 'backup-stale'))
  })

  it('flags empty and stale SigmaHQ index', () => {
    const emptyItems = collectNeedsAttentionItems({
      ...BASE_SYSTEM,
      feeds: {
        ...BASE_SYSTEM.feeds,
        sigmahq_index: { enabled: true, rules_active: 0, age_seconds: null },
      },
    })
    assert.ok(emptyItems.some(i => i.id === 'sigmahq-empty' && i.pageId === 'feedhealth'))

    const staleItems = collectNeedsAttentionItems({
      ...BASE_SYSTEM,
      feeds: {
        ...BASE_SYSTEM.feeds,
        sigmahq_index: {
          enabled: true,
          rules_active: 1200,
          age_seconds: 15 * 24 * 3600,
        },
      },
    })
    assert.ok(staleItems.some(i => i.id === 'sigmahq-stale' && i.pageId === 'feedhealth'))

    const healthy = collectNeedsAttentionItems({
      ...BASE_SYSTEM,
      feeds: {
        ...BASE_SYSTEM.feeds,
        sigmahq_index: { enabled: true, rules_active: 100, age_seconds: 3600 },
      },
    })
    assert.equal(healthy.filter(i => i.id.startsWith('sigmahq')).length, 0)
  })
})
