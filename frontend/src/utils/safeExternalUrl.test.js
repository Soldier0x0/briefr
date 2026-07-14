import test from 'node:test'
import assert from 'node:assert/strict'
import { safeExternalUrl } from './safeExternalUrl.js'

test('safeExternalUrl allows http and https', () => {
  assert.equal(safeExternalUrl('https://example.com/x'), 'https://example.com/x')
  assert.equal(safeExternalUrl('http://example.com'), 'http://example.com/')
})

test('safeExternalUrl blocks javascript and relative URLs', () => {
  assert.equal(safeExternalUrl('javascript:alert(1)'), null)
  assert.equal(safeExternalUrl('/local/path'), null)
  assert.equal(safeExternalUrl(''), null)
  assert.equal(safeExternalUrl(null), null)
})
