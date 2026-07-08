import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildKevRemediationDisplay,
  buildVendorRemediationDisplay,
  isKevStatusMitigationLabel,
  pickCisaRemediationReference,
  pickVendorRemediationReference,
} from './patchRemediation.js'

describe('buildKevRemediationDisplay', () => {
  it('uses kev_required_action when present — not sentences.kev', () => {
    const block = buildKevRemediationDisplay({
      cve: { is_kev: true, cve_id: 'CVE-2024-0001' },
      sentences: {
        kev: 'Listed in CISA Known Exploited Vulnerabilities catalogue',
        kev_required_action: 'Apply updates per vendor instructions.',
      },
    })
    assert.equal(block?.tag, 'CISA REQUIRED ACTION')
    assert.equal(block?.text, 'Apply updates per vendor instructions.')
    assert.doesNotMatch(block.text, /catalogue/i)
  })

  it('falls back to factual KEV listed text when no required action', () => {
    const kevStatus =
      'CISA has confirmed active exploitation and added this to the KEV catalogue.'
    const block = buildKevRemediationDisplay({
      cve: { is_kev: true },
      sentences: { kev: kevStatus },
    })
    assert.equal(block?.tag, 'CISA KEV LISTED')
    assert.match(block.text, /vendor instructions/i)
    assert.notEqual(block.text, kevStatus)
  })

  it('returns null for non-KEV CVEs without required action', () => {
    const block = buildKevRemediationDisplay({
      cve: { is_kev: false },
      sentences: { kev: 'not listed' },
    })
    assert.equal(block, null)
  })

  it('never treats catalogue status label as mitigation', () => {
    assert.equal(isKevStatusMitigationLabel('CISA MITIGATION GUIDANCE'), true)
    assert.equal(isKevStatusMitigationLabel('CISA REQUIRED ACTION'), false)
  })
})

describe('buildVendorRemediationDisplay', () => {
  it('uses concise copy when patch is available', () => {
    const vendor = buildVendorRemediationDisplay({
      cve: { patch_available: true },
      sentences: {
        patch: 'A patch is available. Apply updates. Remediate this vulnerability as soon as possible.',
      },
    })
    assert.equal(vendor.status, 'PATCH AVAILABLE')
    assert.equal(vendor.text, 'Vendor fix available.')
  })
})

describe('remediation reference picks', () => {
  it('prefers vendor advisory over CISA for vendor link', () => {
    const ref = pickVendorRemediationReference(
      { cve_id: 'CVE-2024-0001', is_kev: true },
      [
        'https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
        'https://helpx.adobe.com/security/products/acrobat/apsb26-68.html',
      ],
    )
    assert.match(ref.url, /adobe\.com/)
  })

  it('picks CISA guidance reference separately', () => {
    const ref = pickCisaRemediationReference(
      { cve_id: 'CVE-2024-0001', is_kev: true },
      ['https://www.cisa.gov/known-exploited-vulnerabilities-catalog'],
    )
    assert.match(ref.url, /cisa\.gov/)
    assert.equal(ref.label, 'CISA guidance')
  })
})
