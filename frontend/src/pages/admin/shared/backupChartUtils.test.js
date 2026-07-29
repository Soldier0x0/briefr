import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { bytesChartScale } from '../formatters.js'
import {
  backupChartOrdinalLabel,
  backupChartPoints,
  backupSizeRows,
  backupTooltipModel,
} from './backupChartUtils.js'

describe('backupChartOrdinalLabel', () => {
  it('returns 1-based index without dates', () => {
    assert.equal(backupChartOrdinalLabel(0, 30), '1')
    assert.equal(backupChartOrdinalLabel(29, 30), '30')
  })
})

describe('backupSizeRows', () => {
  it('table rows are newest-first while chart rows are oldest-first', () => {
    const backups = [
      { filename: 'a', created_at: '2026-07-20T00:00:00Z', size_bytes: 1 },
      { filename: 'b', created_at: '2026-07-23T00:00:00Z', size_bytes: 2 },
    ]
    const { chartRows, tableRows } = backupSizeRows(backups)
    assert.equal(tableRows[0].filename, 'b')
    assert.equal(chartRows[0].filename, 'a')
  })

  it('limits chart to 30 archives', () => {
    const backups = Array.from({ length: 40 }, (_, i) => ({
      filename: `briefr-${i}.tar.gz`,
      created_at: `2026-07-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      size_bytes: 1024,
    }))
    const { chartRows, tableRows } = backupSizeRows(backups)
    assert.equal(chartRows.length, 30)
    assert.equal(tableRows.length, 30)
  })
})

describe('backup chart scale ticks', () => {
  it('formats Y ticks as integers', () => {
    const scale = bytesChartScale([50.3 * 1024 * 1024, 95.4 * 1024 * 1024])
    assert.equal(scale.formatTick(50.3), '50 MB')
    assert.ok(!scale.formatTick(50.3).includes('.0'))
  })
})

describe('backupChartPoints', () => {
  it('tolerates null rows and missing size_bytes', () => {
    const scale = bytesChartScale([1024])
    const points = backupChartPoints([null, { filename: 'briefr-20260718T120000Z.tar.gz.age' }], scale)
    assert.equal(points.length, 2)
    assert.equal(points[0].size, 0)
    assert.equal(points[0].filename, 'backup-0')
    assert.equal(points[0].tickLabel, '1')
    assert.equal(points[1].tickLabel, '2')
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
    assert.deepEqual(points.map((p) => p.tickLabel), ['1', '2', '3'])
    assert.equal(new Set(points.map((p) => p.pointKey)).size, rows.length)

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
