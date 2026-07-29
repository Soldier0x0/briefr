import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { clearStatsTimelineCache } from './useStatsTimeline.js'

describe('useStatsTimeline cache', () => {
  it('exports clearStatsTimelineCache helper', () => {
    clearStatsTimelineCache()
    assert.equal(typeof clearStatsTimelineCache, 'function')
  })
})
