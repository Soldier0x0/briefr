import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { shouldIgnoreGlobalShortcut } from './keyboardScope.js'

describe('keyboardScope', () => {
  it('shouldIgnoreGlobalShortcut when IME composing', () => {
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: true, target: null }), true)
  })

  it('shouldIgnoreGlobalShortcut allows navigation keys when not composing', () => {
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: false, target: null }), false)
  })
})
