import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

function fmtSavings(rec) {
  const parts = []
  const est = rec?.estimated_savings || {}
  if (est.bytes) parts.push(`disk:${est.bytes}`)
  if (est.rows) parts.push(`rows:${est.rows}`)
  if (est.requests_per_day) parts.push(`rpd:${est.requests_per_day}`)
  return parts.join('|')
}

describe('efficiency report helpers', () => {
  it('formats estimated savings from recommendation payload', () => {
    const label = fmtSavings({
      estimated_savings: { bytes: 1_200_000_000, requests_per_day: 15000 },
    })
    assert.match(label, /disk:1200000000/)
    assert.match(label, /rpd:15000/)
  })

  it('returns empty string when no savings', () => {
    assert.equal(fmtSavings({ estimated_savings: {} }), '')
  })
})
