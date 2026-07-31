import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  parseFeedQuery,
  parsedQueryToFilters,
  removeChipFromQuery,
  toggleQueryToken,
} from './feedQueryParser.js'

describe('feedQueryParser', () => {
  it('parses vendor + kev with plus', () => {
    const parsed = parseFeedQuery('amazon + kev')
    assert.equal(parsed.vendors.includes('Amazon'), true)
    assert.equal(parsed.kev_only, true)
    assert.equal(parsed.search, '')
    const filters = parsedQueryToFilters(parsed)
    assert.equal(filters.vendors, 'Amazon')
    assert.equal(filters.kev_only, true)
  })

  it('parses comma OR vendors', () => {
    const parsed = parseFeedQuery('microsoft,oracle kev')
    assert.deepEqual(parsed.vendors.sort(), ['Microsoft', 'Oracle'].sort())
    assert.equal(parsed.kev_only, true)
  })

  it('parses exclude vendor with minus', () => {
    const parsed = parseFeedQuery('kev -linux')
    assert.equal(parsed.kev_only, true)
    assert.equal(parsed.excludeVendors.includes('Linux'), true)
  })

  it('parses phrase kevs from vendor', () => {
    const parsed = parseFeedQuery('kevs from apache')
    assert.equal(parsed.vendors.includes('Apache'), true)
    assert.equal(parsed.kev_only, true)
  })

  it('parses vendor kevs phrase', () => {
    const parsed = parseFeedQuery('apache kevs')
    assert.equal(parsed.vendors.includes('Apache'), true)
    assert.equal(parsed.kev_only, true)
  })

  it('parses severity comma OR', () => {
    const parsed = parseFeedQuery('critical,high apache')
    assert.deepEqual(parsed.severities.sort(), ['CRITICAL', 'HIGH'].sort())
    assert.equal(parsed.vendors.includes('Apache'), true)
    const filters = parsedQueryToFilters(parsed)
    assert.equal(filters.severity_list, 'CRITICAL,HIGH')
    assert.equal(filters.severity, null)
  })

  it('parses prefixed qualifiers', () => {
    const parsed = parseFeedQuery('vendor:apache is:kev sev:critical')
    assert.equal(parsed.vendors.includes('Apache'), true)
    assert.equal(parsed.kev_only, true)
    assert.deepEqual(parsed.severities, ['CRITICAL'])
  })

  it('parses CVE id exactly', () => {
    const parsed = parseFeedQuery('CVE-2024-3094')
    assert.equal(parsed.cve_id, 'CVE-2024-3094')
    assert.equal(parsed.search, 'CVE-2024-3094')
  })

  it('parses technique and epss and date', () => {
    const parsed = parseFeedQuery('t:T1059 epss:0.2 date:2026-07-15')
    assert.equal(parsed.technique, 'T1059')
    assert.equal(parsed.epss_min, 0.2)
    assert.equal(parsed.published_on, '2026-07-15')
  })

  it('parses quoted phrase with kev', () => {
    const parsed = parseFeedQuery('"log4j" kev')
    assert.equal(parsed.search, 'log4j')
    assert.equal(parsed.kev_only, true)
    assert.equal(parsed.chips.some((c) => c.type === 'search'), true)
  })

  it('parses palo alto alias', () => {
    const parsed = parseFeedQuery('palo alto kev')
    assert.equal(parsed.vendors.includes('Paloaltonetworks'), true)
  })

  it('leaves unknown tokens as free text', () => {
    const parsed = parseFeedQuery('rce nginx kev')
    assert.equal(parsed.kev_only, true)
    assert.equal(parsed.search, 'rce nginx')
  })

  it('toggleQueryToken adds and removes kev', () => {
    const withKev = toggleQueryToken('apache', 'kev')
    assert.match(withKev, /kev/i)
    const without = toggleQueryToken(withKev, 'kev')
    assert.doesNotMatch(without, /\bkev\b/i)
  })

  it('removeChipFromQuery strips vendor token', () => {
    const next = removeChipFromQuery('apache kev', { type: 'vendor', label: 'Apache', value: 'Apache' })
    assert.equal(next, 'kev')
  })
})
