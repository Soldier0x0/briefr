import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { formatTimeAgo } from './timeAgo.js'

describe('formatTimeAgo', () => {
  it('formats minutes', () => {
    const now = Date.parse('2026-08-24T12:00:00Z')
    assert.equal(formatTimeAgo('2026-08-24T11:50:00Z', now), '10m ago')
  })
})
