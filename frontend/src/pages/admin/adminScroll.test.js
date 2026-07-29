import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { scrollAdminTabToTop } from './adminScroll.js'

describe('scrollAdminTabToTop', () => {
  it('is exported as a function', () => {
    assert.equal(typeof scrollAdminTabToTop, 'function')
  })
})
