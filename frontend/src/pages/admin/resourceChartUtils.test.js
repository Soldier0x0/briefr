import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { resourceChartPoints } from './resourceChartUtils.js'

describe('resourceChartPoints', () => {
  it('uses unique index keys when HH:MM labels collide across days', () => {
    const series = [
      { ts: '2026-07-16T14:30:00Z', briefr_rss_bytes: 50 * 1024 * 1024 },
      { ts: '2026-07-17T14:30:00Z', briefr_rss_bytes: 80 * 1024 * 1024 },
      { ts: '2026-07-18T14:30:00Z', briefr_rss_bytes: 95 * 1024 * 1024 },
    ]
    const { data, scale } = resourceChartPoints(series, ['briefr_rss_bytes'])
    assert.deepEqual(data.map((row) => row.pointKey), [0, 1, 2])
    assert.deepEqual(data.map((row) => row.tsLabel), ['14:30', '14:30', '14:30'])
    assert.equal(scale.unit, 'MB')
    assert.ok(data[0].briefr_rss_bytes < data[2].briefr_rss_bytes)
    assert.notEqual(data[0].tsFull, data[2].tsFull)
  })

  it('leaves non-byte series in native units', () => {
    const series = [
      { ts: '2026-07-18T10:00:00Z', briefr_cpu_pct: 12.5 },
      { ts: '2026-07-18T10:01:00Z', briefr_cpu_pct: 18.0 },
    ]
    const { data, scale } = resourceChartPoints(series, ['briefr_cpu_pct'])
    assert.equal(scale, null)
    assert.equal(data[0].briefr_cpu_pct, 12.5)
    assert.equal(data[1].briefr_cpu_pct, 18.0)
  })
})
