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
    assert.ok(items.some(i => i.id === 'nvd-stale' && i.severity === 'error'))
    assert.ok(items.some(i => i.id === 'backup-stale'))
  })
})
