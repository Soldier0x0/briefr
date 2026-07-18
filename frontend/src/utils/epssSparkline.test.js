import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  EPSS_CONTEXT_DAYS,
  epssSparklineWindowSpec,
  filterEpssHistoryToDays,
} from './epssSparkline.js'

describe('epssSparklineWindowSpec', () => {
  it('uses labeled 7d context for sub-week windows (daily EPSS)', () => {
    for (const hours of [6, 12, 24, 48]) {
      const spec = epssSparklineWindowSpec(hours)
      assert.equal(spec.days, EPSS_CONTEXT_DAYS)
      assert.equal(spec.isContext, true)
      assert.equal(spec.columnLabel, '7d context')
      assert.match(spec.columnTooltip, /once per day/i)
      assert.match(spec.columnTooltip, /Delta/i)
    }
  })

  it('uses window-matched trend labels from 7 days upward', () => {
    assert.deepEqual(
      {
        days: epssSparklineWindowSpec(168).days,
        isContext: epssSparklineWindowSpec(168).isContext,
        columnLabel: epssSparklineWindowSpec(168).columnLabel,
      },
      { days: 7, isContext: false, columnLabel: '7d trend' },
    )
    assert.equal(epssSparklineWindowSpec(720).columnLabel, '30d trend')
    assert.equal(epssSparklineWindowSpec(720).isContext, false)
  })

  it('falls back to 7d context for invalid hours', () => {
    const spec = epssSparklineWindowSpec(NaN)
    assert.equal(spec.days, EPSS_CONTEXT_DAYS)
    assert.equal(spec.isContext, true)
  })
})

describe('filterEpssHistoryToDays', () => {
  it('keeps only points inside the trailing day window', () => {
    const asOf = new Date('2026-07-18T15:00:00Z')
    const history = [
      { date: '2026-07-01', score: 0.1 },
      { date: '2026-07-12', score: 0.2 },
      { date: '2026-07-15', score: 0.3 },
      { date: '2026-07-18', score: 0.4 },
    ]
    const filtered = filterEpssHistoryToDays(history, 7, { asOf })
    assert.deepEqual(
      filtered.map((p) => p.date),
      ['2026-07-12', '2026-07-15', '2026-07-18'],
    )
  })

  it('returns empty array for non-array history', () => {
    assert.deepEqual(filterEpssHistoryToDays(null, 7), [])
  })
})
