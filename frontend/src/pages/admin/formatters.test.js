import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { bytesChartScale, durationChartScale, fmtBytes, fmtDur } from './formatters.js'

describe('fmtDur', () => {
  it('formats sub-minute durations with s unit', () => {
    assert.equal(fmtDur(12.4), '12.4 s')
    assert.equal(fmtDur(0.5), '0.5 s')
  })

  it('formats minute-range durations with min unit', () => {
    assert.equal(fmtDur(60), '1.0 min')
    assert.equal(fmtDur(168), '2.8 min')
  })

  it('formats hour-range durations with h unit', () => {
    assert.equal(fmtDur(4320), '1.2 h')
  })

  it('returns em dash for nullish input', () => {
    assert.equal(fmtDur(null), '—')
    assert.equal(fmtDur(undefined), '—')
  })
})

describe('fmtBytes', () => {
  it('formats zero and small values', () => {
    assert.equal(fmtBytes(0), '0 B')
    assert.equal(fmtBytes(512), '512.0 B')
  })

  it('steps through binary units', () => {
    assert.equal(fmtBytes(1536), '1.5 KB')
    assert.equal(fmtBytes(1048576), '1.0 MB')
  })
})

describe('bytesChartScale', () => {
  it('plots in one display unit so axis ticks match tooltip values', () => {
    const sizes = [
      50.3 * 1024 * 1024,
      50.1 * 1024 * 1024,
      95.4 * 1024 * 1024,
    ]
    const scale = bytesChartScale(sizes)
    assert.equal(scale.unit, 'MB')
    assert.equal(scale.format(scale.toDisplay(sizes[0])), '50.3 MB')
    assert.equal(scale.domainMax, 100)
    // Mid-grid at domain/2 is 50.0 MB — a 50.3 MB point sits on that line,
    // not on a misleading "47.7 MB" label from raw-byte nice ticks.
    assert.equal(scale.format(scale.domainMax / 2), '50.0 MB')
    assert.ok(Math.abs(scale.toDisplay(sizes[0]) - 50.3) < 1e-9)
  })

  it('falls back safely for empty or zero series', () => {
    const scale = bytesChartScale([])
    assert.equal(scale.unit, 'B')
    assert.equal(scale.domainMax, 1)
    assert.equal(scale.format(0), '0.0 B')
  })
})

describe('durationChartScale', () => {
  it('keeps one unit across the axis when values span the minute boundary', () => {
    const scale = durationChartScale([20, 70, 180])
    assert.equal(scale.unit, 'min')
    assert.equal(scale.format(scale.toDisplay(70)), '1.2 min')
    assert.equal(scale.format(scale.toDisplay(45)), '0.8 min')
    // No mixed "45.0 s" / "1.5 min" tick pair on the same axis.
    assert.ok(!scale.format(scale.toDisplay(45)).includes(' s'))
  })

  it('stays in seconds when the whole series is sub-minute', () => {
    const scale = durationChartScale([12.4, 30, 55])
    assert.equal(scale.unit, 's')
    assert.equal(scale.format(scale.toDisplay(12.4)), '12.4 s')
  })
})
