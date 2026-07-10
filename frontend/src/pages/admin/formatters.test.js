import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { fmtBytes, fmtDur } from './formatters.js'

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
