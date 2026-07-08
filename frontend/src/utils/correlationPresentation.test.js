import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildConnectionPanel,
  explainLimitedConfidence,
  formatEvidenceItem,
  linkStrengthLabel,
} from './correlationPresentation.js'

describe('correlationPresentation', () => {
  it('linkStrengthLabel maps confidence levels', () => {
    assert.equal(linkStrengthLabel('high'), 'HIGH')
    assert.equal(linkStrengthLabel('low'), 'LOW')
  })

  it('formatEvidenceItem humanizes shared IP indicator', () => {
    const item = formatEvidenceItem({
      type: 'shared_indicator',
      ioc_type: 'IP',
      value: '185.1.2.3',
    })
    assert.equal(item.heading, 'Shared observable')
    assert.equal(item.value, '185.1.2.3')
    assert.match(item.lines.join(' '), /Type: IP/)
  })

  it('explainLimitedConfidence surfaces IP-only caveat', () => {
    const msg = explainLimitedConfidence('IP-only edges are weaker than domain or hash matches', [])
    assert.match(msg, /IP-only relationship/)
  })

  it('buildConnectionPanel includes link strength and related CVE', () => {
    const panel = buildConnectionPanel({
      cve_id_b: 'CVE-2024-0001',
      confidence: 'low',
      why_not_higher: 'IP-only edges are weaker than domain or hash matches',
      evidence: [{ type: 'shared_indicator', ioc_type: 'IP', value: '1.2.3.4' }],
    }, 'CVE-2024-0002')
    assert.equal(panel.linkStrength, 'LOW')
    assert.equal(panel.relatedCve, 'CVE-2024-0001')
    assert.ok(panel.limitedConfidence)
  })
})
