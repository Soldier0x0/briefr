import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectType,
  lookupCompatibleIoc,
  normalizeIocValue,
  parseError,
  verdictInfo,
} from './iocUtils.js'
import { IOC_NOT_FOUND_IN_DATABASES } from '../../utils/iocLookupMessages.js'

describe('iocUtils', () => {
  it('detects IP, hash, and domain indicators', () => {
    assert.equal(detectType('8.8.8.8'), 'ip')
    assert.equal(detectType('A'.repeat(64)), 'hash')
    assert.equal(detectType('https://plugins.trac.wordpress.org/browser/foo'), 'domain')
    assert.equal(detectType('not a valid indicator'), null)
  })

  it('normalizes domains from URLs and hashes to lowercase', () => {
    assert.equal(normalizeIocValue('https://Example.COM:443/path?x=1', 'domain'), 'example.com')
    assert.equal(normalizeIocValue('ABCDEF0123456789ABCDEF0123456789', 'hash'), 'abcdef0123456789abcdef0123456789')
  })

  it('maps graph url IocKind onto lookup-compatible domain', () => {
    assert.deepEqual(
      lookupCompatibleIoc('https://evil.example/x', 'url'),
      { type: 'domain', value: 'evil.example' },
    )
    assert.deepEqual(lookupCompatibleIoc('8.8.8.8', 'ip'), { type: 'ip', value: '8.8.8.8' })
    assert.deepEqual(lookupCompatibleIoc('deadbeef', 'hash'), { type: 'hash', value: 'deadbeef' })
  })

  it('maps lookup errors to operator-safe messages', () => {
    assert.equal(parseError({ status: 404 }), IOC_NOT_FOUND_IN_DATABASES)
    assert.equal(parseError({ status: 422, message: 'Invalid domain' }), 'Invalid domain')
  })

  it('summarizes verdicts from malicious engine ratios', () => {
    assert.equal(verdictInfo(0, 0).label, 'unknown')
    assert.equal(verdictInfo(1, 20).label, 'clean')
    assert.equal(verdictInfo(3, 20).label, 'suspicious')
    assert.equal(verdictInfo(11, 20).label, 'likely malicious')
  })
})
