import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { shouldCloseDrawerOnCveUrlRemoval } from './drawerUrlSync.js'

describe('drawerUrlSync', () => {
  it('does not close before ?cve= lands on optimistic open', () => {
    assert.equal(shouldCloseDrawerOnCveUrlRemoval(false, null), false)
    assert.equal(shouldCloseDrawerOnCveUrlRemoval(false, ''), false)
  })

  it('closes when ?cve= is removed after being present', () => {
    assert.equal(shouldCloseDrawerOnCveUrlRemoval(true, null), true)
    assert.equal(shouldCloseDrawerOnCveUrlRemoval(true, ''), true)
  })

  it('stays open while ?cve= is present', () => {
    assert.equal(shouldCloseDrawerOnCveUrlRemoval(true, 'CVE-2024-1234'), false)
  })
})
