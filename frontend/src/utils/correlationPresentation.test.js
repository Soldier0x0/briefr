import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildConnectionPanel,
  confidenceBadgeClass,
  confidenceFactorReasons,
  evidenceFreshnessMeta,
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

  it('confidenceFactorReasons extracts and dedupes reason strings', () => {
    const reasons = confidenceFactorReasons([
      { factor: 'ioc_type', value: 'IP', reason: 'Ip-type indicator' },
      { factor: 'degree', value: 50, reason: 'Shared indicator hub' },
      { factor: 'degree', value: 50, reason: 'Shared indicator hub' },
      { factor: 'no_reason' },
    ])
    assert.deepEqual(reasons, ['Ip-type indicator', 'Shared indicator hub'])
  })

  it('confidenceFactorReasons handles missing/non-array input', () => {
    assert.deepEqual(confidenceFactorReasons(undefined), [])
    assert.deepEqual(confidenceFactorReasons(null), [])
  })

  it('formatEvidenceItem includes observation timeline when present', () => {
    const item = formatEvidenceItem({
      type: 'shared_indicator',
      ioc_type: 'DOMAIN',
      value: 'evil.example',
      observed_at: '2024-01-15T00:00:00Z',
      ingested_at: '2026-07-01T00:00:00Z',
      freshness_factor: 0.3,
      freshness_reason: 'Indicator observed 200d ago (DOMAIN half-life 120d)',
    })
    assert.match(item.lines.join(' '), /Observed 2024-01-15/)
    assert.equal(item.stale, true)
  })

  it('evidenceFreshnessMeta skips stale tint when fallback flag set', () => {
    const meta = evidenceFreshnessMeta({
      freshness_factor: 0.25,
      freshness_fallback: true,
    })
    assert.equal(meta.stale, false)
  })

  it('confidenceBadgeClass adds stale modifier', () => {
    assert.match(confidenceBadgeClass('medium', { stale: true }), /corr-badge-stale/)
  })

  it('buildConnectionPanel surfaces confidenceFactors from backend factor vector', () => {
    const panel = buildConnectionPanel({
      cve_id_b: 'CVE-2024-0001',
      confidence: 'low',
      confidence_factors: [
        { factor: 'ioc_type', value: 'IP', reason: 'Ip-type indicator' },
        { factor: 'degree', value: 12, reason: 'Shared indicator hub — seen across 12 CVEs' },
      ],
      evidence: [{ type: 'shared_indicator', ioc_type: 'IP', value: '1.2.3.4' }],
    }, 'CVE-2024-0002')
    assert.deepEqual(panel.confidenceFactors, [
      'Ip-type indicator',
      'Shared indicator hub — seen across 12 CVEs',
    ])
  })
})
