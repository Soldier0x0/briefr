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
  CONFIRMED: 'CONFIRMED',
  POSSIBLE: 'POSSIBLE',
  NO_MATCH: 'NO_MATCH',
  UNKNOWN: 'UNKNOWN',
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
        'Asset relevance cannot be calculated until an asset profile is loaded. The BRIEFR score formula uses a neutral 0.5 placeholder for the Asset Match component — this is not an organizational exposure probability.',
      matchReason: null,
      showSignalBar: false,
      formulaNote: `Formula placeholder: 0.500 × ${(weight * 100).toFixed(0)}% × 100 = ${assetPoints.toFixed(1)} pts (not exposure)`,
    }
  }

  const noMatch =
    assetScore === 0 ||
    assetMatchType === 'No matching assets in your profile'

  if (noMatch) {
    return {
      tier: ASSET_EXPOSURE_TIERS.NO_MATCH,
      label: 'NO MATCH',
      headline: 'NOT IN YOUR STACK',
      detail:
        'No products, vendors, operating systems, or technologies in your asset profile match this CVE\'s affected products.',
      matchReason: assetMatchType || null,
      showSignalBar: true,
      signalScore: assetScore,
    }
  }

  if (assetScore >= 0.9) {
    return {
      tier: ASSET_EXPOSURE_TIERS.CONFIRMED,
      label: 'CONFIRMED MATCH',
      headline: 'AFFECTED ASSET LIKELY',
      detail: assetMatchType,
      matchReason: assetMatchType,
      showSignalBar: true,
      signalScore: assetScore,
    }
  }

  if (assetScore > 0) {
    return {
      tier: ASSET_EXPOSURE_TIERS.POSSIBLE,
      label: 'POSSIBLE MATCH',
      headline: 'PARTIAL STACK OVERLAP',
      detail: assetMatchType,
      matchReason: assetMatchType,
      showSignalBar: true,
      signalScore: assetScore,
    }
  }

  return {
    tier: ASSET_EXPOSURE_TIERS.UNKNOWN,
    label: 'UNKNOWN',
    headline: 'MATCH STATUS UNCLEAR',
    detail:
      assetMatchType ||
      'Unable to determine asset relevance from available profile and CVE data.',
    matchReason: assetMatchType || null,
    showSignalBar: false,
    signalScore: assetScore,
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
