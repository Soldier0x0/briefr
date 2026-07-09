import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { formatSinceHoursLabel } from './morningBriefFormat.js'

describe('morningBriefFormat', () => {
  it('formats singular hour', () => {
    assert.equal(formatSinceHoursLabel(1), '1 hour')
  })

  it('formats plural hours', () => {
    assert.equal(formatSinceHoursLabel(2), '2 hours')
    assert.equal(formatSinceHoursLabel(24), '24 hours')
  })

  it('defaults invalid values to 24 hours', () => {
    assert.equal(formatSinceHoursLabel(undefined), '24 hours')
    assert.equal(formatSinceHoursLabel(0), '24 hours')
  })
})
