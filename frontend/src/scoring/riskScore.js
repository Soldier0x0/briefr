/**
 * BRIEFR Risk Score UI helpers.
 *
 * Canonical scoring runs on the backend: POST /api/cves/{cve_id}/risk
 * Weights for formula display come from GET /api/config/risk (cached at startup).
 */

import { fetchRiskWeights } from '../api.js'

const DEFAULT_WEIGHTS = {
  asset: 0.35,
  kev: 0.25,
  epss: 0.15,
  exploit: 0.10,
  cvss: 0.10,
  momentum: 0.05,
}

let _weights = { ...DEFAULT_WEIGHTS }

export function getRiskWeights() {
  return { ..._weights }
}

export async function fetchAndCacheRiskWeights() {
  try {
    const data = await fetchRiskWeights()
    if (data?.weights && typeof data.weights === 'object') {
      const w = data.weights
      const expectedKeys = Object.keys(DEFAULT_WEIGHTS)
      const receivedKeys = Object.keys(w)
      const keysMatch =
        receivedKeys.length === expectedKeys.length &&
        expectedKeys.every(k => Object.prototype.hasOwnProperty.call(w, k))
      const allFinite = expectedKeys.every(
        k => typeof w[k] === 'number' && Number.isFinite(w[k]),
      )
      if (keysMatch && allFinite) {
        const total = expectedKeys.reduce((s, k) => s + w[k], 0)
        if (Math.abs(total - 1.0) < 1e-6) {
          _weights = w
        }
      }
    }
  } catch {
    // keep bundled fallback
  }
}

const EXPLOIT_SUMMARY_PARTS = [
  { min: 1.0, text: 'Metasploit module' },
  { min: 0.88, text: 'Weaponised exploit' },
  { min: 0.55, text: 'Public PoC' },
  { min: 0.01, text: 'Exploit refs' },
]

function boolish(value) {
  return value === true || value === 1 || value === '1' || value === 'true'
}

export function buildRiskHeroSummary(cve, riskScore) {
  if (!cve || !riskScore) return ''

  const parts = []
  const { hasProfile, assetMatchType, components } = riskScore

  if (hasProfile) {
    if (assetMatchType && assetMatchType !== 'No matching assets in your profile') {
      parts.push('Matches your stack')
    } else {
      parts.push('No stack match')
    }
  }

  if (boolish(cve?.is_kev)) parts.push('KEV listed')

  const exploitScore = components?.exploit?.score ?? 0
  for (const tier of EXPLOIT_SUMMARY_PARTS) {
    if (exploitScore >= tier.min) {
      parts.push(tier.text)
      break
    }
  }

  if (cve.cvss_score != null) {
    parts.push(`CVSS ${cve.cvss_score.toFixed(1)}`)
  } else if (cve.severity && cve.severity !== 'UNKNOWN') {
    parts.push(cve.severity)
  }

  if (!parts.length && components?.epss?.score > 0) {
    parts.push(`${(components.epss.score * 100).toFixed(1)}% EPSS`)
  }

  return parts.slice(0, 3).join(' · ')
}

export const RISK_COMPONENT_LABELS = {
  asset: 'Asset Match',
  kev: 'KEV Status',
  epss: 'EPSS',
  exploit: 'Exploit Avail',
  cvss: 'CVSS',
  momentum: 'Momentum',
}

/** Analyst-facing asset exposure tiers (UI only — scoring unchanged). */
export const ASSET_EXPOSURE_TIERS = {
  NOT_LOADED: 'NOT_LOADED',
  STRONG: 'STRONG',
  HIGH: 'HIGH',
  POSSIBLE: 'POSSIBLE',
  NO_MATCH: 'NO_MATCH',
  UNKNOWN: 'UNKNOWN',
}

/** Backend CPE matcher label — version range evaluated in matching/cpe.py */
const BACKEND_EXACT_CPE_VERSION =
  'Your asset directly affected (exact CPE version match)'

const BACKEND_CPE_PRODUCT =
  'Your asset found in affected products (CPE product match)'

/**
 * Map backend assetMatchType to analyst-safe wording.
 * Fuzzy matcher scores can reach 1.0 without vulnerable-version proof.
 */
export function inferAssetMatchSemantics(assetMatchType, assetScore) {
  const mt = String(assetMatchType || '').trim()

  if (!mt || mt === 'No matching assets in your profile' || assetScore === 0) {
    return {
      tier: ASSET_EXPOSURE_TIERS.NO_MATCH,
      label: 'NO MATCH FOUND',
      headline: 'NO PROFILE MATCH DETECTED',
      detail:
        'No products, vendors, operating systems, or technologies in your asset profile match this CVE\'s affected products.',
    }
  }

  if (mt === BACKEND_EXACT_CPE_VERSION) {
    return {
      tier: ASSET_EXPOSURE_TIERS.STRONG,
      label: 'STRONG MATCH',
      headline: 'HIGH ASSET RELEVANCE',
      detail:
        `${mt} — CPE version evaluated against stored vulnerable version constraints.`,
    }
  }

  if (mt === BACKEND_CPE_PRODUCT) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'PRODUCT OVERLAP DETECTED',
      detail: `${mt} — product-level CPE overlap; exact vulnerable version not confirmed.`,
    }
  }

  if (mt.includes('directly affected (exact CPE match)')) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'PRODUCT/VERSION OVERLAP',
      detail:
        `${mt} — profile product/vendor overlap; vulnerable version range not verified by CPE constraints.`,
    }
  }

  if (
    mt.includes('(CPE product match)')
    || mt.includes('(OS match)')
    || assetScore >= 0.8
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'STACK OVERLAP DETECTED',
      detail: mt,
    }
  }

  if (
    mt.includes('mentioned in vulnerability description')
    || mt.includes('referenced in vulnerability description')
    || mt.includes('description mention')
    || mt.includes('referenced in')
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.POSSIBLE,
      label: 'POSSIBLE MATCH',
      headline: 'WEAK TEXTUAL OVERLAP',
      detail: `${mt} — mention in CVE text or partial profile overlap only.`,
    }
  }

  if (
    mt.includes('product match')
    || mt.includes('vendor match')
    || mt.includes('AI system match')
    || (assetScore >= 0.35 && assetScore < 0.8)
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.POSSIBLE,
      label: 'POSSIBLE MATCH',
      headline: 'PARTIAL STACK OVERLAP',
      detail: mt,
    }
  }

  return {
    tier: ASSET_EXPOSURE_TIERS.UNKNOWN,
    label: 'UNKNOWN',
    headline: 'MATCH STATUS UNCLEAR',
    detail: mt || 'Unable to determine asset relevance from available profile and CVE data.',
  }
}

/**
 * Classify asset exposure for display. Backend uses DEFAULT_ASSET_UNKNOWN (0.5)
 * when profile is null — documented here, not changed in the formula.
 */
export function getAssetExposureStatus(riskScore) {
  if (!riskScore) return null

  const { hasProfile, assetMatchType, components } = riskScore
  const assetScore = components?.asset?.score ?? 0
  const assetPoints = components?.asset?.points ?? 0
  const weight = components?.asset?.weight ?? getRiskWeights().asset

  if (!hasProfile) {
    return {
      tier: ASSET_EXPOSURE_TIERS.NOT_LOADED,
      label: 'ASSET DATA NOT LOADED',
      headline: 'EXPOSURE UNKNOWN',
      detail:
        'Load an asset profile to determine whether this CVE affects your environment.',
      matchReason: null,
      showSignalBar: false,
      formulaNote: `Formula placeholder: 0.500 × ${(weight * 100).toFixed(0)}% × 100 = ${assetPoints.toFixed(1)} pts (neutral scoring input — not exposure probability)`,
    }
  }

  const semantics = inferAssetMatchSemantics(assetMatchType, assetScore)

  return {
    tier: semantics.tier,
    label: semantics.label,
    headline: semantics.headline,
    detail: semantics.detail,
    matchReason: assetMatchType && semantics.tier !== ASSET_EXPOSURE_TIERS.NO_MATCH
      ? assetMatchType
      : null,
    showSignalBar: semantics.tier !== ASSET_EXPOSURE_TIERS.NO_MATCH,
    signalScore: assetScore,
    formulaNote: null,
  }
}

export function riskScoreColor(score) {
  if (score == null || Number.isNaN(score)) return 'var(--text3)'
  if (score >= 90) return 'var(--red)'
  if (score >= 70) return '#b84a28'
  if (score >= 40) return 'var(--amber)'
  return 'var(--text3)'
}

/** Score color with severity fallback so medium/high CVEs are not flat grey. */
export function riskScoreDisplayColor(score, severity) {
  const byScore = riskScoreColor(score)
  if (byScore !== 'var(--text3)') return byScore
  const sev = String(severity || '').toUpperCase()
  if (sev === 'CRITICAL') return 'var(--red)'
  if (sev === 'HIGH') return 'var(--amber)'
  if (sev === 'MEDIUM') return 'var(--accent)'
  return byScore
}

export function componentBarColor(score) {
  if (score >= 0.7) return 'var(--red)'
  if (score >= 0.3) return 'var(--amber)'
  return 'var(--text3)'
}
