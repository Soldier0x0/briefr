import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  calculateThreatScore,
  classifyEnvironment,
  correlationEscalation,
  deriveOperationalPriority,
  inferAssetMatchSemantics,
  getAssetExposureStatus,
  KEV_FLOOR,
  ASSET_EXPOSURE_TIERS,
} from '../scoring/riskScore.js'

describe('calculateThreatScore parity (ADR-002 S1/S4)', () => {
  const recentKev = new Date()
  recentKev.setDate(recentKev.getDate() - 3)
  const kevDate = recentKev.toISOString().slice(0, 10)

  it('S1: KEV floor with low EPSS → CRIT ≥80', () => {
    const threat = calculateThreatScore({
      is_kev: true,
      kev_date_added: kevDate,
      cvss_score: 9.8,
      epss_score: 0.02,
      has_poc: true,
      public_exploits: [{ type: 'poc' }],
    }, 0.8)
    assert.ok(threat.score >= KEV_FLOOR)
    assert.equal(threat.band, 'CRIT')
    const op = deriveOperationalPriority(threat.band, 'UNKNOWN')
    assert.equal(op.band, 'P1')
    assert.equal(op.provisional, true)
  })

  it('S4: high CVSS alone → LOW threat, P4 provisional', () => {
    const threat = calculateThreatScore({
      is_kev: false,
      cvss_score: 9.8,
      epss_score: 0.05,
      has_poc: false,
      public_exploits: [],
    }, 0.1)
    assert.equal(threat.band, 'LOW')
    const op = deriveOperationalPriority(threat.band, 'UNKNOWN')
    assert.equal(op.band, 'P4')
  })
})

describe('correlationEscalation', () => {
  it('requires same-pulse plus hash/domain edge', () => {
    assert.equal(correlationEscalation({
      campaigns: [{
        lifecycle: 'active',
        confidence: 'high',
        member_count: 3,
        evidence: [
          { type: 'same_pulse' },
          { type: 'shared_indicator', ioc_type: 'IP' },
        ],
      }],
    }), false)
    assert.equal(correlationEscalation({
      campaigns: [{
        lifecycle: 'active',
        confidence: 'high',
        member_count: 3,
        evidence: [
          { type: 'same_pulse' },
          { type: 'shared_indicator', ioc_type: 'HASH' },
        ],
      }],
    }), true)
  })
})

describe('classifyEnvironment parity', () => {
  const profile = { applications: [], operatingSystems: [], aiSystems: [] }

  it('maps vendor-level score to POSSIBLE tier', () => {
    const env = classifyEnvironment({}, profile, 0, 0.75, 'Vendor match (Apache)')
    assert.equal(env.tier, 'POSSIBLE')
  })
})

describe('inferAssetMatchSemantics', () => {
  it('no profile match uses non-definitive wording', () => {
    const s = inferAssetMatchSemantics('No matching assets in your profile', 0)
    assert.equal(s.label, 'NO MATCH FOUND')
    assert.equal(s.headline, 'NO PROFILE MATCH DETECTED')
    assert.doesNotMatch(s.headline, /not in your stack/i)
  })

  it('authoritative backend CPE version match is STRONG MATCH', () => {
    const s = inferAssetMatchSemantics(
      'Your asset directly affected (exact CPE version match)',
      1.0,
    )
    assert.equal(s.label, 'STRONG MATCH')
    assert.match(s.detail, /version constraints/i)
  })

  it('fuzzy exact CPE at 1.0 is HIGH — not confirmed affected', () => {
    const s = inferAssetMatchSemantics(
      'Log4j 2.14 directly affected (exact CPE match)',
      1.0,
    )
    assert.equal(s.label, 'HIGH ASSET RELEVANCE')
    assert.match(s.detail, /not verified/i)
    assert.doesNotMatch(s.label, /CONFIRMED/i)
  })

  it('product-only backend CPE match is HIGH ASSET RELEVANCE', () => {
    const s = inferAssetMatchSemantics(
      'Your asset found in affected products (CPE product match)',
      0.55,
    )
    assert.equal(s.label, 'HIGH ASSET RELEVANCE')
  })

  it('description mention is POSSIBLE MATCH', () => {
    const s = inferAssetMatchSemantics(
      'TensorFlow mentioned in vulnerability description',
      0.45,
    )
    assert.equal(s.label, 'POSSIBLE MATCH')
    assert.equal(s.headline, 'WEAK TEXTUAL OVERLAP')
  })
})

describe('getAssetExposureStatus', () => {
  it('without profile stays EXPOSURE UNKNOWN', () => {
    const status = getAssetExposureStatus({
      hasProfile: false,
      assetMatchType: '',
      components: { asset: { score: 0.5, points: 17.5, weight: 0.35 } },
    })
    assert.equal(status.tier, ASSET_EXPOSURE_TIERS.NOT_LOADED)
    assert.equal(status.headline, 'EXPOSURE UNKNOWN')
    assert.match(status.detail, /Load an asset profile/)
    assert.ok(status.formulaNote)
  })
})
