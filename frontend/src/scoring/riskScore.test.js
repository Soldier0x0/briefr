import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  classifyEnvironment,
  correlationEscalation,
  deriveOperationalPriority,
  applyCorrelationEscalationToRiskScore,
  inferAssetMatchSemantics,
  getAssetExposureStatus,
  KEV_FLOOR,
  ASSET_EXPOSURE_TIERS,
} from '../scoring/riskScore.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const THREAT_FIXTURES = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/threat_parity.json'), 'utf8'),
)

describe('Threat display SSOT is backend fixtures (ADR-002 S1/S4)', () => {
  it('does not export a live calculateThreatScore engine', async () => {
    const mod = await import('../scoring/riskScore.js')
    assert.equal(
      Object.prototype.hasOwnProperty.call(mod, 'calculateThreatScore'),
      false,
      'FE must not recompute Threat for display — use POST /risk',
    )
  })

  it('S1: frozen backend Threat fixture — KEV floor CRIT ≥80 → P1 provisional', () => {
    const fx = THREAT_FIXTURES.s1_cisa_kev_floor
    assert.ok(fx.threat.score >= KEV_FLOOR)
    assert.equal(fx.threat.band, 'CRIT')
    assert.equal(fx.threat.kev_floor_applied, true)
    const op = deriveOperationalPriority(fx.threat.band, 'UNKNOWN')
    assert.equal(op.band, fx.expected_op_unknown)
    assert.equal(op.provisional, true)
  })

  it('S4: frozen backend Threat fixture — CVSS alone → LOW, P4 provisional', () => {
    const fx = THREAT_FIXTURES.s4_cvss_only_low
    assert.equal(fx.threat.band, 'LOW')
    assert.ok(fx.threat.score < 40)
    assert.equal(fx.threat.kev_floor_applied, false)
    const op = deriveOperationalPriority(fx.threat.band, 'UNKNOWN')
    assert.equal(op.band, fx.expected_op_unknown)
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
    assert.match(status.detail, /No My Stack profile is loaded/)
    assert.ok(status.formulaNote)
  })
})

describe('applyCorrelationEscalationToRiskScore', () => {
  it('bumps P2 to P1 when correlation qualifies', () => {
    const riskScore = {
      threat: { band: 'HIGH', score: 72 },
      environment: { tier: 'UNKNOWN' },
      operational_priority: {
        band: 'P2',
        base_band: 'P2',
        provisional: true,
        escalated_by_correlation: false,
        rationale: 'High threat; environment unknown — provisional priority.',
      },
    }
    const correlation = {
      campaigns: [{
        lifecycle: 'active',
        confidence: 'high',
        member_count: 3,
        evidence: [
          { type: 'same_pulse' },
          { type: 'shared_indicator', ioc_type: 'HASH' },
        ],
      }],
    }
    const merged = applyCorrelationEscalationToRiskScore(riskScore, correlation)
    assert.equal(merged.operational_priority.band, 'P1')
    assert.equal(merged.operational_priority.escalated_by_correlation, true)
  })
})

describe('correlation escalation parity with backend derive_operational_priority', () => {
  it('HIGH × UNKNOWN: base P2; corr → P1 (backend contract)', () => {
    const base = deriveOperationalPriority('HIGH', 'UNKNOWN', false)
    assert.equal(base.band, 'P2')
    const bumped = deriveOperationalPriority('HIGH', 'UNKNOWN', true)
    assert.equal(bumped.band, 'P1')
    assert.equal(bumped.escalated_by_correlation, true)
    assert.equal(bumped.base_band, 'P2')
  })

  it('MED × UNKNOWN: corr → P2 (backend S7)', () => {
    const bumped = deriveOperationalPriority('MED', 'UNKNOWN', true)
    assert.equal(bumped.band, 'P2')
    assert.equal(bumped.escalated_by_correlation, true)
  })

  it('CRIT × UNKNOWN stays P1 (no escalate past P1)', () => {
    const bumped = deriveOperationalPriority('CRIT', 'UNKNOWN', true)
    assert.equal(bumped.band, 'P1')
    assert.equal(bumped.escalated_by_correlation, false)
  })
})
