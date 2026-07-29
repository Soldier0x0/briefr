import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { useBusyGuard } from './useBusyGuard.js'

describe('useBusyGuard', () => {
  it('exports a hook function', () => {
    assert.equal(typeof useBusyGuard, 'function')
  })
})
