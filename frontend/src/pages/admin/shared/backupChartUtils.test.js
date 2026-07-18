import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { bytesChartScale } from '../formatters.js'
import { backupChartPoints, backupChartTickLabel } from './backupChartUtils.js'

describe('backupChartTickLabel', () => {
  it('uses distinct timestamp ticks for age-encrypted archives', () => {
    const a = backupChartTickLabel('briefr-20260717T202746Z.tar.gz.age')
    const b = backupChartTickLabel('briefr-20260717T120000Z.tar.gz.age')
    const c = backupChartTickLabel('briefr-20260716T202746Z.tar.gz.age')
    assert.equal(a, '07-17 20:27')
    assert.equal(b, '07-17 12:00')
    assert.equal(c, '07-16 20:27')
    assert.notEqual(a, b)
    assert.notEqual(a, c)
  })

  it('does not collapse every archive to the same truncated prefix', () => {
    const labels = [
      'briefr-20260717T202746Z.tar.gz.age',
      'briefr-20260717T180000Z.tar.gz.age',
      'briefr-20260715T090000Z.tar.gz.age',
    ].map(backupChartTickLabel)
    assert.equal(new Set(labels).size, labels.length)
    assert.ok(labels.every((label) => !label.includes('…')))
  })

  it('handles legacy briefr-backup- prefix', () => {
    assert.equal(
      backupChartTickLabel('briefr-backup-20260710T010203Z.tar.gz'),
      '07-10 01:02',
    )
  })
})

describe('backupChartPoints', () => {
  it('keeps unique pointKey values even when tick labels were previously colliding', () => {
    const rows = [
      { filename: 'briefr-20260717T202746Z.tar.gz.age', size_bytes: 50.3 * 1024 * 1024 },
      { filename: 'briefr-20260717T120000Z.tar.gz.age', size_bytes: 48.0 * 1024 * 1024 },
      { filename: 'briefr-20260716T202746Z.tar.gz.age', size_bytes: 47.5 * 1024 * 1024 },
    ]
    const scale = bytesChartScale(rows.map((r) => r.size_bytes))
    const points = backupChartPoints(rows, scale)
    assert.equal(new Set(points.map((p) => p.pointKey)).size, rows.length)
    assert.deepEqual(
      points.map((p) => p.filename),
      rows.map((r) => r.filename),
    )
    assert.ok(Math.abs(points[0].size - 50.3) < 1e-9)
    assert.ok(Math.abs(points[1].size - 48.0) < 1e-9)
  })
})
