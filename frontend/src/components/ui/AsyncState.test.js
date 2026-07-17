import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const src = await import('node:fs/promises').then(fs =>
  fs.readFile(new URL('./AsyncState.jsx', import.meta.url), 'utf8'),
)

describe('AsyncState error surfacing (F5.6)', () => {
  it('surfaces errors on the no-data path, not gated solely on the caller `empty` flag', () => {
    // The old bug: `if (error && empty)` let a first-load error with empty=false
    // fall through to render an empty body silently.
    assert.doesNotMatch(src, /if\s*\(\s*error\s*&&\s*empty\s*\)/)
    assert.match(src, /error\s*&&\s*!hasData/)
  })

  it('derives hasData internally instead of trusting the caller heuristic', () => {
    assert.match(src, /const hasData\s*=/)
  })

  it('keeps existing data on a refresh error with a non-blocking compact notice', () => {
    assert.match(src, /<ErrorState[^>]*compact/)
  })
})
