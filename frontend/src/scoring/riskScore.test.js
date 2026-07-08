import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  inferAssetMatchSemantics,
  getAssetExposureStatus,
  ASSET_EXPOSURE_TIERS,
} from '../scoring/riskScore.js'

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
