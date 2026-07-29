import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { formatClientAddresses, formatClientAddressLabel } from './ipDisplay.js'

describe('formatClientAddresses', () => {
  it('parses IPv4', () => {
    assert.deepEqual(formatClientAddresses('192.168.1.10'), {
      ipv4: '192.168.1.10',
      ipv6: 'N/A',
    })
  })

  it('parses IPv6', () => {
    assert.deepEqual(formatClientAddresses('2001:db8::1'), {
      ipv4: 'N/A',
      ipv6: '2001:db8::1',
    })
  })

  it('parses IPv4-mapped IPv6', () => {
    assert.deepEqual(formatClientAddresses('::ffff:10.0.0.5'), {
      ipv4: '10.0.0.5',
      ipv6: 'N/A',
    })
  })

  it('returns N/A for empty input', () => {
    assert.deepEqual(formatClientAddresses(''), { ipv4: 'N/A', ipv6: 'N/A' })
    assert.deepEqual(formatClientAddresses(null), { ipv4: 'N/A', ipv6: 'N/A' })
  })
})

describe('formatClientAddressLabel', () => {
  it('labels IPv4 only', () => {
    assert.equal(formatClientAddressLabel('8.8.8.8'), 'IPv4 8.8.8.8')
  })

  it('labels IPv6 only', () => {
    assert.equal(formatClientAddressLabel('fe80::1'), 'IPv6 fe80::1')
  })
})
