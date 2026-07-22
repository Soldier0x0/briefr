import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { deltaToneClass } from './statsRowDelta.js'

describe('deltaToneClass', () => {
  it('treats positive PATCHES (better-up) as good', () => {
    assert.equal(deltaToneClass(3, 'better-up'), 'stat-delta--down')
  })
  it('treats positive CRITICAL (worse-up) as bad', () => {
    assert.equal(deltaToneClass(3, 'worse-up'), 'stat-delta--up')
  })
  it('treats negative better-up as bad', () => {
    assert.equal(deltaToneClass(-2, 'better-up'), 'stat-delta--up')
  })
})
