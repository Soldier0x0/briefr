import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { bytesChartScale } from '../formatters.js'
import {
  backupChartPoints,
  backupChartTickLabel,
  backupTooltipModel,
} from './backupChartUtils.js'

describe('backupChartTickLabel', () => {
  it('uses distinct date ticks for age-encrypted archives', () => {
    const a = backupChartTickLabel('briefr-20260717T202746Z.tar.gz.age')
    const b = backupChartTickLabel('briefr-20260717T120000Z.tar.gz.age')
    const c = backupChartTickLabel('briefr-20260716T202746Z.tar.gz.age')
    assert.equal(a, '07-17')
    assert.equal(b, '07-17')
    assert.equal(c, '07-16')
    assert.notEqual(a, c)
  })

  it('does not collapse archives on the same day to one label', () => {
    const labels = [
      'briefr-20260717T202746Z.tar.gz.age',
      'briefr-20260717T180000Z.tar.gz.age',
      'briefr-20260715T090000Z.tar.gz.age',
    ].map(backupChartTickLabel)
    assert.equal(labels[0], '07-17')
    assert.equal(labels[1], '07-17')
    assert.equal(labels[2], '07-15')
    assert.ok(labels.every((label) => !label.includes('…')))
  })

  it('handles legacy briefr-backup- prefix', () => {
    assert.equal(
      backupChartTickLabel('briefr-backup-20260710T010203Z.tar.gz'),
      '07-10',
    )
  })
})

describe('backupChartPoints', () => {
  it('tolerates null rows and missing size_bytes', () => {
    const scale = bytesChartScale([1024])
    const points = backupChartPoints([null, { filename: 'briefr-20260718T120000Z.tar.gz.age' }], scale)
    assert.equal(points.length, 2)
    assert.equal(points[0].size, 0)
    assert.equal(points[0].filename, 'backup-0')
    assert.equal(points[1].tickLabel, '07-18')
  })

  it('uses unique index keys so far-left and far-right never share an X category', () => {
    const rows = [
      { filename: 'briefr-20260717T202746Z.tar.gz.age', size_bytes: 50.3 * 1024 * 1024 },
      { filename: 'briefr-20260717T120000Z.tar.gz.age', size_bytes: 48.0 * 1024 * 1024 },
      { filename: 'briefr-20260718T010000Z.tar.gz.age', size_bytes: 95.4 * 1024 * 1024 },
    ]
    const scale = bytesChartScale(rows.map((r) => r.size_bytes))
    const points = backupChartPoints(rows, scale)

    assert.deepEqual(points.map((p) => p.pointKey), [0, 1, 2])
    assert.equal(new Set(points.map((p) => p.pointKey)).size, rows.length)

    // Simulate Recharts axis tooltip payload for far-left vs far-right.
    const leftTip = backupTooltipModel([{ payload: points[0] }])
    const rightTip = backupTooltipModel([{ payload: points[2] }])
    assert.equal(leftTip.filename, rows[0].filename)
    assert.equal(rightTip.filename, rows[2].filename)
    assert.notEqual(leftTip.filename, rightTip.filename)
    assert.ok(Math.abs(leftTip.size - 50.3) < 1e-9)
    assert.ok(Math.abs(rightTip.size - 95.4) < 1e-9)
  })
})

describe('backupTooltipModel', () => {
  it('returns null when payload is empty', () => {
    assert.equal(backupTooltipModel([]), null)
    assert.equal(backupTooltipModel(null), null)
  })
})
