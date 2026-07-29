import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

describe('opsChartsRecharts source guards', () => {
  it('ingest chart module does not use minute-based durationChartScale', () => {
    const src = readFileSync(join(__dirname, 'opsChartsRecharts.jsx'), 'utf8')
    assert.ok(src.includes('ingestDurationChartScale'))
    assert.ok(!src.includes('durationChartScale'))
  })
})
