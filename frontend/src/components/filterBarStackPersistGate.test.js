import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const FILTER_BAR = path.join(ROOT, 'components', 'FilterBar.jsx')

describe('FEED stack filter persist gate', () => {
  it('does not persist throwaway STACK // input to My Stack', () => {
    const src = fs.readFileSync(FILTER_BAR, 'utf8')
    assert.equal(
      src.includes('saveUserStack'),
      false,
      'FilterBar.jsx must not call saveUserStack — FEED STACK // is throwaway',
    )
  })
})
