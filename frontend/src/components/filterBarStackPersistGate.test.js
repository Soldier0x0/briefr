import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const FILTER_BAR = path.join(ROOT, 'components', 'FilterBar.jsx')
const APP = path.join(ROOT, 'App.jsx')

describe('FEED stack filter persist gate', () => {
  it('does not persist throwaway STACK // input to My Stack', () => {
    const src = fs.readFileSync(FILTER_BAR, 'utf8')
    assert.equal(
      src.includes('saveUserStack'),
      false,
      'FilterBar.jsx must not call saveUserStack — FEED STACK // is throwaway',
    )
  })

  it('does not auto-seed FEED filters.stack from My Stack on load', () => {
    const src = fs.readFileSync(APP, 'utf8')
    assert.equal(
      src.includes('setFilters((prev) => (prev.stack ? prev : { ...prev, stack:'),
      false,
      'App.jsx must not seed filters.stack from getSavedStack / briefr-stack-loaded',
    )
  })
})
