import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  classifyRemediationReference,
  pickPrimaryRemediationReference,
} from './patchReferences.js'

const CVE = 'CVE-2024-1234'

describe('classifyRemediationReference', () => {
  it('CVE-specific vendor security advisory ranks highest', () => {
    const r = classifyRemediationReference(
      'https://msrc.microsoft.com/update-guide/vulnerability/CVE-2024-1234',
      { cveId: CVE, isKev: true },
    )
    assert.equal(r.label, 'Vendor advisory')
    assert.ok(r.score >= 80)
  })

  it('generic vendor homepage is vendor reference — not advisory', () => {
    const r = classifyRemediationReference('https://www.microsoft.com/en-us/', {
      cveId: CVE,
    })
    assert.equal(r.label, 'Vendor reference')
    assert.ok(r.score < 80)
  })

  it('NVD CVE page outranks generic vendor doc', () => {
    const nvd = classifyRemediationReference(
      `https://nvd.nist.gov/vuln/detail/${CVE}`,
      { cveId: CVE },
    )
    const vendorDoc = classifyRemediationReference(
      'https://www.adobe.com/support/documentation.html',
      { cveId: CVE },
    )
    assert.equal(nvd.label, 'NVD reference')
    assert.ok(nvd.score > vendorDoc.score)
  })

  it('CISA KEV catalogue URL scores as CISA guidance', () => {
    const r = classifyRemediationReference(
      'https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
      { cveId: CVE, isKev: true },
    )
    assert.equal(r.label, 'CISA guidance')
    assert.ok(r.score >= 85)
  })

  it('GitHub security advisory differs from generic repo', () => {
    const advisory = classifyRemediationReference(
      'https://github.com/org/repo/security/advisories/GHSA-xxxx',
      { cveId: CVE },
    )
    const repo = classifyRemediationReference(
      'https://github.com/org/repo',
      { cveId: CVE },
    )
    assert.equal(advisory.label, 'Security advisory')
    assert.ok(advisory.score > repo.score)
  })

  it('malformed URL scores negative', () => {
    const r = classifyRemediationReference('not-a-url', { cveId: CVE })
    assert.equal(r.score, -1)
  })
})

describe('pickPrimaryRemediationReference', () => {
  it('prefers NVD CVE page over generic vendor homepage', () => {
    const pick = pickPrimaryRemediationReference(
      { cve_id: CVE, is_kev: false },
      [
        'https://www.cisco.com/',
        `https://nvd.nist.gov/vuln/detail/${CVE}`,
      ],
    )
    assert.equal(pick.label, 'NVD reference')
    assert.match(pick.url, /nvd\.nist\.gov/)
  })

  it('prefers CVE-specific vendor advisory over NVD when both present', () => {
    const pick = pickPrimaryRemediationReference(
      { cve_id: CVE, is_kev: true },
      [
        `https://nvd.nist.gov/vuln/detail/${CVE}`,
        `https://msrc.microsoft.com/update-guide/vulnerability/${CVE}`,
      ],
    )
    assert.equal(pick.label, 'Vendor advisory')
  })
})
