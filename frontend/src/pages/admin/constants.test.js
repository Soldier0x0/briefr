import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { NAV } from './constants.js'

const here = dirname(fileURLToPath(import.meta.url))

describe('admin reports nav', () => {
  it('includes Daily brief under REPORTS', () => {
    const reports = NAV.find(s => s.section === 'REPORTS')
    assert.ok(reports)
    assert.equal(reports.items.some(i => i.id === 'dailybrief'), true)
  })

  it('keeps watchlist trigger density class', () => {
    const src = readFileSync(join(here, 'WatchlistPage.jsx'), 'utf8')
    assert.match(src, /admin-watchlist-triggers/)
    assert.match(src, /not the daily brief/)
  })
})
