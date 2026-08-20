import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { shouldRefitAfterStructuralChange } from './investigateCameraPolicy.js'

describe('shouldRefitAfterStructuralChange', () => {
  it('refits when versions differ', () => {
    assert.equal(shouldRefitAfterStructuralChange({
      structuralVersion: 3,
      lastFitVersion: 2,
    }), true)
  })

  it('skips when already fitted for this version', () => {
    assert.equal(shouldRefitAfterStructuralChange({
      structuralVersion: 4,
      lastFitVersion: 4,
    }), false)
  })
})
