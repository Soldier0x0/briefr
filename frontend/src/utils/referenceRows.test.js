import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { buildReferenceRow, buildReferenceRows } from './referenceRows.js'

describe('buildReferenceRow', () => {
  it('derives Adobe bulletin title from URL path', () => {
    const row = buildReferenceRow(
      'https://helpx.adobe.com/security/products/acrobat/apsb26-68.html',
      { cveId: 'CVE-2026-1234' },
    )
    assert.equal(row.vendor, 'Adobe')
    assert.match(row.title, /Apsb26 68|APSB26-68|apsb26/i)
  })

  it('labels CISA KEV catalogue references', () => {
    const row = buildReferenceRow(
      'https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
      { cveId: 'CVE-2024-0001', isKev: true },
    )
    assert.equal(row.vendor, 'CISA')
    assert.equal(row.title, 'Known Exploited Vulnerabilities')
  })

  it('preserves original URL on row', () => {
    const url = 'https://nvd.nist.gov/vuln/detail/CVE-2024-0001'
    const row = buildReferenceRow(url, { cveId: 'CVE-2024-0001' })
    assert.equal(row.url, url)
  })
})

describe('buildReferenceRows', () => {
  it('drops non-http(s) URLs from feed data', () => {
    const rows = buildReferenceRows([
      'https://example.com/advisory',
      'javascript:alert(1)',
      '/relative/path',
    ])
    assert.equal(rows.length, 1)
    assert.equal(rows[0].url, 'https://example.com/advisory')
  })
})
