import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { daysUntilDue, kevDueBucket, parseDueDate } from './kevDeadline.js'

describe('parseDueDate', () => {
  it('parses YYYY-MM-DD at UTC noon', () => {
    const due = parseDueDate('2099-06-15')
    assert.ok(due)
    assert.equal(due.toISOString(), '2099-06-15T12:00:00.000Z')
  })

  it('returns null for empty or invalid values', () => {
    assert.equal(parseDueDate(''), null)
    assert.equal(parseDueDate('not-a-date'), null)
  })
})

describe('daysUntilDue', () => {
  it('returns null when due date is missing', () => {
    assert.equal(daysUntilDue(null), null)
    assert.equal(daysUntilDue(''), null)
  })

  it('uses UTC noon anchor consistent with histogram buckets', () => {
    const today = new Date()
    today.setUTCHours(12, 0, 0, 0)
    const iso = today.toISOString().slice(0, 10)
    assert.equal(daysUntilDue(iso), 0)
  })
})

describe('kevDueBucket', () => {
  it('maps day offsets to bucket keys', () => {
    assert.equal(kevDueBucket(-1), 'overdue')
    assert.equal(kevDueBucket(3), '0-7')
    assert.equal(kevDueBucket(10), '8-14')
    assert.equal(kevDueBucket(20), '15-30')
    assert.equal(kevDueBucket(45), '31+')
    assert.equal(kevDueBucket(null), '31+')
  })
})
