import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDatetimeLocalFromParts,
  formatDatetimeDisplay,
  partsFromDatetimeLocal,
  toDatetimeLocalValue,
} from '../components/timeWindowDateUtils.js'

describe('timeWindowDateUtils', () => {
  it('formats display as DD-MM-YY HH:mm:ss', () => {
    const value = toDatetimeLocalValue(new Date(2026, 6, 16, 14, 30, 45))
    assert.equal(formatDatetimeDisplay(value), '16-07-26 14:30:45')
  })

  it('round-trips parts through datetime-local value', () => {
    const value = buildDatetimeLocalFromParts({
      day: 31,
      month: 1,
      year: 2026,
      hours: 9,
      minutes: 5,
      seconds: 2,
    })
    assert.equal(value, '2026-01-31T09:05:02')
    const parts = partsFromDatetimeLocal(value)
    assert.equal(parts.day, 31)
    assert.equal(parts.month, 1)
    assert.equal(parts.year, 2026)
    assert.equal(parts.hours, 9)
    assert.equal(parts.minutes, 5)
    assert.equal(parts.seconds, 2)
  })

  it('clamps invalid day when month changes', () => {
    const value = buildDatetimeLocalFromParts({
      day: 31,
      month: 2,
      year: 2026,
      hours: 0,
      minutes: 0,
      seconds: 0,
    })
    assert.equal(value, '2026-02-28T00:00:00')
  })
})
