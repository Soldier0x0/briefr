import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { toggleChipSelection } from './toggleChipSelection.js'

describe('toggleChipSelection', () => {
  it('selects when inactive', () => {
    assert.equal(toggleChipSelection(null, 6), 6)
  })

  it('clears when re-clicking active', () => {
    assert.equal(toggleChipSelection(6, 6, null), null)
  })

  it('switches to a different value without clearing', () => {
    assert.equal(toggleChipSelection(6, 8, null), 8)
  })

  it('uses custom cleared value', () => {
    assert.equal(toggleChipSelection('kev', 'kev', 'all'), 'all')
  })
})
